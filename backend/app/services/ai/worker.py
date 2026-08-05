import asyncio
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from ... import models
from ...clock import utc_now
from ..learning_content import (
    PROMPT_VERSION,
    MeaningNormalizer,
    build_lexeme_key,
    queue_ai_job,
)
from . import AiService, MemoryBundleCandidate
from .base import (
    ConfigurationError,
    ContentRejectedError,
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
)


logger = logging.getLogger(__name__)
QUOTA_CHECK_INTERVAL = timedelta(minutes=10)
STALE_JOB_AGE = timedelta(minutes=10)
TEXT_BATCH_SIZE = 5
TEXT_JOB_KINDS = ("feedback_bundle", "bundle_text", "bundle_refresh")
MEDIA_JOB_KINDS = ("image", "audio")


class CandidateValidationError(Exception):
    pass


def media_root() -> Path:
    configured = os.getenv("AI_MEDIA_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "data" / "ai-media"


def _json_load(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _extract_quota_state(payload: Any) -> tuple[Optional[float], Optional[datetime]]:
    """Understand several historical Token Plan payload shapes conservatively."""

    measurements: list[tuple[float, Optional[datetime]]] = []

    def reset_time(raw: Any) -> Optional[datetime]:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return None
        if value > 10_000_000_000:
            value /= 1000
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    def add_percent(raw: Any, reset: Any = None) -> None:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return
        if 0 <= value <= 1:
            value *= 100
        measurements.append((
            max(0.0, min(100.0, value)),
            reset_time(reset),
        ))

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        lowered = {str(key).lower(): item for key, item in value.items()}
        percent_keys = (
            ("current_interval_remaining_percent", "end_time"),
            ("current_weekly_remaining_percent", "weekly_end_time"),
            ("remaining_percent", "reset_at"),
            ("remain_percent", "reset_at"),
            ("remainingpercentage", "reset_at"),
            ("remainpercentage", "reset_at"),
        )
        for key, reset_key in percent_keys:
            if key in lowered:
                add_percent(lowered[key], lowered.get(reset_key))

        pairs = (
            ("remaining", "total"),
            ("remain", "total"),
            ("remaining_amount", "total_amount"),
            ("remaining_count", "total_count"),
        )
        for remaining_key, total_key in pairs:
            if remaining_key in lowered and total_key in lowered:
                try:
                    remaining = float(lowered[remaining_key])
                    total = float(lowered[total_key])
                    if total > 0:
                        add_percent(remaining * 100 / total, lowered.get("reset_at"))
                except (TypeError, ValueError):
                    pass

        used_pairs = (
            ("used", "total"),
            ("used_amount", "total_amount"),
            ("current_interval_usage_count", "current_interval_total_count"),
        )
        for used_key, total_key in used_pairs:
            if used_key in lowered and total_key in lowered:
                try:
                    used = float(lowered[used_key])
                    total = float(lowered[total_key])
                    if total > 0:
                        add_percent(
                            max(0, total - used) * 100 / total,
                            lowered.get("reset_at"),
                        )
                except (TypeError, ValueError):
                    pass
        for item in value.values():
            walk(item)

    walk(payload)
    if not measurements:
        return None, None
    remaining, reset_at = min(measurements, key=lambda item: item[0])
    return round(remaining, 2), reset_at


def _extract_remaining_percent(payload: Any) -> Optional[float]:
    return _extract_quota_state(payload)[0]


def _extract_quota_resource_states(
    payload: Any,
) -> dict[str, tuple[Optional[float], Optional[datetime]]]:
    """Return conservative text/image/audio balances when the plan exposes them."""

    result: dict[str, tuple[Optional[float], Optional[datetime]]] = {}

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for child in value:
                walk(child)
            return
        if not isinstance(value, dict):
            return
        name = str(value.get("model_name") or "").lower()
        resource = None
        if any(token in name for token in ("image", "图片")):
            resource = "image"
        elif any(token in name for token in ("speech", "audio", "语音")):
            resource = "audio"
        elif any(token in name for token in ("general", "text", "m3", "m2")):
            resource = "text"
        if resource:
            remaining, reset_at = _extract_quota_state(value)
            previous = result.get(resource)
            if remaining is not None and (
                previous is None
                or previous[0] is None
                or remaining < previous[0]
            ):
                result[resource] = (remaining, reset_at)
        for child in value.values():
            walk(child)

    walk(payload)
    return result


def _store_media(
    *,
    bundle_id: int,
    version: int,
    asset_type: str,
    content: bytes,
) -> tuple[str, str, str]:
    digest = hashlib.sha256(content).hexdigest()
    if asset_type == "image":
        if content.startswith(b"\x89PNG"):
            extension, mime_type = "png", "image/png"
        elif content.startswith(b"\xff\xd8"):
            extension, mime_type = "jpg", "image/jpeg"
        elif content.startswith(b"RIFF"):
            extension, mime_type = "webp", "image/webp"
        else:
            raise ProviderError("Generated image format is not supported")
        folder = "images"
    elif asset_type == "audio":
        extension, mime_type, folder = "mp3", "audio/mpeg", "audio"
    else:
        raise ValueError(f"Unsupported asset type: {asset_type}")

    relative = f"{folder}/bundle-{bundle_id}-v{version}-{digest[:12]}.{extension}"
    destination = media_root() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, destination)
    return relative, digest, mime_type


class AiJobProcessor:
    def __init__(self, db: Session):
        self.db = db
        self._prefer_deepseek = False

    def recover_interrupted(self) -> int:
        jobs = self.db.query(models.AiJob).filter(
            models.AiJob.status == "running",
        ).all()
        for job in jobs:
            job.status = "pending"
            job.available_at = utc_now()
            job.last_error_message = "应用重启后恢复"
            job.batch_id = None
            job.started_at = None
        self.db.query(models.AiLaneState).update({
            "current_batch_id": None,
            "current_job_ids": None,
        }, synchronize_session=False)
        self.db.commit()
        return len(jobs)

    def recover_stale(self) -> int:
        cutoff = utc_now() - STALE_JOB_AGE
        jobs = self.db.query(models.AiJob).filter(
            models.AiJob.status == "running",
            models.AiJob.updated_at < cutoff,
        ).all()
        for job in jobs:
            job.status = "pending"
            job.available_at = utc_now()
            job.last_error_code = "stale_recovered"
            job.last_error_message = "运行任务超过十分钟未完成，已自动恢复排队"
            job.batch_id = None
            job.started_at = None
            job.updated_at = utc_now()
        self.db.commit()
        return len(jobs)

    async def refresh_quota(self, *, force: bool = False) -> Optional[models.AiQuotaSnapshot]:
        latest = self.db.query(models.AiQuotaSnapshot).filter(
            models.AiQuotaSnapshot.provider == "minimax",
        ).order_by(models.AiQuotaSnapshot.checked_at.desc()).first()
        if (
            not force
            and latest
            and utc_now() - latest.checked_at < QUOTA_CHECK_INTERVAL
        ):
            return latest

        provider = AiService(self.db).minimax
        if not provider:
            return None
        try:
            payload = await provider.get_quota()
            remaining_percent, reset_at = _extract_quota_state(payload)
            snapshot = models.AiQuotaSnapshot(
                provider="minimax",
                remaining_percent=remaining_percent,
                status="available",
                reset_at=reset_at,
                raw_payload=json.dumps(payload, ensure_ascii=False),
                checked_at=utc_now(),
            )
        except QuotaExhaustedError as exc:
            snapshot = models.AiQuotaSnapshot(
                provider="minimax",
                remaining_percent=0,
                status="exhausted",
                raw_payload=json.dumps(
                    {"code": exc.code, "message": str(exc)},
                    ensure_ascii=False,
                ),
                checked_at=utc_now(),
            )
        except Exception as exc:
            logger.warning("MiniMax quota check failed: %s", exc)
            snapshot = models.AiQuotaSnapshot(
                provider="minimax",
                remaining_percent=None,
                status="unknown",
                raw_payload=json.dumps({"message": str(exc)}, ensure_ascii=False),
                checked_at=utc_now(),
            )
        self.db.add(snapshot)
        self.db.commit()
        return snapshot

    async def process_next(self, kinds: Optional[tuple[str, ...]] = None) -> bool:
        self._prefer_deepseek = False
        state_session = sessionmaker(bind=self.db.get_bind())
        with state_session() as state_db:
            system_state = state_db.query(models.SystemState).filter(
                models.SystemState.id == 1,
            ).first()
            if system_state and system_state.maintenance_mode:
                return False
            maintenance_marker = (
                system_state.maintenance_started_at if system_state else None
            )
        flags = self._flags()
        if flags.ai_worker_paused:
            return False
        lane_name = self._lane_name(kinds)
        lane = self._lane_state(lane_name)
        if lane.blocked_until and lane.blocked_until > utc_now():
            return False
        jobs = self._select_jobs(kinds, flags, lane)
        if not jobs:
            return False
        job = jobs[0]

        if job.kind in TEXT_JOB_KINDS:
            minimax_text_lane = self._lane_state("minimax_text")
            if (
                minimax_text_lane.blocked_until
                and minimax_text_lane.blocked_until > utc_now()
            ):
                if AiService(self.db).deepseek:
                    self._prefer_deepseek = True
                else:
                    self._block_lane(
                        lane,
                        minimax_text_lane.blocked_until,
                        minimax_text_lane.block_reason or "MiniMax 文字通道正在冷却",
                    )
                    self.db.commit()
                    return False

        if self._uses_minimax(job) and not self._prefer_deepseek:
            quota = await self.refresh_quota()
            threshold = (
                flags.feedback_reserve_percent
                if self._is_feedback_job(job)
                else flags.quota_reserve_percent
            )
            if quota:
                resource_name = self._lane_name((job.kind,))
                resource_states = _extract_quota_resource_states(
                    _json_load(quota.raw_payload),
                )
                remaining, resource_reset_at = resource_states.get(
                    resource_name,
                    (quota.remaining_percent, quota.reset_at),
                )
                if remaining is not None and remaining <= threshold:
                    if job.kind in TEXT_JOB_KINDS and AiService(self.db).deepseek:
                        self._prefer_deepseek = True
                        self._block_text_provider({
                            "provider": "minimax",
                            "error_code": "quota_reserve",
                        })
                    else:
                        retry_at = resource_reset_at or (utc_now() + timedelta(minutes=10))
                        job.available_at = retry_at
                        job.last_error_code = "quota_reserve"
                        job.last_error_message = f"{resource_name} 剩余额度 {remaining}% 低于保留线 {threshold}%"
                        self._block_lane(
                            lane,
                            retry_at,
                            job.last_error_message,
                        )
                        self.db.commit()
                        return False

        batch_id = str(uuid.uuid4())
        started_at = utc_now()
        for selected in jobs:
            selected.status = "running"
            selected.attempts += 1
            selected.batch_id = batch_id
            selected.started_at = started_at
            selected.updated_at = started_at
        lane.current_batch_id = batch_id
        lane.current_job_ids = json.dumps([selected.id for selected in jobs])
        lane.heartbeat_at = started_at
        lane.last_error = None
        self.db.commit()

        if len(jobs) > 1:
            return await self._process_initial_batch(
                jobs,
                lane,
                started_at,
                maintenance_marker,
                state_session,
            )
        try:
            await self._dispatch(job)
            with state_session() as state_db:
                current_state = state_db.query(models.SystemState).filter(
                    models.SystemState.id == 1,
                ).first()
                maintenance_changed = current_state and (
                    current_state.maintenance_mode
                    or current_state.maintenance_started_at != maintenance_marker
                )
            if maintenance_changed:
                self.db.rollback()
                if not current_state.maintenance_mode:
                    retry_job = self.db.query(models.AiJob).filter(
                        models.AiJob.id == job.id,
                        models.AiJob.status == "running",
                    ).first()
                    if retry_job:
                        retry_job.status = "pending"
                        retry_job.available_at = utc_now()
                        retry_job.batch_id = None
                        retry_job.started_at = None
                        retry_job.updated_at = utc_now()
                        self.db.commit()
                return False
            self._complete_job(job, lane, started_at)
            self.db.commit()
            return True
        except QuotaExhaustedError as exc:
            self._retry_without_attempt(job, lane, started_at, str(exc), exc.code, 600)
        except RateLimitError as exc:
            self._retry_without_attempt(
                job,
                lane,
                started_at,
                str(exc),
                "rate_limited",
                exc.retry_after or 60,
            )
        except ConfigurationError as exc:
            job.status = "failed"
            job.last_error_code = exc.code or "provider_error"
            job.last_error_message = str(exc)
            self._mark_feedback_manual(job)
            self._record_attempt(job, started_at, "failed", exc.code or "provider_error")
            self._finish_job_state(job)
            self._block_lane(lane, utc_now() + timedelta(minutes=30), str(exc))
            self.db.commit()
        except ContentRejectedError as exc:
            job.status = "failed"
            job.last_error_code = exc.code or "content_rejected"
            job.last_error_message = str(exc)
            self._mark_feedback_manual(job)
            self._record_attempt(job, started_at, "failed", exc.code or "content_rejected")
            self._finish_job_state(job)
            self._clear_lane(lane, error=str(exc))
            self.db.commit()
        except ProviderError as exc:
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                self._mark_feedback_manual(job)
            else:
                job.status = "pending"
                job.available_at = utc_now() + timedelta(
                    seconds=min(900, 30 * (2 ** max(job.attempts - 1, 0)))
                )
            job.last_error_code = exc.code or "provider_error"
            job.last_error_message = str(exc)[:1000]
            outcome = "failed" if job.status == "failed" else "retry"
            self._record_attempt(job, started_at, outcome, job.last_error_code)
            self._finish_job_state(job)
            self._block_lane(
                lane,
                job.available_at if job.status == "pending" else utc_now() + timedelta(seconds=30),
                str(exc),
            )
            self.db.commit()
        except CandidateValidationError as exc:
            job.status = "failed"
            job.last_error_code = "content_validation"
            job.last_error_message = str(exc)[:1000]
            self._mark_feedback_manual(job)
            self._record_attempt(job, started_at, "failed", "content_validation")
            self._finish_job_state(job)
            self._clear_lane(lane, error=str(exc))
            self.db.commit()
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower():
                raise
            self.db.rollback()
            retry_job = self.db.query(models.AiJob).filter(
                models.AiJob.id == job.id,
            ).first()
            if retry_job:
                retry_job.status = "pending"
                retry_job.attempts = max(0, retry_job.attempts - 1)
                retry_job.available_at = utc_now() + timedelta(seconds=5)
                retry_job.last_error_code = "database_busy"
                retry_job.last_error_message = "SQLite 短暂繁忙，任务已自动重新排队"
                self._finish_job_state(retry_job)
                retry_job.updated_at = utc_now()
                retry_lane = self.db.query(models.AiLaneState).filter(
                    models.AiLaneState.name == lane_name,
                ).first()
                if retry_lane:
                    self._clear_lane(retry_lane, error=retry_job.last_error_message)
                self.db.commit()
        except Exception as exc:
            logger.exception("AI job %s failed", job.id)
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                self._mark_feedback_manual(job)
            else:
                job.status = "pending"
                job.available_at = utc_now() + timedelta(
                    seconds=min(900, 30 * (2 ** max(job.attempts - 1, 0)))
                )
            job.last_error_code = "job_error"
            job.last_error_message = str(exc)[:1000]
            outcome = "failed" if job.status == "failed" else "retry"
            self._record_attempt(job, started_at, outcome, "job_error")
            self._finish_job_state(job)
            self._block_lane(
                lane,
                job.available_at if job.status == "pending" else utc_now() + timedelta(seconds=30),
                str(exc),
            )
            self.db.commit()
        return False

    @staticmethod
    def _lane_name(kinds: Optional[tuple[str, ...]]) -> str:
        if kinds == ("image",):
            return "image"
        if kinds == ("audio",):
            return "audio"
        if kinds and set(kinds).issubset(set(TEXT_JOB_KINDS)):
            return "text"
        return "mixed"

    def _lane_state(self, name: str) -> models.AiLaneState:
        lane = self.db.query(models.AiLaneState).filter(
            models.AiLaneState.name == name,
        ).first()
        if not lane:
            lane = models.AiLaneState(name=name, updated_at=utc_now())
            self.db.add(lane)
            self.db.flush()
        return lane

    def _select_jobs(
        self,
        kinds: Optional[tuple[str, ...]],
        flags: models.FeatureFlags,
        lane: models.AiLaneState,
    ) -> list[models.AiJob]:
        query = self.db.query(models.AiJob).filter(
            models.AiJob.status == "pending",
            models.AiJob.available_at <= utc_now(),
        )
        if kinds:
            query = query.filter(models.AiJob.kind.in_(kinds))
        if not query.first():
            return []

        preferred_bank = None
        if flags.priority_bank_id and query.filter(
            models.AiJob.bank_id == flags.priority_bank_id,
        ).first():
            preferred_bank = flags.priority_bank_id
        priority_query = query
        if preferred_bank is not None:
            priority_query = priority_query.filter(models.AiJob.bank_id == preferred_bank)
        min_priority = priority_query.with_entities(
            func.min(models.AiJob.priority),
        ).scalar()
        tier = query.filter(models.AiJob.priority == min_priority)
        if preferred_bank is not None:
            tier = tier.filter(models.AiJob.bank_id == preferred_bank)

        bank_ids = sorted({row[0] for row in tier.with_entities(
            models.AiJob.bank_id,
        ).distinct().all() if row[0] is not None})
        selected_bank = preferred_bank
        if selected_bank is None and bank_ids:
            selected_bank = next(
                (bank_id for bank_id in bank_ids if lane.cursor_bank_id is None or bank_id > lane.cursor_bank_id),
                bank_ids[0],
            )
        if selected_bank is not None:
            tier = tier.filter(models.AiJob.bank_id == selected_bank)
            lane.cursor_bank_id = selected_bank
        else:
            tier = tier.filter(models.AiJob.bank_id.is_(None))

        first = tier.order_by(models.AiJob.created_at.asc()).first()
        if not first:
            return []
        if first.kind != "bundle_text":
            return [first]
        batch = tier.filter(models.AiJob.kind == "bundle_text").order_by(
            models.AiJob.created_at.asc(),
        ).limit(TEXT_BATCH_SIZE).all()
        for index, candidate in enumerate(batch):
            if _json_load(candidate.payload).get("repair_feedback"):
                return [candidate] if index == 0 else batch[:index]
        return batch

    async def _process_initial_batch(
        self,
        jobs: list[models.AiJob],
        lane: models.AiLaneState,
        started_at: datetime,
        maintenance_marker: Optional[datetime],
        state_session,
    ) -> bool:
        try:
            entries = [(job.id, self._word(job.target_id)) for job in jobs]
            service = AiService(self.db)
            candidates, validation_errors = await service.generate_memory_candidates(
                entries,
                prefer_deepseek=self._prefer_deepseek,
            )
            if getattr(service, "batch_fallback_error", None):
                event = service.batch_fallback_error
                self.db.add(models.AiJobAttempt(
                    job_id=jobs[0].id,
                    batch_id=jobs[0].batch_id,
                    kind="bundle_text",
                    provider=event["provider"],
                    model=event["model"],
                    outcome="failed",
                    started_at=started_at,
                    finished_at=utc_now(),
                    duration_ms=event["duration_ms"],
                    error_code=event["error_code"],
                ))
                self._block_text_provider(event)
                self._prefer_deepseek = True
            completed = 0
            repair_jobs: list[models.AiJob] = []
            for job in jobs:
                candidate = candidates.get(job.id)
                if candidate is None:
                    # The batch call was one provider request. A failed item gets
                    # exactly one isolated repair request with its own request id.
                    self._record_attempt(
                        job,
                        started_at,
                        "validation_retry",
                        "content_validation",
                    )
                    payload = _json_load(job.payload)
                    payload["repair_feedback"] = validation_errors.get(
                        job.id,
                        "批量项目未通过校验",
                    )
                    job.payload = json.dumps(payload, ensure_ascii=False)
                    repair_jobs.append(job)
                    continue
                if candidate.generation_model and "deepseek" in candidate.generation_model.lower():
                    job.batch_id = str(uuid.uuid4())
                self._save_initial_bundle(job, self._word(job.target_id), candidate)
                self._complete_job(job, None, started_at)
                completed += 1

            lane_blocked = False
            for index, job in enumerate(repair_jobs):
                job.batch_id = str(uuid.uuid4())
                repair_started_at = utc_now()
                try:
                    candidate = await self._validated_candidate(
                        self._word(job.target_id),
                        validation_feedback=validation_errors.get(
                            job.id,
                            "批量项目未通过校验",
                        ),
                    )
                except CandidateValidationError as exc:
                    job.status = "failed"
                    job.last_error_code = "content_validation"
                    job.last_error_message = str(exc)[:1000]
                    self._record_attempt(
                        job,
                        repair_started_at,
                        "failed",
                        "content_validation",
                    )
                    self._finish_job_state(job)
                    continue
                except ContentRejectedError as exc:
                    job.status = "failed"
                    job.last_error_code = exc.code or "content_rejected"
                    job.last_error_message = str(exc)[:1000]
                    self._record_attempt(
                        job,
                        repair_started_at,
                        "failed",
                        job.last_error_code,
                    )
                    self._finish_job_state(job)
                    continue
                except (QuotaExhaustedError, RateLimitError, ConfigurationError, ProviderError) as exc:
                    if isinstance(exc, QuotaExhaustedError):
                        code = exc.code or "2056"
                        retry_at = utc_now() + timedelta(minutes=10)
                        job.status = "pending"
                        outcome = "retry"
                    elif isinstance(exc, RateLimitError):
                        code = "rate_limited"
                        retry_at = utc_now() + timedelta(seconds=exc.retry_after or 60)
                        job.status = "pending"
                        outcome = "retry"
                    elif isinstance(exc, ConfigurationError):
                        code = exc.code or "provider_error"
                        retry_at = utc_now() + timedelta(minutes=30)
                        job.status = "failed"
                        outcome = "failed"
                    else:
                        code = exc.code or "provider_error"
                        retry_at = utc_now() + timedelta(seconds=30)
                        job.status = "failed" if job.attempts >= job.max_attempts else "pending"
                        outcome = "failed" if job.status == "failed" else "retry"
                    job.available_at = retry_at
                    job.last_error_code = code
                    job.last_error_message = str(exc)[:1000]
                    self._record_attempt(job, repair_started_at, outcome, code)
                    self._finish_job_state(job)
                    for waiting in repair_jobs[index + 1:]:
                        waiting.status = "pending"
                        waiting.available_at = retry_at
                        waiting.last_error_code = code
                        waiting.last_error_message = "同一通道正在冷却，稍后继续单项修复"
                        self._finish_job_state(waiting)
                    self._block_lane(lane, retry_at, str(exc))
                    if completed:
                        lane.last_success_at = utc_now()
                    lane_blocked = True
                    break
                self._save_initial_bundle(job, self._word(job.target_id), candidate)
                self._complete_job(job, None, repair_started_at)
                completed += 1

            with state_session() as state_db:
                current_state = state_db.query(models.SystemState).filter(
                    models.SystemState.id == 1,
                ).first()
                maintenance_changed = current_state and (
                    current_state.maintenance_mode
                    or current_state.maintenance_started_at != maintenance_marker
                )
            if maintenance_changed:
                self.db.rollback()
                return False
            if not lane_blocked:
                self._clear_lane(lane, success=completed > 0)
            self.db.commit()
            return completed > 0
        except QuotaExhaustedError as exc:
            self._retry_batch_without_attempt(jobs, lane, started_at, str(exc), exc.code, 600)
        except RateLimitError as exc:
            self._retry_batch_without_attempt(
                jobs, lane, started_at, str(exc), "rate_limited", exc.retry_after or 60,
            )
        except ConfigurationError as exc:
            for job in jobs:
                job.status = "failed"
                job.last_error_code = exc.code or "provider_error"
                job.last_error_message = str(exc)[:1000]
                self._record_attempt(job, started_at, "failed", job.last_error_code)
                self._finish_job_state(job)
            self._block_lane(lane, utc_now() + timedelta(minutes=30), str(exc))
            self.db.commit()
        except ContentRejectedError as exc:
            for job in jobs:
                job.status = "failed"
                job.last_error_code = exc.code or "content_rejected"
                job.last_error_message = str(exc)[:1000]
                self._record_attempt(job, started_at, "failed", job.last_error_code)
                self._finish_job_state(job)
            self._clear_lane(lane, error=str(exc))
            self.db.commit()
        except ProviderError as exc:
            retry_at = utc_now() + timedelta(seconds=30)
            for job in jobs:
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                else:
                    job.status = "pending"
                    job.available_at = retry_at
                job.last_error_code = exc.code or "provider_error"
                job.last_error_message = str(exc)[:1000]
                self._record_attempt(
                    job,
                    started_at,
                    "failed" if job.status == "failed" else "retry",
                    job.last_error_code,
                )
                self._finish_job_state(job)
            self._block_lane(lane, retry_at, str(exc))
            self.db.commit()
        except Exception as exc:
            logger.exception("AI text batch %s failed", jobs[0].batch_id)
            for job in jobs:
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                else:
                    job.status = "pending"
                    job.available_at = utc_now() + timedelta(
                        seconds=min(900, 30 * (2 ** max(job.attempts - 1, 0)))
                    )
                job.last_error_code = "job_error"
                job.last_error_message = str(exc)[:1000]
                self._record_attempt(
                    job,
                    started_at,
                    "failed" if job.status == "failed" else "retry",
                    "job_error",
                )
                self._finish_job_state(job)
            retry_times = [
                job.available_at for job in jobs if job.status == "pending"
            ]
            self._block_lane(
                lane,
                min(retry_times) if retry_times else utc_now() + timedelta(seconds=30),
                str(exc),
            )
            self.db.commit()
        return False

    def _flags(self) -> models.FeatureFlags:
        flags = self.db.query(models.FeatureFlags).first()
        if not flags:
            flags = models.FeatureFlags(id=1)
            self.db.add(flags)
            self.db.commit()
        return flags

    @staticmethod
    def _uses_minimax(job: models.AiJob) -> bool:
        return job.kind in {
            "bundle_text",
            "bundle_refresh",
            "feedback_bundle",
            "image",
            "audio",
        }

    @staticmethod
    def _is_feedback_job(job: models.AiJob) -> bool:
        return job.kind == "feedback_bundle" or bool(_json_load(job.payload).get("feedback_id"))

    def _record_attempt(
        self,
        job: models.AiJob,
        started_at: datetime,
        outcome: str,
        error_code: Optional[str] = None,
    ) -> None:
        finished_at = utc_now()
        candidate_model = None
        provider_name = "minimax"
        if job.kind in TEXT_JOB_KINDS:
            candidate_model = self._text_model_for_job(job) or "MiniMax-M3"
            if "deepseek" in candidate_model.lower():
                provider_name = "deepseek"
        elif job.kind == "image":
            candidate_model = "image-01"
        elif job.kind == "audio":
            candidate_model = "speech-2.8-turbo"
        self.db.add(models.AiJobAttempt(
            job_id=job.id,
            batch_id=job.batch_id,
            kind=job.kind,
            provider=provider_name,
            model=candidate_model,
            outcome=outcome,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(0, int((finished_at - started_at).total_seconds() * 1000)),
            error_code=error_code,
            retry_at=job.available_at if outcome == "retry" else None,
        ))

    def _text_model_for_job(self, job: models.AiJob) -> Optional[str]:
        bundle = None
        if job.kind == "bundle_text":
            link = self.db.query(models.WordMemoryLink).filter(
                models.WordMemoryLink.word_id == job.target_id,
            ).first()
            if link and link.active_bundle_id:
                bundle = self.db.query(models.MemoryBundle).filter(
                    models.MemoryBundle.id == link.active_bundle_id,
                ).first()
        elif job.kind == "feedback_bundle":
            feedback = self.db.query(models.MemoryFeedback).filter(
                models.MemoryFeedback.id == job.target_id,
            ).first()
            if feedback and feedback.replacement_bundle_id:
                bundle = self.db.query(models.MemoryBundle).filter(
                    models.MemoryBundle.id == feedback.replacement_bundle_id,
                ).first()
        elif job.kind == "bundle_refresh":
            source_id = _json_load(job.payload).get("source_bundle_id")
            bundle = self.db.query(models.MemoryBundle).filter(
                models.MemoryBundle.source_bundle_id == source_id,
            ).order_by(models.MemoryBundle.content_version.desc()).first()
        return bundle.text_model if bundle and bundle.text_model else None

    @staticmethod
    def _finish_job_state(job: models.AiJob) -> None:
        job.batch_id = None
        job.started_at = None
        job.updated_at = utc_now()

    def _complete_job(
        self,
        job: models.AiJob,
        lane: Optional[models.AiLaneState],
        started_at: datetime,
    ) -> None:
        job.status = "completed"
        job.last_error_code = None
        job.last_error_message = None
        self._record_attempt(job, started_at, "completed")
        self._finish_job_state(job)
        if lane is not None:
            self._clear_lane(lane, success=True)

    @staticmethod
    def _clear_lane(
        lane: models.AiLaneState,
        *,
        success: bool = False,
        error: Optional[str] = None,
    ) -> None:
        now = utc_now()
        lane.current_batch_id = None
        lane.current_job_ids = None
        lane.heartbeat_at = now
        lane.updated_at = now
        lane.last_error = error[:1000] if error else None
        if success:
            lane.last_success_at = now
            lane.blocked_until = None
            lane.block_reason = None

    @staticmethod
    def _block_lane(
        lane: models.AiLaneState,
        blocked_until: datetime,
        reason: str,
    ) -> None:
        lane.current_batch_id = None
        lane.current_job_ids = None
        lane.blocked_until = blocked_until
        lane.block_reason = reason[:1000]
        lane.last_error = reason[:1000]
        lane.heartbeat_at = utc_now()
        lane.updated_at = utc_now()

    def _retry_without_attempt(
        self,
        job: models.AiJob,
        lane: models.AiLaneState,
        started_at: datetime,
        message: str,
        code: Optional[str],
        seconds: float,
    ) -> None:
        retry_at = utc_now() + timedelta(seconds=max(1, seconds))
        job.status = "pending"
        job.attempts = max(0, job.attempts - 1)
        job.available_at = retry_at
        job.last_error_code = code
        job.last_error_message = message[:1000]
        self._record_attempt(job, started_at, "retry", code)
        self._finish_job_state(job)
        self._block_lane(lane, retry_at, message)
        self.db.commit()

    def _retry_batch_without_attempt(
        self,
        jobs: list[models.AiJob],
        lane: models.AiLaneState,
        started_at: datetime,
        message: str,
        code: Optional[str],
        seconds: float,
    ) -> None:
        retry_at = utc_now() + timedelta(seconds=max(1, seconds))
        for job in jobs:
            job.status = "pending"
            job.attempts = max(0, job.attempts - 1)
            job.available_at = retry_at
            job.last_error_code = code
            job.last_error_message = message[:1000]
            self._record_attempt(job, started_at, "retry", code)
            self._finish_job_state(job)
        self._block_lane(lane, retry_at, message)
        self.db.commit()

    def requeue_failed(
        self,
        *,
        job_ids: Optional[list[str]] = None,
        error_codes: Optional[list[str]] = None,
        commit: bool = True,
    ) -> int:
        """Explicit admin recovery for failed background work after a fix."""

        query = self.db.query(models.AiJob).filter(
            models.AiJob.status == "failed",
            models.AiJob.kind.in_((
                "bundle_text", "bundle_refresh", "feedback_bundle", "image", "audio",
            )),
        )
        if job_ids:
            query = query.filter(models.AiJob.id.in_(job_ids))
        if error_codes:
            query = query.filter(models.AiJob.last_error_code.in_(error_codes))
        elif not job_ids:
            query = query.filter(or_(
                models.AiJob.last_error_code.is_(None),
                models.AiJob.last_error_code.in_((
                    "database_busy", "job_error", "provider_error", "stale_recovered",
                )),
            ))
        jobs = query.all()
        now = utc_now()
        for job in jobs:
            job.status = "pending"
            job.attempts = 0
            job.available_at = now
            job.last_error_code = None
            job.last_error_message = None
            job.batch_id = None
            job.started_at = None
            job.updated_at = now
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return len(jobs)

    def reconcile_jobs(self, *, apply: bool = False, commit: bool = True) -> dict:
        """Find objectively obsolete pending work without deleting history."""

        reasons: dict[str, list[str]] = {}
        jobs = self.db.query(models.AiJob).filter(
            models.AiJob.status == "pending",
        ).order_by(models.AiJob.id.asc()).all()
        obsolete = self._obsolete_jobs(jobs)
        for job in jobs:
            reason = obsolete.get(job.id)
            if reason:
                reasons.setdefault(reason, []).append(job.id)
        queue_version = [
            (job.id, job.status, job.updated_at.isoformat() if job.updated_at else None)
            for job in jobs
        ]
        digest = hashlib.sha256(json.dumps(
            {"queue": queue_version, "reasons": reasons},
            ensure_ascii=True,
            sort_keys=True,
        ).encode()).hexdigest()
        if apply:
            now = utc_now()
            ids = [job_id for values in reasons.values() for job_id in values]
            if ids:
                self.db.query(models.AiJob).filter(
                    models.AiJob.id.in_(ids),
                    models.AiJob.status == "pending",
                ).update({
                    "status": "cancelled",
                    "last_error_code": "reconciled",
                    "last_error_message": "队列核对确认该步骤已无须执行",
                    "updated_at": now,
                }, synchronize_session=False)
                if commit:
                    self.db.commit()
                else:
                    self.db.flush()
        return {
            "token": digest,
            "total": sum(len(values) for values in reasons.values()),
            "by_reason": {key: len(value) for key, value in reasons.items()},
        }

    def _obsolete_jobs(self, jobs: list[models.AiJob]) -> dict[str, str]:
        """Resolve all reconciliation checks with a fixed number of queries."""

        result: dict[str, str] = {}
        by_kind: dict[str, list[models.AiJob]] = {}
        for job in jobs:
            by_kind.setdefault(job.kind, []).append(job)

        text_jobs = by_kind.get("bundle_text", [])
        if text_jobs:
            existing_words = {
                row[0]
                for row in self.db.query(models.Word.id).join(
                    models.AiJob,
                    and_(
                        models.AiJob.target_id == models.Word.id,
                        models.AiJob.kind == "bundle_text",
                        models.AiJob.status == "pending",
                    ),
                ).all()
            }
            ready_words = {
                row[0]
                for row in self.db.query(models.WordMemoryLink.word_id).join(
                    models.AiJob,
                    and_(
                        models.AiJob.target_id == models.WordMemoryLink.word_id,
                        models.AiJob.kind == "bundle_text",
                        models.AiJob.status == "pending",
                    ),
                ).filter(
                    models.WordMemoryLink.active_bundle_id.isnot(None),
                ).all()
            }
            for job in text_jobs:
                if job.target_id not in existing_words:
                    result[job.id] = "missing_target"
                elif job.target_id in ready_words:
                    result[job.id] = "text_already_ready"

        refresh_jobs = by_kind.get("bundle_refresh", [])
        if refresh_jobs:
            source_by_job = {
                job.id: _json_load(job.payload).get("source_bundle_id")
                for job in refresh_jobs
            }
            sources = {
                bundle.id: bundle
                for bundle in self.db.query(models.MemoryBundle).all()
            }
            for job in refresh_jobs:
                source = sources.get(source_by_job[job.id])
                if not source:
                    result[job.id] = "missing_target"
                elif source.status == "archived" or source.prompt_version == PROMPT_VERSION:
                    result[job.id] = "refresh_obsolete"

        media_jobs = by_kind.get("image", []) + by_kind.get("audio", [])
        if media_jobs:
            bundles = {
                bundle.id: bundle.status
                for bundle in self.db.query(models.MemoryBundle).join(
                    models.AiJob,
                    and_(
                        models.AiJob.target_id == models.MemoryBundle.id,
                        models.AiJob.kind.in_(("image", "audio")),
                        models.AiJob.status == "pending",
                    ),
                ).all()
            }
            ready_assets = {
                (row[0], row[1])
                for row in self.db.query(
                    models.MemoryAsset.bundle_id,
                    models.MemoryAsset.asset_type,
                ).join(
                    models.AiJob,
                    and_(
                        models.AiJob.target_id == models.MemoryAsset.bundle_id,
                        models.AiJob.kind == models.MemoryAsset.asset_type,
                        models.AiJob.status == "pending",
                    ),
                ).filter(
                    models.MemoryAsset.status == "ready",
                ).all()
            }
            for job in media_jobs:
                if job.target_id not in bundles or bundles[job.target_id] == "archived":
                    result[job.id] = "missing_or_archived_bundle"
                elif (job.target_id, job.kind) in ready_assets:
                    result[job.id] = "asset_already_ready"

        feedback_jobs = by_kind.get("feedback_bundle", [])
        if feedback_jobs:
            feedback_states = {
                row[0]: row[1]
                for row in self.db.query(
                    models.MemoryFeedback.id,
                    models.MemoryFeedback.status,
                ).join(
                    models.AiJob,
                    and_(
                        models.AiJob.target_id == models.MemoryFeedback.id,
                        models.AiJob.kind == "feedback_bundle",
                        models.AiJob.status == "pending",
                    ),
                ).all()
            }
            for job in feedback_jobs:
                state = feedback_states.get(job.target_id)
                if state is None or state in {"resolved", "manual_review"}:
                    result[job.id] = "feedback_closed"
        return result

    def _mark_feedback_manual(self, job: models.AiJob) -> None:
        feedback_id = _json_load(job.payload).get("feedback_id")
        if feedback_id:
            feedback = self.db.query(models.MemoryFeedback).filter(
                models.MemoryFeedback.id == feedback_id,
            ).first()
            if feedback:
                feedback.status = "manual_review"

    async def _dispatch(self, job: models.AiJob) -> None:
        if job.kind == "bundle_text":
            await self._generate_initial_bundle(job)
        elif job.kind == "bundle_refresh":
            await self._generate_refresh_bundle(job)
        elif job.kind == "feedback_bundle":
            await self._generate_feedback_bundle(job)
        elif job.kind == "image":
            await self._generate_image(job)
        elif job.kind == "audio":
            await self._generate_audio(job)
        else:
            raise ValueError(f"Unknown AI job kind: {job.kind}")

    async def _validated_candidate(
        self,
        word: models.Word,
        feedback_context: str = "",
        validation_feedback: str = "",
    ) -> MemoryBundleCandidate:
        last_error: Optional[Exception] = None
        current_feedback = validation_feedback
        attempts = 1 if validation_feedback else 2
        for _ in range(attempts):
            try:
                options = {"feedback_context": feedback_context}
                if current_feedback:
                    options["validation_feedback"] = current_feedback
                return await AiService(self.db).generate_memory_candidate(
                    word,
                    prefer_deepseek=self._prefer_deepseek,
                    **options,
                )
            except (ValueError, TypeError, RuntimeError) as exc:
                last_error = exc
                current_feedback = str(exc)[:600]
        raise CandidateValidationError(
            f"AI Schema/quality validation failed: {last_error}"
        )

    async def _generate_initial_bundle(self, job: models.AiJob) -> None:
        word = self._word(job.target_id)
        repair_feedback = _json_load(job.payload).get("repair_feedback", "")
        candidate = await self._validated_candidate(
            word,
            validation_feedback=repair_feedback,
        )
        self._save_initial_bundle(job, word, candidate)

    def _save_initial_bundle(
        self,
        job: models.AiJob,
        word: models.Word,
        candidate: MemoryBundleCandidate,
    ) -> None:
        self._record_candidate_fallbacks(job, candidate)
        normalized = MeaningNormalizer.normalize(word.meaning)
        lexeme_key = build_lexeme_key(
            word.word,
            normalized.normalized_pos,
            normalized.primary_meaning,
        )
        reusable = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.lexeme_key == lexeme_key,
            models.MemoryBundle.status == "active",
        ).order_by(models.MemoryBundle.content_version.desc()).first()
        if reusable:
            self._link_word(word.id, reusable.id, "ready")
            return
        version = self._next_bundle_version(lexeme_key)
        bundle = self._new_bundle(
            word,
            lexeme_key,
            version,
            candidate,
            status="active",
        )
        self.db.flush()
        self._link_word(word.id, bundle.id, "generating_assets")
        self._queue_bundle_assets(
            bundle,
            word.bank_id,
            priority=job.priority,
        )

    async def _generate_feedback_bundle(self, job: models.AiJob) -> None:
        feedback = self.db.query(models.MemoryFeedback).filter(
            models.MemoryFeedback.id == job.target_id,
        ).first()
        if not feedback:
            raise ValueError("Feedback not found")
        if feedback.status == "resolved":
            return
        word = self._word(feedback.word_id)
        normalized = MeaningNormalizer.normalize(word.meaning)
        lexeme_key = build_lexeme_key(
            word.word,
            normalized.normalized_pos,
            normalized.primary_meaning,
        )
        context = "；".join(filter(None, [feedback.reason, feedback.detail]))
        candidate = await self._validated_candidate(word, context)
        self._record_candidate_fallbacks(job, candidate)
        source = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == feedback.bundle_id,
        ).first()
        bundle = self._new_bundle(
            word,
            lexeme_key,
            self._next_bundle_version(lexeme_key),
            candidate,
            status="draft",
            source_bundle_id=feedback.bundle_id,
        )
        feedback.auto_attempts += 1
        feedback.status = "generating"
        self.db.flush()
        feedback.replacement_bundle_id = bundle.id

        image_only = (
            feedback.component == "image"
            and feedback.reason in {"图片过于普通", "图片质量差"}
        )
        text_only = (
            feedback.component == "memory_anchor"
            and feedback.reason == "记忆点牵强"
        )
        if source and image_only:
            bundle.normalized_pos = source.normalized_pos
            bundle.primary_meaning = source.primary_meaning
            bundle.strategy = source.strategy
            bundle.memory_anchor = source.memory_anchor
            bundle.narration_text = source.narration_text
            has_audio = self._clone_asset(source.id, bundle.id, "audio")
            self._queue_bundle_assets(
                bundle,
                word.bank_id,
                feedback.id,
                priority=5,
                asset_types=("image",) if has_audio else ("image", "audio"),
            )
        elif source and text_only:
            bundle.image_prompt = source.image_prompt
            bundle.narration_text = source.narration_text
            missing_types = tuple(
                asset_type
                for asset_type in ("image", "audio")
                if not self._clone_asset(source.id, bundle.id, asset_type)
            )
            self.db.flush()
            if missing_types:
                self._queue_bundle_assets(
                    bundle,
                    word.bank_id,
                    feedback.id,
                    priority=5,
                    asset_types=missing_types,
                )
            else:
                self._maybe_activate_feedback(bundle.id)
        else:
            self._queue_bundle_assets(bundle, word.bank_id, feedback.id, priority=5)

    async def _generate_refresh_bundle(self, job: models.AiJob) -> None:
        word = self._word(job.target_id)
        source_id = _json_load(job.payload).get("source_bundle_id")
        source = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == source_id,
        ).first()
        if not source or source.prompt_version == PROMPT_VERSION:
            return
        candidate = await self._validated_candidate(word)
        self._record_candidate_fallbacks(job, candidate)
        bundle = self._new_bundle(
            word,
            source.lexeme_key,
            self._next_bundle_version(source.lexeme_key),
            candidate,
            status="replacement",
            source_bundle_id=source.id,
        )
        self.db.flush()
        self._queue_bundle_assets(
            bundle,
            word.bank_id,
            priority=job.priority,
        )

    async def _generate_image(self, job: models.AiJob) -> None:
        bundle = self._bundle(job.target_id)
        if self._ready_asset(bundle.id, "image"):
            self._maybe_activate_feedback(bundle.id)
            return
        provider = AiService(self.db).minimax
        if not provider:
            raise ConfigurationError("MiniMax 未配置，图片任务已停止", code="not_configured")
        content = await provider.generate_image(bundle.image_prompt)
        path, digest, mime = _store_media(
            bundle_id=bundle.id,
            version=bundle.content_version,
            asset_type="image",
            content=content,
        )
        self._upsert_asset(
            bundle_id=bundle.id,
            asset_type="image",
            file_path=path,
            sha256=digest,
            mime_type=mime,
            model=provider.config.image_model or "image-01",
            generation_params=json.dumps(
                {"aspect_ratio": "1:1", "prompt_version": bundle.prompt_version},
                ensure_ascii=False,
            ),
        )
        self.db.flush()
        self._maybe_activate_feedback(bundle.id)

    async def _generate_audio(self, job: models.AiJob) -> None:
        bundle = self._bundle(job.target_id)
        if self._ready_asset(bundle.id, "audio"):
            self._maybe_activate_feedback(bundle.id)
            return
        provider = AiService(self.db).minimax
        if not provider:
            raise ConfigurationError("MiniMax 未配置，语音任务已停止", code="not_configured")
        content = await provider.text_to_speech(bundle.narration_text)
        path, digest, mime = _store_media(
            bundle_id=bundle.id,
            version=bundle.content_version,
            asset_type="audio",
            content=content,
        )
        self._upsert_asset(
            bundle_id=bundle.id,
            asset_type="audio",
            file_path=path,
            sha256=digest,
            mime_type=mime,
            model=provider.config.speech_model or "speech-2.8-turbo",
            generation_params=json.dumps(
                {"language_boost": "Chinese"},
                ensure_ascii=False,
            ),
        )
        self.db.flush()
        self._maybe_activate_feedback(bundle.id)

    def _upsert_asset(
        self,
        *,
        bundle_id: int,
        asset_type: str,
        file_path: str,
        sha256: str,
        mime_type: str,
        model: str,
        generation_params: str,
    ) -> None:
        asset = self.db.query(models.MemoryAsset).filter(
            models.MemoryAsset.bundle_id == bundle_id,
            models.MemoryAsset.asset_type == asset_type,
            models.MemoryAsset.version == 1,
        ).first()
        if not asset:
            asset = models.MemoryAsset(
                bundle_id=bundle_id,
                asset_type=asset_type,
                version=1,
            )
            self.db.add(asset)
        asset.file_path = file_path
        asset.sha256 = sha256
        asset.mime_type = mime_type
        asset.model = model
        asset.generation_params = generation_params
        asset.status = "ready"

    def _queue_bundle_assets(
        self,
        bundle: models.MemoryBundle,
        bank_id: int,
        feedback_id: Optional[int] = None,
        priority: int = 30,
        asset_types: tuple[str, ...] = ("image", "audio"),
    ) -> None:
        payload = {"feedback_id": feedback_id} if feedback_id else {}
        for asset_type in asset_types:
            queue_ai_job(
                self.db,
                kind=asset_type,
                target_type="bundle",
                target_id=bundle.id,
                bank_id=bank_id,
                priority=priority,
                payload=payload,
                idempotency_key=f"bundle:{bundle.id}:{asset_type}:v1",
            )

    def _clone_asset(
        self,
        source_bundle_id: int,
        target_bundle_id: int,
        asset_type: str,
    ) -> bool:
        source = self._ready_asset(source_bundle_id, asset_type)
        if not source:
            return False
        self.db.add(models.MemoryAsset(
            bundle_id=target_bundle_id,
            asset_type=source.asset_type,
            file_path=source.file_path,
            sha256=source.sha256,
            mime_type=source.mime_type,
            version=1,
            model=source.model,
            generation_params=source.generation_params,
            status="ready",
        ))
        return True

    def _new_bundle(
        self,
        word: models.Word,
        lexeme_key: str,
        version: int,
        candidate: MemoryBundleCandidate,
        *,
        status: str,
        source_bundle_id: Optional[int] = None,
    ) -> models.MemoryBundle:
        bundle = models.MemoryBundle(
            lexeme_key=lexeme_key,
            word_text=word.word,
            normalized_pos=candidate.normalized_pos,
            primary_meaning=candidate.primary_meaning,
            strategy=candidate.strategy,
            memory_anchor=candidate.memory_anchor,
            scene_summary=candidate.scene_summary,
            image_prompt=candidate.image_prompt,
            narration_text=candidate.narration_text,
            prompt_version=PROMPT_VERSION,
            content_version=version,
            text_model=candidate.generation_model,
            quality_scores=candidate.scores.model_dump_json(),
            status=status,
            source_bundle_id=source_bundle_id,
        )
        self.db.add(bundle)
        return bundle

    def _record_candidate_fallbacks(
        self,
        job: models.AiJob,
        candidate: MemoryBundleCandidate,
    ) -> None:
        finished_at = utc_now()
        for event in getattr(candidate, "_fallback_errors", []):
            duration_ms = int(event.get("duration_ms") or 0)
            self.db.add(models.AiJobAttempt(
                job_id=job.id,
                batch_id=str(uuid.uuid4()),
                kind=job.kind,
                provider=event.get("provider"),
                model=event.get("model"),
                outcome="failed",
                started_at=finished_at - timedelta(milliseconds=duration_ms),
                finished_at=finished_at,
                duration_ms=duration_ms,
                error_code=event.get("error_code"),
            ))
            self._block_text_provider(event)
        if (
            candidate.generation_model
            and "deepseek" not in candidate.generation_model.lower()
        ):
            provider_lane = self.db.query(models.AiLaneState).filter(
                models.AiLaneState.name == "minimax_text",
            ).first()
            if provider_lane:
                self._clear_lane(provider_lane, success=True)

    def _block_text_provider(self, event: dict) -> None:
        if event.get("provider") != "minimax":
            return
        code = str(event.get("error_code") or "provider_error").lower()
        if code in {"ratelimiterror", "1002", "2045"}:
            seconds = 60
        elif code in {"quotaexhaustederror", "2056", "quota_reserve"}:
            seconds = 600
        elif code in {"configurationerror", "1004", "1039", "2013", "http_401", "http_403", "http_404"}:
            seconds = 1800
        else:
            seconds = 30
        self._block_lane(
            self._lane_state("minimax_text"),
            utc_now() + timedelta(seconds=seconds),
            f"MiniMax 文字通道异常：{event.get('error_code') or 'provider_error'}",
        )

    def _maybe_activate_feedback(self, bundle_id: int) -> None:
        feedback = self.db.query(models.MemoryFeedback).filter(
            models.MemoryFeedback.replacement_bundle_id == bundle_id,
            models.MemoryFeedback.status == "generating",
        ).first()
        if not feedback:
            bundle = self._bundle(bundle_id)
            if bundle.status == "replacement":
                if not (
                    self._ready_asset(bundle_id, "image")
                    and self._ready_asset(bundle_id, "audio")
                ):
                    return
                previous = self.db.query(models.MemoryBundle).filter(
                    models.MemoryBundle.id == bundle.source_bundle_id,
                ).first()
                if previous:
                    previous.status = "archived"
                bundle.status = "active"
                self.db.query(models.WordMemoryLink).filter(
                    models.WordMemoryLink.active_bundle_id == bundle.source_bundle_id,
                ).update(
                    {
                        "active_bundle_id": bundle.id,
                        "status": "ready",
                        "updated_at": utc_now(),
                    },
                    synchronize_session=False,
                )
                return
            link_status = (
                "ready"
                if self._ready_asset(bundle_id, "image") and self._ready_asset(bundle_id, "audio")
                else "generating_assets"
            )
            self.db.query(models.WordMemoryLink).filter(
                models.WordMemoryLink.active_bundle_id == bundle_id,
            ).update({"status": link_status}, synchronize_session=False)
            return
        if not (
            self._ready_asset(bundle_id, "image")
            and self._ready_asset(bundle_id, "audio")
        ):
            return

        replacement = self._bundle(bundle_id)
        previous_id = feedback.bundle_id
        previous = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == previous_id,
        ).first()
        if previous:
            previous.status = "archived"
        replacement.status = "active"
        self.db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.active_bundle_id == previous_id,
        ).update(
            {
                "active_bundle_id": replacement.id,
                "status": "ready",
                "updated_at": utc_now(),
                "revision": models.WordMemoryLink.revision + 1,
            },
            synchronize_session=False,
        )
        self._link_word(feedback.word_id, replacement.id, "ready")
        feedback.status = "resolved"
        feedback.resolved_at = utc_now()

    def _next_bundle_version(self, lexeme_key: str) -> int:
        latest = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.lexeme_key == lexeme_key,
        ).order_by(models.MemoryBundle.content_version.desc()).first()
        return (latest.content_version if latest else 0) + 1

    def _link_word(self, word_id: int, bundle_id: int, status: str) -> None:
        link = self.db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id == word_id,
        ).first()
        if not link:
            link = models.WordMemoryLink(word_id=word_id)
            self.db.add(link)
        else:
            link.revision = (link.revision or 1) + 1
        link.active_bundle_id = bundle_id
        link.status = status
        link.updated_at = utc_now()

    def _ready_asset(self, bundle_id: int, asset_type: str) -> Optional[models.MemoryAsset]:
        return self.db.query(models.MemoryAsset).filter(
            models.MemoryAsset.bundle_id == bundle_id,
            models.MemoryAsset.asset_type == asset_type,
            models.MemoryAsset.status == "ready",
        ).first()

    def _word(self, word_id: int) -> models.Word:
        word = self.db.query(models.Word).filter(models.Word.id == word_id).first()
        if not word:
            raise ValueError("Word not found")
        return word

    def _bundle(self, bundle_id: int) -> models.MemoryBundle:
        bundle = self.db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == bundle_id,
        ).first()
        if not bundle:
            raise ValueError("Memory bundle not found")
        return bundle


class SilentAiWorker:
    """One MiniMax call at a time with a 2 text : 1 image : 1 audio cycle."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._heartbeat_at: Optional[datetime] = None
        self._started_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._lane_errors: dict[str, Optional[str]] = {
            "text": None,
            "image": None,
            "audio": None,
        }

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._started_at = utc_now()
        self._task = asyncio.create_task(self._supervise())
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None
        if self._heartbeat_task:
            await self._heartbeat_task
            self._heartbeat_task = None

    async def _heartbeat(self) -> None:
        while not self._stop.is_set():
            self._heartbeat_at = utc_now()
            try:
                with self.session_factory() as db:
                    lane = db.query(models.AiLaneState).filter(
                        models.AiLaneState.name == "scheduler",
                    ).first()
                    if not lane:
                        lane = models.AiLaneState(name="scheduler", updated_at=utc_now())
                        db.add(lane)
                    lane.heartbeat_at = self._heartbeat_at
                    lane.updated_at = self._heartbeat_at
                    db.commit()
            except Exception:
                logger.debug("Unable to persist AI worker heartbeat", exc_info=True)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

    async def _supervise(self) -> None:
        while not self._stop.is_set():
            try:
                with self.session_factory() as db:
                    processor = AiJobProcessor(db)
                    processor.recover_interrupted()
                    processor.reconcile_jobs(apply=True)
                await self._consume()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)[:1000]
                logger.exception("Silent AI worker consumer stopped; restarting")
            if not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass

    async def _consume(self) -> None:
        cycle = (
            ("text", TEXT_JOB_KINDS),
            ("text", TEXT_JOB_KINDS),
            ("image", ("image",)),
            ("audio", ("audio",)),
        )
        cycle_index = 0
        idle_slots = 0
        while not self._stop.is_set():
            lane, kinds = cycle[cycle_index]
            cycle_index = (cycle_index + 1) % len(cycle)
            processed = False
            with self.session_factory() as db:
                try:
                    processor = AiJobProcessor(db)
                    processor.recover_stale()
                    processed = await processor.process_next(kinds)
                    if processed:
                        self._last_success_at = utc_now()
                        self._lane_errors[lane] = None
                        idle_slots = 0
                        self._last_error = next(
                            (error for error in self._lane_errors.values() if error),
                            None,
                        )
                except OperationalError as exc:
                    db.rollback()
                    if "database is locked" in str(exc).lower():
                        message = f"{lane} 通道遇到 SQLite 短暂繁忙，将在下一轮继续"
                        self._lane_errors[lane] = message
                        self._last_error = message
                    else:
                        raise
                except Exception as exc:
                    message = str(exc)[:1000]
                    self._lane_errors[lane] = message
                    self._last_error = message
                    logger.exception("Silent AI worker %s lane iteration failed", lane)
                    db.rollback()
            if not processed:
                idle_slots += 1
            delay = 0.25 if processed or idle_slots < len(cycle) else 5
            if idle_slots >= len(cycle):
                idle_slots = 0
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    def status(self) -> dict:
        alive = bool(self._task and not self._task.done())
        return {
            "alive": alive,
            "started_at": self._started_at,
            "heartbeat_at": self._heartbeat_at,
            "last_success_at": self._last_success_at,
            "last_error": self._last_error,
            "lanes": {
                name: {"last_error": error}
                for name, error in self._lane_errors.items()
            },
        }


_worker: Optional[SilentAiWorker] = None


def start_silent_worker(session_factory) -> None:
    global _worker
    if _worker is None:
        _worker = SilentAiWorker(session_factory)
    _worker.start()


async def stop_silent_worker() -> None:
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None


def silent_worker_status() -> dict:
    if not _worker:
        return {
            "alive": False,
            "started_at": None,
            "heartbeat_at": None,
            "last_success_at": None,
            "last_error": "后台执行器尚未启动",
            "lanes": {},
        }
    return _worker.status()
