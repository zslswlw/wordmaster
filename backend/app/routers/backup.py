from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, date
import hashlib
import io
import json
import os
import zipfile
from typing import Optional
from pydantic import BaseModel

from .. import models
from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..auth import get_current_user
from ..services.ai.worker import media_root
from ..services.learning_content import queue_ai_job, seed_word_evolution

router = APIRouter(prefix="/api/backup", tags=["backup"])


class ImportData(BaseModel):
    username: Optional[str] = None
    exported_at: Optional[str] = None
    banks: list = []
    groups: list = []


def _lookup(mapping: dict, key):
    if key in mapping:
        return mapping[key]
    if key is None:
        return None
    try:
        int_key = int(key)
        if int_key in mapping:
            return mapping[int_key]
    except (TypeError, ValueError):
        pass
    str_key = str(key)
    return mapping.get(str_key)


def _delete_current_user_data(db: Session, user_id: int):
    groups = db.query(StudyGroup).filter(StudyGroup.user_id == user_id).all()
    group_ids = [g.id for g in groups]
    banks = db.query(WordBank).filter(WordBank.user_id == user_id).all()
    bank_ids = [b.id for b in banks]
    word_ids = [
        row[0]
        for row in db.query(Word.id).filter(Word.bank_id.in_(bank_ids)).all()
    ] if bank_ids else []

    db.query(models.MemoryExposure).filter(
        models.MemoryExposure.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.user_id == user_id
    ).delete(synchronize_session=False)
    if group_ids:
        db.query(StudyRecord).filter(StudyRecord.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(ReviewPlan).filter(ReviewPlan.group_id.in_(group_ids)).delete(synchronize_session=False)
        db.query(StudyGroup).filter(StudyGroup.id.in_(group_ids)).delete(synchronize_session=False)

    if bank_ids:
        if word_ids:
            db.query(models.WordMemoryLink).filter(
                models.WordMemoryLink.word_id.in_(word_ids)
            ).delete(synchronize_session=False)
        db.query(models.AiJob).filter(
            models.AiJob.bank_id.in_(bank_ids)
        ).delete(synchronize_session=False)
        db.query(Word).filter(Word.bank_id.in_(bank_ids)).delete(synchronize_session=False)
        db.query(WordBank).filter(WordBank.id.in_(bank_ids)).delete(synchronize_session=False)


async def _read_import_payload(request: Request) -> dict:
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded = form.get("file")
        if uploaded is None:
            raise HTTPException(status_code=400, detail="缺少备份文件")
        if hasattr(uploaded, "read"):
            raw = await uploaded.read()
        else:
            raw = str(uploaded).encode("utf-8")
        if raw.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    payload = json.loads(archive.read("backup.json"))
                    manifest = json.loads(archive.read("manifest.json"))
                    restored: list[str] = []
                    root = media_root().resolve()
                    for item in manifest.get("files", []):
                        relative = item["path"].lstrip("/")
                        archive_name = f"media/{relative}"
                        if archive_name not in archive.namelist():
                            continue
                        content = archive.read(archive_name)
                        if hashlib.sha256(content).hexdigest() != item["sha256"]:
                            raise HTTPException(400, f"媒体校验失败: {relative}")
                        destination = (root / relative).resolve()
                        if root not in destination.parents:
                            raise HTTPException(400, "备份包含非法媒体路径")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        temporary = destination.with_suffix(destination.suffix + ".tmp")
                        temporary.write_bytes(content)
                        os.replace(temporary, destination)
                        restored.append(relative)
                    payload["_restored_media_paths"] = restored
                    return payload
            except (KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=400, detail=f"ZIP 备份无效: {exc}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="备份文件不是有效的 JSON")

    try:
        return await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体不是有效的 JSON")


def _memory_export(db: Session, user_id: int, bank_ids: set[int]) -> dict:
    word_rows = db.query(Word.id).filter(Word.bank_id.in_(bank_ids)).all() if bank_ids else []
    word_ids = {row[0] for row in word_rows}
    links = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id.in_(word_ids)
    ).all() if word_ids else []
    active_bundle_ids = {link.active_bundle_id for link in links if link.active_bundle_id}
    active_bundles = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.id.in_(active_bundle_ids)
    ).all() if active_bundle_ids else []
    lexeme_keys = {bundle.lexeme_key for bundle in active_bundles}
    bundles = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.lexeme_key.in_(lexeme_keys)
    ).all() if lexeme_keys else []
    bundle_ids = {bundle.id for bundle in bundles}
    assets = db.query(models.MemoryAsset).filter(
        models.MemoryAsset.bundle_id.in_(bundle_ids)
    ).all() if bundle_ids else []
    feedback = db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.user_id == user_id,
        models.MemoryFeedback.word_id.in_(word_ids),
    ).all() if word_ids else []
    exposures = db.query(models.MemoryExposure).filter(
        models.MemoryExposure.user_id == user_id,
        models.MemoryExposure.word_id.in_(word_ids),
    ).all() if word_ids else []
    jobs = db.query(models.AiJob).filter(
        models.AiJob.bank_id.in_(bank_ids)
    ).all() if bank_ids else []

    return {
        "bundles": [{
            "id": row.id,
            "lexeme_key": row.lexeme_key,
            "word_text": row.word_text,
            "normalized_pos": row.normalized_pos,
            "primary_meaning": row.primary_meaning,
            "strategy": row.strategy,
            "memory_anchor": row.memory_anchor,
            "scene_summary": row.scene_summary,
            "image_prompt": row.image_prompt,
            "narration_text": row.narration_text,
            "prompt_version": row.prompt_version,
            "content_version": row.content_version,
            "text_model": row.text_model,
            "quality_scores": row.quality_scores,
            "status": row.status,
            "source_bundle_id": row.source_bundle_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        } for row in bundles],
        "assets": [{
            "id": row.id,
            "bundle_id": row.bundle_id,
            "asset_type": row.asset_type,
            "file_path": row.file_path,
            "sha256": row.sha256,
            "mime_type": row.mime_type,
            "version": row.version,
            "model": row.model,
            "generation_params": row.generation_params,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in assets],
        "links": [{
            "word_id": row.word_id,
            "active_bundle_id": row.active_bundle_id,
            "status": row.status,
        } for row in links],
        "feedback": [{
            "id": row.id,
            "word_id": row.word_id,
            "bundle_id": row.bundle_id,
            "component": row.component,
            "reason": row.reason,
            "detail": row.detail,
            "status": row.status,
            "replacement_bundle_id": row.replacement_bundle_id,
            "auto_attempts": row.auto_attempts,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        } for row in feedback],
        "exposures": [{
            "word_id": row.word_id,
            "bundle_id": row.bundle_id,
            "group_id": row.group_id,
            "plan_id": row.plan_id,
            "study_type": row.study_type,
            "exposed_at": row.exposed_at.isoformat() if row.exposed_at else None,
            "next_result": row.next_result,
        } for row in exposures],
        "jobs": [{
            "kind": row.kind,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "bank_id": row.bank_id,
            "priority": row.priority,
            "status": row.status,
            "attempts": row.attempts,
            "payload": row.payload,
            "idempotency_key": row.idempotency_key,
        } for row in jobs],
    }


def _parse_datetime(value, fallback=None):
    if not value:
        return fallback
    return datetime.fromisoformat(value)


def _restore_memory(
    db: Session,
    *,
    user_id: int,
    memory: dict,
    word_id_map: dict,
    group_id_map: dict,
    plan_id_map: dict,
    restored_media_paths: set[str],
) -> None:
    bundle_map: dict = {}
    pending_sources: list[tuple[models.MemoryBundle, object]] = []
    for item in memory.get("bundles", []):
        existing = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.lexeme_key == item["lexeme_key"],
            models.MemoryBundle.content_version == item.get("content_version", 1),
        ).first()
        if existing:
            bundle = existing
        else:
            bundle = models.MemoryBundle(
                lexeme_key=item["lexeme_key"],
                word_text=item["word_text"],
                normalized_pos=item.get("normalized_pos"),
                primary_meaning=item["primary_meaning"],
                strategy=item.get("strategy"),
                memory_anchor=item.get("memory_anchor"),
                scene_summary=item.get("scene_summary"),
                image_prompt=item.get("image_prompt"),
                narration_text=item["narration_text"],
                prompt_version=item.get("prompt_version", "memory-v1"),
                content_version=item.get("content_version", 1),
                text_model=item.get("text_model"),
                quality_scores=item.get("quality_scores"),
                status=item.get("status", "active"),
                created_at=_parse_datetime(item.get("created_at"), datetime.utcnow()),
                updated_at=_parse_datetime(item.get("updated_at"), datetime.utcnow()),
            )
            db.add(bundle)
            db.flush()
            pending_sources.append((bundle, item.get("source_bundle_id")))
        for key in (item.get("id"), str(item.get("id"))):
            if key is not None:
                bundle_map[key] = bundle.id

    for bundle, old_source_id in pending_sources:
        bundle.source_bundle_id = _lookup(bundle_map, old_source_id)

    root = media_root()
    for item in memory.get("assets", []):
        bundle_id = _lookup(bundle_map, item.get("bundle_id"))
        if not bundle_id:
            continue
        existing_asset = db.query(models.MemoryAsset).filter(
            models.MemoryAsset.bundle_id == bundle_id,
            models.MemoryAsset.asset_type == item["asset_type"],
            models.MemoryAsset.version == item.get("version", 1),
        ).first()
        relative = (item.get("file_path") or "").lstrip("/")
        media_exists = relative in restored_media_paths or (root / relative).is_file()
        if existing_asset:
            existing_asset.status = "ready" if media_exists else "missing"
            continue
        db.add(models.MemoryAsset(
            bundle_id=bundle_id,
            asset_type=item["asset_type"],
            file_path=relative,
            sha256=item.get("sha256", ""),
            mime_type=item.get("mime_type", "application/octet-stream"),
            version=item.get("version", 1),
            model=item.get("model"),
            generation_params=item.get("generation_params"),
            status="ready" if media_exists else "missing",
            created_at=_parse_datetime(item.get("created_at"), datetime.utcnow()),
        ))

    for item in memory.get("links", []):
        word_id = _lookup(word_id_map, item.get("word_id"))
        bundle_id = _lookup(bundle_map, item.get("active_bundle_id"))
        if not word_id or not bundle_id:
            continue
        link = db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id == word_id,
        ).first()
        if not link:
            link = models.WordMemoryLink(word_id=word_id)
            db.add(link)
        link.active_bundle_id = bundle_id
        link.status = item.get("status", "ready")

    feedback_map = {}
    for item in memory.get("feedback", []):
        word_id = _lookup(word_id_map, item.get("word_id"))
        if not word_id:
            continue
        feedback = models.MemoryFeedback(
            user_id=user_id,
            word_id=word_id,
            bundle_id=_lookup(bundle_map, item.get("bundle_id")),
            component=item.get("component", "memory_anchor"),
            reason=item.get("reason", "其他说明"),
            detail=item.get("detail"),
            status=item.get("status", "pending"),
            replacement_bundle_id=_lookup(
                bundle_map,
                item.get("replacement_bundle_id"),
            ),
            auto_attempts=item.get("auto_attempts", 0),
            created_at=_parse_datetime(item.get("created_at"), datetime.utcnow()),
            resolved_at=_parse_datetime(item.get("resolved_at")),
        )
        db.add(feedback)
        db.flush()
        if item.get("id") is not None:
            feedback_map[item["id"]] = feedback.id

    for item in memory.get("exposures", []):
        word_id = _lookup(word_id_map, item.get("word_id"))
        if not word_id:
            continue
        db.add(models.MemoryExposure(
            user_id=user_id,
            word_id=word_id,
            bundle_id=_lookup(bundle_map, item.get("bundle_id")),
            group_id=_lookup(group_id_map, item.get("group_id")),
            plan_id=_lookup(plan_id_map, item.get("plan_id")),
            study_type=item.get("study_type"),
            exposed_at=_parse_datetime(item.get("exposed_at"), datetime.utcnow()),
            next_result=item.get("next_result"),
        ))
    db.flush()

    restored_word_ids = set(word_id_map.values())
    restored_words = db.query(Word).filter(Word.id.in_(restored_word_ids)).all()
    for word in restored_words:
        link = db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id == word.id,
        ).first()
        if not link or not link.active_bundle_id:
            seed_word_evolution(db, word)
            continue
        bundle = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.id == link.active_bundle_id,
        ).first()
        if not bundle:
            seed_word_evolution(db, word)
            continue
        for asset_type, priority in (("image", 30), ("audio", 35)):
            ready = db.query(models.MemoryAsset).filter(
                models.MemoryAsset.bundle_id == bundle.id,
                models.MemoryAsset.asset_type == asset_type,
                models.MemoryAsset.status == "ready",
            ).first()
            if not ready:
                queue_ai_job(
                    db,
                    kind=asset_type,
                    target_type="bundle",
                    target_id=bundle.id,
                    bank_id=word.bank_id,
                    priority=priority,
                    idempotency_key=f"bundle:{bundle.id}:{asset_type}:v1",
                )

    unfinished_feedback = db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.user_id == user_id,
        models.MemoryFeedback.status.in_(["pending", "generating"]),
    ).all()
    for feedback in unfinished_feedback:
        word = db.query(Word).filter(Word.id == feedback.word_id).first()
        if feedback.status == "pending" or not feedback.replacement_bundle_id:
            queue_ai_job(
                db,
                kind="feedback_bundle",
                target_type="feedback",
                target_id=feedback.id,
                bank_id=word.bank_id if word else None,
                priority=1,
                payload={"feedback_id": feedback.id},
                idempotency_key=f"feedback:{feedback.id}:replacement",
            )
            continue
        for asset_type in ("image", "audio"):
            queue_ai_job(
                db,
                kind=asset_type,
                target_type="bundle",
                target_id=feedback.replacement_bundle_id,
                bank_id=word.bank_id if word else None,
                priority=5,
                payload={"feedback_id": feedback.id},
                idempotency_key=(
                    f"bundle:{feedback.replacement_bundle_id}:{asset_type}:v1"
                ),
            )

    for bundle in db.query(models.MemoryBundle).filter(
        models.MemoryBundle.id.in_(set(bundle_map.values())),
        models.MemoryBundle.status == "replacement",
    ).all() if bundle_map else []:
        source_link = db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.active_bundle_id == bundle.source_bundle_id,
        ).first()
        source_word = db.query(Word).filter(
            Word.id == source_link.word_id,
        ).first() if source_link else None
        for asset_type in ("image", "audio"):
            queue_ai_job(
                db,
                kind=asset_type,
                target_type="bundle",
                target_id=bundle.id,
                bank_id=source_word.bank_id if source_word else None,
                priority=30,
                idempotency_key=f"bundle:{bundle.id}:{asset_type}:v1",
            )


@router.post("/export")
def export_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id

    groups = db.query(StudyGroup).filter(StudyGroup.user_id == user_id).all()
    group_bank_ids = {g.bank_id for g in groups}
    owned_banks = db.query(WordBank).filter(WordBank.user_id == user_id).all()
    bank_by_id = {b.id: b for b in owned_banks}
    if group_bank_ids:
        for bank in db.query(WordBank).filter(WordBank.id.in_(group_bank_ids)).all():
            bank_by_id[bank.id] = bank

    bank_data = []
    for bank in bank_by_id.values():
        words = db.query(Word).filter(Word.bank_id == bank.id).all()
        bank_data.append({
            "id": bank.id,
            "name": bank.name,
            "words": [
                {
                    "id": w.id,
                    "seq_num": w.seq_num,
                    "word": w.word,
                    "phonetic": w.phonetic,
                    "meaning": w.meaning,
                    "example_l1": w.example_l1,
                    "example_l2": w.example_l2,
                    "example_l3": w.example_l3,
                    "image_prompt": w.image_prompt,
                    "image_url": w.image_url,
                    "mnemonic": w.mnemonic,
                    "etymology": w.etymology,
                    "word_family": w.word_family,
                    "synonyms": w.synonyms,
                    "context_audio": w.context_audio,
                    "enriched": w.enriched,
                }
                for w in words
            ]
        })

    group_data = []
    for group in groups:
        records = db.query(StudyRecord).filter(StudyRecord.group_id == group.id).all()
        plans = db.query(ReviewPlan).filter(ReviewPlan.group_id == group.id).all()
        bank = bank_by_id.get(group.bank_id)
        group_data.append({
            "id": group.id,
            "bank_id": group.bank_id,
            "bank_name": bank.name if bank else "",
            "name": group.name,
            "start_seq": group.start_seq,
            "end_seq": group.end_seq,
            "status": group.status,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "completed_at": group.completed_at.isoformat() if group.completed_at else None,
            "records": [
                {
                    "id": r.id,
                    "word_id": r.word_id,
                    "round": r.round,
                    "correct": r.correct,
                    "study_type": r.study_type,
                    "plan_id": r.plan_id,
                    "user_input": r.user_input,
                    "studied_at": r.studied_at.isoformat() if r.studied_at else None
                }
                for r in records
            ],
            "plans": [
                {
                    "id": p.id,
                    "review_date": p.review_date.isoformat() if p.review_date else None,
                    "original_date": p.original_date.isoformat() if p.original_date else None,
                    "review_round": p.review_round,
                    "status": p.status,
                    "postponed_days": p.postponed_days,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None
                }
                for p in plans
            ]
        })
    
    export_data = {
        "username": current_user.username,
        "exported_at": datetime.utcnow().isoformat(),
        "banks": bank_data,
        "groups": group_data,
        "memory": _memory_export(db, user_id, set(bank_by_id)),
    }
    
    return export_data


@router.post("/export-full")
def export_full_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = export_data(db=db, current_user=current_user)
    memory = payload.get("memory", {})
    root = media_root()
    files = []
    written_media: set[str] = set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "backup.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        for asset in memory.get("assets", []):
            relative = (asset.get("file_path") or "").lstrip("/")
            path = root / relative
            if not relative or relative in written_media or not path.is_file():
                continue
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            files.append({
                "path": relative,
                "sha256": digest,
                "size": len(content),
            })
            archive.writestr(f"media/{relative}", content)
            written_media.add(relative)
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "wordmaster-full-backup-v1",
                    "created_at": datetime.utcnow().isoformat(),
                    "files": files,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    buffer.seek(0)
    filename = f"wordmaster_{date.today().isoformat()}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
async def import_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    payload = await _read_import_payload(request)
    data = ImportData.model_validate(payload)
    restored_media_paths = set(payload.get("_restored_media_paths", []))

    _delete_current_user_data(db, current_user.id)

    bank_id_map = {}
    word_maps_by_bank_key = {}
    global_word_id_map = {}
    global_group_id_map = {}
    global_plan_id_map = {}
    for bank_info in data.banks:
        bank = WordBank(
            name=bank_info["name"],
            user_id=current_user.id,
            word_count=len(bank_info.get("words", []))
        )
        db.add(bank)
        db.flush()
        
        word_id_map = {}
        for w in bank_info.get("words", []):
            word = Word(
                bank_id=bank.id,
                seq_num=w["seq_num"],
                word=w["word"],
                phonetic=w.get("phonetic"),
                meaning=w["meaning"],
                example_l1=w.get("example_l1"),
                example_l2=w.get("example_l2"),
                example_l3=w.get("example_l3"),
                image_prompt=w.get("image_prompt"),
                image_url=w.get("image_url"),
                mnemonic=w.get("mnemonic"),
                etymology=w.get("etymology"),
                word_family=w.get("word_family"),
                synonyms=w.get("synonyms"),
                context_audio=w.get("context_audio"),
                enriched=w.get("enriched", False),
            )
            db.add(word)
            db.flush()
            for key in (w.get("id"), w.get("old_id"), w.get("word_id"), w["seq_num"], str(w["seq_num"])):
                if key is not None:
                    word_id_map[key] = word.id
            for key in (w.get("id"), w.get("old_id"), w.get("word_id")):
                if key is not None:
                    global_word_id_map[key] = word.id
        
        old_bank_id = bank_info.get("id") or bank_info.get("old_id") or bank_info.get("bank_id")
        for key in (old_bank_id, bank_info["name"], str(old_bank_id) if old_bank_id is not None else None):
            if key is not None:
                bank_id_map[key] = bank.id
                word_maps_by_bank_key[key] = word_id_map
        word_maps_by_bank_key[bank.id] = word_id_map
    
    for group_info in data.groups:
        bank_ref = group_info.get("bank_id")
        bank_name = group_info.get("bank_name") or group_info.get("bank")
        bank_id = _lookup(bank_id_map, bank_ref) or _lookup(bank_id_map, bank_name)
        if not bank_id:
            continue
        
        group = StudyGroup(
            user_id=current_user.id,
            bank_id=bank_id,
            name=group_info["name"],
            start_seq=group_info["start_seq"],
            end_seq=group_info["end_seq"],
            status=group_info.get("status", "new"),
            created_at=datetime.fromisoformat(group_info["created_at"]) if group_info.get("created_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(group_info["completed_at"]) if group_info.get("completed_at") else None
        )
        db.add(group)
        db.flush()
        for key in (
            group_info.get("id"),
            group_info.get("old_id"),
            group_info.get("group_id"),
        ):
            if key is not None:
                global_group_id_map[key] = group.id

        word_id_map = (
            _lookup(word_maps_by_bank_key, bank_ref)
            or _lookup(word_maps_by_bank_key, bank_name)
            or word_maps_by_bank_key.get(bank_id)
            or {}
        )

        plan_id_map = {}
        plans_by_round = {}
        for p in group_info.get("plans", []):
            plans_by_round.setdefault(p["review_round"], []).append(p)

        for review_round, source_plans in plans_by_round.items():
            p = source_plans[0]
            review_date = date.fromisoformat(p["review_date"]) if p.get("review_date") else date.today()
            original_date = date.fromisoformat(p["original_date"]) if p.get("original_date") else review_date
            completed_sources = [item for item in source_plans if item.get("status") == "completed"]
            completed_dates = sorted(
                item["completed_at"] for item in completed_sources if item.get("completed_at")
            )

            plan = ReviewPlan(
                group_id=group.id,
                review_date=review_date,
                original_date=original_date,
                review_round=review_round,
                status="completed" if completed_sources else p.get("status", "pending"),
                postponed_days=max((item.get("postponed_days", 0) or 0) for item in source_plans),
                completed_at=datetime.fromisoformat(completed_dates[0]) if completed_dates else None
            )
            db.add(plan)
            db.flush()
            for source_plan in source_plans:
                for key in (
                    source_plan.get("id"),
                    source_plan.get("old_id"),
                    source_plan.get("plan_id"),
                ):
                    if key is not None:
                        plan_id_map[key] = plan.id
                        global_plan_id_map[key] = plan.id
        
        canonical_records = {}
        for r in group_info.get("records", []):
            word_id = _lookup(word_id_map, r.get("word_id"))
            if not word_id:
                continue
            plan_id = _lookup(plan_id_map, r.get("plan_id")) if r.get("plan_id") else None
            study_type = r.get("study_type", "new")
            key = (word_id, r["round"], study_type, plan_id)
            canonical_records[key] = (r, word_id, plan_id, study_type)

        for r, word_id, plan_id, study_type in canonical_records.values():
            record = StudyRecord(
                group_id=group.id,
                word_id=word_id,
                round=r["round"],
                correct=r["correct"],
                study_type=study_type,
                plan_id=plan_id,
                user_input=r.get("user_input"),
                studied_at=datetime.fromisoformat(r["studied_at"]) if r.get("studied_at") else datetime.utcnow()
            )
            db.add(record)

    _restore_memory(
        db,
        user_id=current_user.id,
        memory=payload.get("memory", {}),
        word_id_map=global_word_id_map,
        group_id_map=global_group_id_map,
        plan_id_map=global_plan_id_map,
        restored_media_paths=restored_media_paths,
    )
    db.commit()
    
    return {"message": "Data imported successfully"}
