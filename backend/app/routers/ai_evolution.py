import json
import re
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_admin_user, get_current_user
from ..clock import utc_now
from ..admin_consistency import RevisionConflict, audit_admin_action, utc_iso
from ..services.ai.worker import AiJobProcessor, silent_worker_status
from ..services.learning_content import (
    MeaningNormalizer,
    build_lexeme_key,
    coverage_for_bank,
    queue_ai_job,
    seed_bank_evolution,
)


router = APIRouter(prefix="/api/ai/evolution", tags=["ai-evolution"])

FEEDBACK_REASONS = {
    "联系不强",
    "词义不准",
    "记忆点牵强",
    "图片过于普通",
    "图片质量差",
    "内容不适",
    "其他说明",
}


class FeedbackCreate(BaseModel):
    word_id: int
    bundle_id: Optional[int] = None
    component: Literal["image", "memory_anchor"]
    reason: str
    detail: Optional[str] = Field(default=None, max_length=500)


class ExposureCreate(BaseModel):
    word_id: int
    bundle_id: Optional[int] = None
    group_id: Optional[int] = None
    plan_id: Optional[int] = None
    study_type: Optional[Literal["new", "enhance", "review"]] = None


class WorkerUpdate(BaseModel):
    expected_revision: int
    paused: Optional[bool] = None
    quota_reserve_percent: Optional[int] = Field(default=None, ge=0, le=95)
    feedback_reserve_percent: Optional[int] = Field(default=None, ge=0, le=95)
    priority_bank_id: Optional[int] = None


class BundleEdit(BaseModel):
    memory_anchor: Optional[str] = Field(default=None, min_length=1, max_length=45)
    image_prompt: Optional[str] = Field(default=None, min_length=20, max_length=800)
    narration_text: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @field_validator("image_prompt")
    @classmethod
    def image_prompt_must_be_english(cls, value):
        if value and re.search(r"[\u3400-\u9fff]", value):
            raise ValueError("图片提示词应使用英文")
        return value


class BundleActivation(BaseModel):
    expected_active_bundle_id: Optional[int] = Field(...)


def _api_value(value):
    if hasattr(value, "tzinfo"):
        return utc_iso(value)
    if isinstance(value, dict):
        return {key: _api_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_api_value(item) for item in value]
    return value

    @field_validator("narration_text")
    @classmethod
    def narration_must_be_natural_chinese(cls, value):
        if value and any(
            token in value.lower()
            for token in ("vt.", "vi.", "adj.", "adv.", "prep.")
        ):
            raise ValueError("播报脚本不能包含词性缩写")
        return value


def _flags(db: Session) -> models.FeatureFlags:
    flags = db.query(models.FeatureFlags).first()
    if not flags:
        flags = models.FeatureFlags(id=1)
        db.add(flags)
        db.commit()
        db.refresh(flags)
    return flags


def _json_or_none(value: Optional[str]):
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _job_summary(
    db: Session,
    bank_id: Optional[int] = None,
    *,
    detailed: bool = True,
) -> dict:
    query = db.query(models.AiJob)
    if bank_id is not None:
        query = query.filter(models.AiJob.bank_id == bank_id)

    counts = {
        status: count
        for status, count in query.with_entities(
            models.AiJob.status,
            func.count(models.AiJob.id),
        ).group_by(models.AiJob.status).all()
    }
    current_jobs = query.filter(
        models.AiJob.status == "running",
    ).order_by(models.AiJob.updated_at.desc()).all()
    next_job = query.filter(
        models.AiJob.status == "pending",
    ).order_by(
        models.AiJob.priority.asc(),
        models.AiJob.available_at.asc(),
    ).first()
    latest_success = query.filter(
        models.AiJob.status == "completed",
    ).order_by(models.AiJob.updated_at.desc()).first()
    latest_failure = query.filter(
        models.AiJob.status == "failed",
    ).order_by(models.AiJob.updated_at.desc()).first()
    if current_jobs:
        state = "running"
    elif counts.get("pending", 0):
        state = "queued"
    elif counts.get("failed", 0):
        state = "attention"
    else:
        state = "idle"

    def serialize(job):
        if not job:
            return None
        return {
            "id": job.id,
            "kind": job.kind,
            "target_type": job.target_type,
            "target_id": job.target_id,
            "bank_id": job.bank_id,
            "attempts": job.attempts,
            "available_at": utc_iso(job.available_at),
            "updated_at": utc_iso(job.updated_at),
            "last_error_code": job.last_error_code,
            "last_error_message": job.last_error_message,
        }

    result = {
        "state": state,
        "counts": counts,
        "active_jobs": counts.get("pending", 0) + counts.get("running", 0),
        "current_job": serialize(current_jobs[0]) if current_jobs else None,
        "current_jobs": [serialize(job) for job in current_jobs],
        "next_job": serialize(next_job),
        "last_activity_at": utc_iso(latest_success.updated_at) if latest_success else None,
        "last_failure_at": utc_iso(latest_failure.updated_at) if latest_failure else None,
        "latest_failure": serialize(latest_failure),
    }
    if not detailed:
        return result

    by_kind: dict[str, dict[str, int]] = {}
    for kind, status, count in query.with_entities(
        models.AiJob.kind,
        models.AiJob.status,
        func.count(models.AiJob.id),
    ).group_by(models.AiJob.kind, models.AiJob.status).all():
        by_kind.setdefault(kind, {})[status] = int(count)

    completed_24h = {
        kind: int(count)
        for kind, count in query.filter(
            models.AiJob.status == "completed",
            models.AiJob.updated_at >= utc_now() - timedelta(hours=24),
        ).with_entities(
            models.AiJob.kind,
            func.count(models.AiJob.id),
        ).group_by(models.AiJob.kind).all()
    }
    failed_by_code = {
        (code or "unknown"): int(count)
        for code, count in query.filter(
            models.AiJob.status == "failed",
        ).with_entities(
            models.AiJob.last_error_code,
            func.count(models.AiJob.id),
        ).group_by(models.AiJob.last_error_code).order_by(
            func.count(models.AiJob.id).desc(),
        ).limit(8).all()
    }
    result.update({
        "by_kind": by_kind,
        "completed_24h": completed_24h,
        "failed_by_code": failed_by_code,
    })
    return result


def _quota_payload(db: Session) -> dict:
    snapshot = db.query(models.AiQuotaSnapshot).filter(
        models.AiQuotaSnapshot.provider == "minimax",
    ).order_by(models.AiQuotaSnapshot.checked_at.desc()).first()
    if not snapshot:
        return {"status": "unknown", "remaining_percent": None, "checked_at": None}
    return {
        "status": snapshot.status,
        "remaining_percent": snapshot.remaining_percent,
        "reset_at": utc_iso(snapshot.reset_at),
        "checked_at": utc_iso(snapshot.checked_at),
    }


def _worker_payload(db: Session) -> dict:
    flags = _flags(db)
    queue = _job_summary(db)
    raw_runtime = silent_worker_status()
    runtime = _api_value(raw_runtime)
    heartbeat = raw_runtime.get("heartbeat_at")
    heartbeat_stale = (
        heartbeat is None
        or utc_now() - heartbeat > timedelta(seconds=20)
    )
    next_job = queue.get("next_job") or {}
    next_error = next_job.get("last_error_code")

    if flags.ai_worker_paused:
        state = "paused"
    elif not runtime.get("alive") or heartbeat_stale:
        state = "stalled" if queue["active_jobs"] else "idle"
    elif queue.get("current_job"):
        state = "running"
    elif queue["counts"].get("pending", 0):
        if next_error in {"quota_reserve", "2056"}:
            state = "waiting_quota"
        elif next_error in {"rate_limited", "1002", "2045"}:
            state = "waiting_rate_limit"
        else:
            state = "queued"
    elif queue["counts"].get("failed", 0):
        state = "attention"
    else:
        state = "idle"

    return {
        "paused": flags.ai_worker_paused,
        "pause_reason": flags.ai_worker_pause_reason,
        "paused_at": utc_iso(flags.ai_worker_paused_at),
        "revision": flags.revision,
        "state": state,
        "quota_reserve_percent": flags.quota_reserve_percent,
        "feedback_reserve_percent": flags.feedback_reserve_percent,
        "priority_bank_id": flags.priority_bank_id,
        "queue": queue,
        "runtime": runtime,
    }


def _user_word(db: Session, user_id: int, word_id: int) -> models.Word:
    word = db.query(models.Word).join(
        models.StudyGroup,
        models.StudyGroup.bank_id == models.Word.bank_id,
    ).filter(
        models.Word.id == word_id,
        models.StudyGroup.user_id == user_id,
        models.Word.seq_num >= models.StudyGroup.start_seq,
        models.Word.seq_num <= models.StudyGroup.end_seq,
    ).first()
    if not word:
        raise HTTPException(404, "当前用户的学习组中没有这个单词")
    return word


@router.post("/feedback")
def submit_feedback(
    data: FeedbackCreate,
    db: Session = Depends(models.get_db),
    current_user: models.User = Depends(get_current_user),
):
    if data.reason not in FEEDBACK_REASONS:
        raise HTTPException(400, "不支持的反馈原因")
    word = _user_word(db, current_user.id, data.word_id)
    link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word.id,
    ).first()
    active_bundle_id = link.active_bundle_id if link else None
    if data.bundle_id != active_bundle_id:
        raise HTTPException(409, "展示版本已更新，请刷新后再反馈")
    if not active_bundle_id:
        raise HTTPException(409, "当前仅有本地兜底内容，尚无可更新的 AI 版本")

    existing = db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.user_id == current_user.id,
        models.MemoryFeedback.word_id == word.id,
        models.MemoryFeedback.bundle_id == active_bundle_id,
        models.MemoryFeedback.component == data.component,
        models.MemoryFeedback.status.in_(["pending", "generating", "manual_review"]),
    ).first()
    if existing:
        return {
            "id": existing.id,
            "status": existing.status,
            "message": "该素材已在更新队列中，旧版本会继续显示",
        }

    feedback = models.MemoryFeedback(
        user_id=current_user.id,
        word_id=word.id,
        bundle_id=active_bundle_id,
        component=data.component,
        reason=data.reason,
        detail=data.detail,
        status="pending",
    )
    resolved_count = db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.word_id == word.id,
        models.MemoryFeedback.component == data.component,
        models.MemoryFeedback.status == "resolved",
    ).count()
    feedback.auto_attempts = resolved_count
    if resolved_count >= 2:
        feedback.status = "manual_review"
    db.add(feedback)
    db.flush()
    if feedback.status == "pending":
        queue_ai_job(
            db,
            kind="feedback_bundle",
            target_type="feedback",
            target_id=feedback.id,
            bank_id=word.bank_id,
            priority=1,
            payload={"feedback_id": feedback.id},
            idempotency_key=f"feedback:{feedback.id}:replacement",
        )
    db.commit()
    if feedback.status == "manual_review":
        return {
            "id": feedback.id,
            "status": feedback.status,
            "message": "自动替换已达两版，已转管理员检查；当前素材继续使用",
        }
    return {
        "id": feedback.id,
        "status": "pending",
        "message": "已进入后台更新队列，替代版完成前继续使用当前素材",
    }


@router.get("/feedback")
def list_feedback(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    query = db.query(models.MemoryFeedback)
    if status:
        query = query.filter(models.MemoryFeedback.status == status)
    rows = query.order_by(
        models.MemoryFeedback.created_at.desc(),
    ).limit(min(max(limit, 1), 500)).all()
    result = []
    for row in rows:
        word = db.query(models.Word).filter(models.Word.id == row.word_id).first()
        result.append({
            "id": row.id,
            "word_id": row.word_id,
            "word": word.word if word else "",
            "bundle_id": row.bundle_id,
            "component": row.component,
            "reason": row.reason,
            "detail": row.detail,
            "status": row.status,
            "replacement_bundle_id": row.replacement_bundle_id,
            "auto_attempts": row.auto_attempts,
            "created_at": utc_iso(row.created_at),
        })
    return result


@router.get("/words/{word_id}/versions")
def word_versions(
    word_id: int,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(404, "单词不存在")
    link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word_id,
    ).first()
    if not link or not link.active_bundle_id:
        return {
            "word_id": word_id,
            "active_bundle_id": None,
            "link_revision": link.revision if link else 0,
            "items": [],
        }
    active = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.id == link.active_bundle_id,
    ).first()
    rows = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.lexeme_key == active.lexeme_key,
    ).order_by(models.MemoryBundle.content_version.desc()).all()
    return {
        "word_id": word_id,
        "active_bundle_id": link.active_bundle_id,
        "link_revision": link.revision,
        "items": [{
            "id": row.id,
            "version": row.content_version,
            "status": row.status,
            "memory_anchor": row.memory_anchor,
            "image_prompt": row.image_prompt,
            "narration_text": row.narration_text,
            "prompt_version": row.prompt_version,
            "text_model": row.text_model,
            "quality_scores": _json_or_none(row.quality_scores),
            "assets": [{
                "type": asset.asset_type,
                "url": f"/ai-media/{asset.file_path.lstrip('/')}",
                "status": asset.status,
                "model": asset.model,
            } for asset in db.query(models.MemoryAsset).filter(
                models.MemoryAsset.bundle_id == row.id,
            ).all()],
        } for row in rows],
    }


@router.post("/exposures")
def record_exposure(
    data: ExposureCreate,
    db: Session = Depends(models.get_db),
    current_user: models.User = Depends(get_current_user),
):
    word = _user_word(db, current_user.id, data.word_id)
    if data.group_id:
        group = db.query(models.StudyGroup).filter(
            models.StudyGroup.id == data.group_id,
            models.StudyGroup.user_id == current_user.id,
        ).first()
        if not group or group.bank_id != word.bank_id:
            raise HTTPException(404, "学习组不存在")
    exposure = models.MemoryExposure(
        user_id=current_user.id,
        word_id=word.id,
        bundle_id=data.bundle_id,
        group_id=data.group_id,
        plan_id=data.plan_id,
        study_type=data.study_type,
    )
    db.add(exposure)
    db.commit()
    return {"id": exposure.id}


@router.get("/banks/{bank_id}/coverage")
def bank_coverage(
    bank_id: int,
    db: Session = Depends(models.get_db),
    current_user: models.User = Depends(get_current_user),
):
    bank = db.query(models.WordBank).filter(models.WordBank.id == bank_id).first()
    if not bank:
        raise HTTPException(404, "词库不存在")
    return {
        **coverage_for_bank(db, bank_id),
        "queue": _job_summary(db, bank_id),
    }


@router.post("/banks/{bank_id}/seed")
def seed_bank(
    bank_id: int,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    bank = db.query(models.WordBank).filter(models.WordBank.id == bank_id).first()
    if not bank:
        raise HTTPException(404, "词库不存在")
    return seed_bank_evolution(db, bank_id, priority=50)


@router.get("/quota")
def get_quota(
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    return _quota_payload(db)


@router.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    query = db.query(models.AiJob)
    if status:
        query = query.filter(models.AiJob.status == status)
    jobs = query.order_by(
        models.AiJob.priority.asc(),
        models.AiJob.created_at.desc(),
    ).limit(min(max(limit, 1), 500)).all()
    summary = _job_summary(db)
    return {
        "counts": summary["counts"],
        "summary": summary,
        "items": [
            {
                "id": job.id,
                "kind": job.kind,
                "target_type": job.target_type,
                "target_id": job.target_id,
                "bank_id": job.bank_id,
                "priority": job.priority,
                "status": job.status,
                "attempts": job.attempts,
                "last_error_code": job.last_error_code,
                "last_error_message": job.last_error_message,
                "available_at": utc_iso(job.available_at),
                "updated_at": utc_iso(job.updated_at),
            }
            for job in jobs
        ],
    }


@router.get("/worker")
def get_worker(
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    return _worker_payload(db)


@router.get("/dashboard")
def evolution_dashboard(
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    banks = db.query(models.WordBank).order_by(
        models.WordBank.created_at.asc(),
        models.WordBank.id.asc(),
    ).all()
    bank_rows = []
    for bank in banks:
        coverage = coverage_for_bank(db, bank.id)
        bank_rows.append({
            "id": bank.id,
            "name": bank.name,
            "word_count": bank.word_count,
            "revision": bank.revision,
            **coverage,
            "queue": _job_summary(db, bank.id, detailed=False),
        })
    feedback_count = db.query(func.count(models.MemoryFeedback.id)).filter(
        models.MemoryFeedback.status.in_(["pending", "generating", "manual_review"]),
    ).scalar() or 0
    worker = _worker_payload(db)
    return {
        "observed_at": utc_iso(utc_now()),
        "worker": worker,
        "jobs": worker["queue"]["counts"],
        "quota": _quota_payload(db),
        "banks": bank_rows,
        "feedback_pending": int(feedback_count),
    }


def _worker_config_snapshot(flags: models.FeatureFlags) -> dict:
    return {
        "paused": bool(flags.ai_worker_paused),
        "pause_reason": flags.ai_worker_pause_reason,
        "paused_at": utc_iso(flags.ai_worker_paused_at),
        "quota_reserve_percent": flags.quota_reserve_percent,
        "feedback_reserve_percent": flags.feedback_reserve_percent,
        "priority_bank_id": flags.priority_bank_id,
        "revision": flags.revision,
    }


@router.patch("/worker")
@router.put("/worker")
def update_worker(
    data: WorkerUpdate,
    request: Request,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    flags = _flags(db)
    values = data.model_dump(exclude_unset=True)
    values.pop("expected_revision", None)
    if "priority_bank_id" in values and values["priority_bank_id"] is not None:
        bank = db.query(models.WordBank).filter(
            models.WordBank.id == values["priority_bank_id"],
        ).first()
        if not bank:
            raise HTTPException(404, "优先词库不存在")
    requested_pause = values.pop("paused", None)
    values = {
        key: value
        for key, value in values.items()
        if value is not None or key == "priority_bank_id"
    }
    update_values = dict(values)
    if requested_pause is True:
        update_values.update({
            "ai_worker_paused": True,
            "ai_worker_pause_reason": "管理员手动暂停",
            "ai_worker_paused_at": utc_now(),
        })
    elif requested_pause is False:
        update_values.update({
            "ai_worker_paused": False,
            "ai_worker_pause_reason": None,
            "ai_worker_paused_at": None,
        })

    before = _worker_config_snapshot(flags)
    already_applied = all(
        getattr(flags, key) == value
        for key, value in update_values.items()
        if key != "ai_worker_paused_at"
    )
    if data.expected_revision != flags.revision and not already_applied:
        raise RevisionConflict(_worker_payload(db))

    changed = bool(update_values) and not already_applied
    if changed:
        updated = db.query(models.FeatureFlags).filter(
            models.FeatureFlags.id == flags.id,
            models.FeatureFlags.revision == data.expected_revision,
        ).update(
            {**update_values, "revision": models.FeatureFlags.revision + 1},
            synchronize_session=False,
        )
        if updated != 1:
            db.rollback()
            raise RevisionConflict(_worker_payload(db))
        db.expire_all()
        flags = _flags(db)

    requeued_failed = 0
    if requested_pause is False:
        requeued_failed = AiJobProcessor(db).requeue_failed(commit=False)
    action = (
        "ai_worker.pause" if requested_pause is True
        else "ai_worker.resume" if requested_pause is False
        else "ai_worker.config.update"
    )
    audit_admin_action(
        db,
        request,
        admin,
        action=action,
        target_type="ai_worker",
        target_id=flags.id,
        before=before,
        after={**_worker_config_snapshot(flags), "requeued_failed": requeued_failed},
    )
    db.commit()
    payload = _worker_payload(db)
    payload["requeued_failed"] = requeued_failed
    return payload


@router.post("/jobs/retry-failed")
def retry_failed_jobs(
    request: Request,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    count = AiJobProcessor(db).requeue_failed(commit=False)
    audit_admin_action(
        db,
        request,
        admin,
        action="ai_jobs.retry_failed",
        target_type="ai_job_queue",
        after={"requeued": count},
    )
    db.commit()
    return {"requeued": count, "worker": _worker_payload(db)}


@router.post("/words/{word_id}/regenerate")
def regenerate_word(
    word_id: int,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    if not word:
        raise HTTPException(404, "单词不存在")
    link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word.id,
    ).first()
    if not link or not link.active_bundle_id:
        seed_bank_evolution(db, word.bank_id, priority=5)
        return {"message": "已进入初次生成队列"}
    feedback = models.MemoryFeedback(
        user_id=admin.id,
        word_id=word.id,
        bundle_id=link.active_bundle_id,
        component="memory_anchor",
        reason="其他说明",
        detail="管理员要求重新生成完整记忆包",
        status="pending",
    )
    db.add(feedback)
    db.flush()
    queue_ai_job(
        db,
        kind="feedback_bundle",
        target_type="feedback",
        target_id=feedback.id,
        bank_id=word.bank_id,
        priority=0,
        payload={"feedback_id": feedback.id},
        idempotency_key=f"feedback:{feedback.id}:replacement",
    )
    db.commit()
    return {"feedback_id": feedback.id, "message": "已进入优先更新队列"}


@router.put("/bundles/{bundle_id}")
def edit_bundle(
    bundle_id: int,
    data: BundleEdit,
    request: Request,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    source = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.id == bundle_id,
    ).first()
    if not source:
        raise HTTPException(404, "记忆包不存在")
    values = data.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(400, "没有需要修改的字段")
    replacement = None
    for _attempt in range(5):
        latest = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.lexeme_key == source.lexeme_key,
        ).order_by(models.MemoryBundle.content_version.desc()).first()
        replacement = models.MemoryBundle(
            lexeme_key=source.lexeme_key,
            word_text=source.word_text,
            normalized_pos=source.normalized_pos,
            primary_meaning=source.primary_meaning,
            strategy=source.strategy,
            memory_anchor=values.get("memory_anchor", source.memory_anchor),
            scene_summary=source.scene_summary,
            image_prompt=values.get("image_prompt", source.image_prompt),
            narration_text=values.get("narration_text", source.narration_text),
            prompt_version=f"{source.prompt_version}-admin",
            content_version=(latest.content_version if latest else 0) + 1,
            text_model="admin",
            quality_scores=source.quality_scores,
            status="draft",
            source_bundle_id=source.id,
        )
        db.add(replacement)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            source = db.query(models.MemoryBundle).filter(
                models.MemoryBundle.id == bundle_id,
            ).first()
    else:
        raise HTTPException(409, "版本号竞争频繁，请稍后重试")
    source_assets = db.query(models.MemoryAsset).filter(
        models.MemoryAsset.bundle_id == source.id,
        models.MemoryAsset.status == "ready",
    ).all()
    source_asset_types = {asset.asset_type for asset in source_assets}
    changed_types = set()
    if (
        values.get("image_prompt", source.image_prompt) != source.image_prompt
        or "image" not in source_asset_types
    ):
        changed_types.add("image")
    if (
        values.get("narration_text", source.narration_text) != source.narration_text
        or "audio" not in source_asset_types
    ):
        changed_types.add("audio")
    for asset in source_assets:
        if asset.asset_type in changed_types:
            continue
        db.add(models.MemoryAsset(
            bundle_id=replacement.id,
            asset_type=asset.asset_type,
            file_path=asset.file_path,
            sha256=asset.sha256,
            mime_type=asset.mime_type,
            version=1,
            model=asset.model,
            generation_params=asset.generation_params,
            status="ready",
        ))
    source_link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.active_bundle_id == source.id,
    ).first()
    source_word = db.query(models.Word).filter(
        models.Word.id == source_link.word_id,
    ).first() if source_link else None
    for asset_type in changed_types:
        queue_ai_job(
            db,
            kind=asset_type,
            target_type="bundle",
            target_id=replacement.id,
            bank_id=source_word.bank_id if source_word else None,
            priority=0,
            idempotency_key=f"bundle:{replacement.id}:{asset_type}:v1",
        )
    audit_admin_action(
        db,
        request,
        admin,
        action="memory_bundle.draft.create",
        target_type="memory_bundle",
        target_id=replacement.id,
        before={"source_bundle_id": source.id, "version": source.content_version},
        after={
            "bundle_id": replacement.id,
            "version": replacement.content_version,
            "changed_fields": sorted(values),
        },
    )
    db.commit()
    db.refresh(replacement)
    return {"bundle_id": replacement.id, "status": replacement.status}


@router.post("/words/{word_id}/activate/{bundle_id}")
def activate_bundle(
    word_id: int,
    bundle_id: int,
    data: BundleActivation,
    request: Request,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    return _change_active_bundle(
        word_id=word_id,
        bundle_id=bundle_id,
        expected_active_bundle_id=data.expected_active_bundle_id,
        action="memory_bundle.activate",
        request=request,
        db=db,
        admin=admin,
    )


def _change_active_bundle(
    *,
    word_id: int,
    bundle_id: int,
    expected_active_bundle_id: Optional[int],
    action: str,
    request: Request,
    db: Session,
    admin: models.User,
):
    word = db.query(models.Word).filter(models.Word.id == word_id).first()
    target = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.id == bundle_id,
    ).first()
    if not word or not target or target.word_text.casefold() != word.word.casefold():
        raise HTTPException(404, "单词或记忆包不存在")
    normalized = MeaningNormalizer.normalize(word.meaning)
    expected_lexeme_key = build_lexeme_key(
        word.word,
        normalized.normalized_pos,
        normalized.primary_meaning,
    )
    if target.lexeme_key != expected_lexeme_key:
        raise HTTPException(409, "记忆包词义与当前单词不一致")
    ready_types = {
        row[0]
        for row in db.query(models.MemoryAsset.asset_type).filter(
            models.MemoryAsset.bundle_id == target.id,
            models.MemoryAsset.status == "ready",
        ).all()
    }
    if not {"image", "audio"}.issubset(ready_types):
        raise HTTPException(409, "图片和中文播报尚未全部就绪，不能启用")
    link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word_id,
    ).first()
    if link and link.active_bundle_id:
        current_bundle = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == link.active_bundle_id,
        ).first()
        if current_bundle and current_bundle.lexeme_key != target.lexeme_key:
            raise HTTPException(409, "记忆包词义与当前单词不一致")
    if not link:
        if expected_active_bundle_id is not None:
            raise RevisionConflict({"active_bundle_id": None, "link_revision": 0})
        link = models.WordMemoryLink(word_id=word_id, revision=1)
        db.add(link)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            link = db.query(models.WordMemoryLink).filter(
                models.WordMemoryLink.word_id == word_id,
            ).first()
            if not link or link.active_bundle_id != expected_active_bundle_id:
                raise RevisionConflict({
                    "active_bundle_id": link.active_bundle_id if link else None,
                    "link_revision": link.revision if link else 0,
                })
    previous_id = link.active_bundle_id
    if previous_id != expected_active_bundle_id:
        raise RevisionConflict({
            "active_bundle_id": previous_id,
            "link_revision": link.revision,
        })
    if previous_id == target.id:
        audit_admin_action(
            db,
            request,
            admin,
            action=action,
            target_type="word_memory_link",
            target_id=link.id,
            before={"word_id": word_id, "active_bundle_id": previous_id},
            after={"word_id": word_id, "active_bundle_id": previous_id, "no_change": True},
        )
        db.commit()
        return {
            "bundle_id": target.id,
            "status": "active",
            "link_revision": link.revision,
        }

    active_filter = (
        models.WordMemoryLink.active_bundle_id.is_(None)
        if previous_id is None
        else models.WordMemoryLink.active_bundle_id == previous_id
    )
    updated = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.id == link.id,
        active_filter,
    ).update(
        {
            "active_bundle_id": target.id,
            "status": "ready",
            "updated_at": utc_now(),
            "revision": models.WordMemoryLink.revision + 1,
        },
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        current = db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id == word_id,
        ).first()
        raise RevisionConflict({
            "active_bundle_id": current.active_bundle_id if current else None,
            "link_revision": current.revision if current else 0,
        })
    if previous_id and previous_id != target.id:
        previous = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == previous_id,
        ).first()
        if previous:
            previous.status = "archived"
    target.status = "active"
    if previous_id:
        db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.active_bundle_id == previous_id,
        ).update(
            {
                "active_bundle_id": target.id,
                "status": "ready",
                "updated_at": utc_now(),
                "revision": models.WordMemoryLink.revision + 1,
            },
            synchronize_session=False,
        )
    feedback_rows = db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.word_id == word_id,
        models.MemoryFeedback.status.in_(["pending", "generating", "manual_review"]),
    ).all()
    for feedback in feedback_rows:
        feedback.status = "resolved"
        feedback.replacement_bundle_id = target.id
        feedback.resolved_at = utc_now()
    db.flush()
    db.expire_all()
    current_link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word_id,
    ).first()
    audit_admin_action(
        db,
        request,
        admin,
        action=action,
        target_type="word_memory_link",
        target_id=current_link.id,
        before={"word_id": word_id, "active_bundle_id": previous_id},
        after={
            "word_id": word_id,
            "active_bundle_id": target.id,
            "link_revision": current_link.revision,
        },
    )
    db.commit()
    return {
        "bundle_id": target.id,
        "status": "active",
        "link_revision": current_link.revision,
    }


@router.post("/words/{word_id}/rollback/{bundle_id}")
def rollback_bundle(
    word_id: int,
    bundle_id: int,
    data: BundleActivation,
    request: Request,
    db: Session = Depends(models.get_db),
    admin: models.User = Depends(get_admin_user),
):
    return _change_active_bundle(
        word_id=word_id,
        bundle_id=bundle_id,
        expected_active_bundle_id=data.expected_active_bundle_id,
        action="memory_bundle.rollback",
        request=request,
        db=db,
        admin=admin,
    )
