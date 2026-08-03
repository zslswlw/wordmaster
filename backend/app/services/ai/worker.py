import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import case, or_
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

    def recover_interrupted(self) -> int:
        jobs = self.db.query(models.AiJob).filter(
            models.AiJob.status == "running",
        ).all()
        for job in jobs:
            job.status = "pending"
            job.available_at = utc_now()
            job.last_error_message = "应用重启后恢复"
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
        query = self.db.query(models.AiJob).filter(
            models.AiJob.status == "pending",
            models.AiJob.available_at <= utc_now(),
        )
        if kinds:
            query = query.filter(models.AiJob.kind.in_(kinds))
        if flags.priority_bank_id:
            query = query.order_by(
                case(
                    (models.AiJob.bank_id == flags.priority_bank_id, 0),
                    else_=1,
                )
            )
        job = query.order_by(
            models.AiJob.priority.asc(),
            models.AiJob.created_at.asc(),
        ).first()
        if not job:
            return False

        if self._uses_minimax(job):
            quota = await self.refresh_quota()
            threshold = (
                flags.feedback_reserve_percent
                if self._is_feedback_job(job)
                else flags.quota_reserve_percent
            )
            if quota and quota.remaining_percent is not None:
                if quota.remaining_percent <= threshold:
                    job.available_at = quota.reset_at or (utc_now() + timedelta(minutes=10))
                    job.last_error_code = "quota_reserve"
                    job.last_error_message = f"剩余额度 {quota.remaining_percent}% 低于保留线 {threshold}%"
                    self.db.commit()
                    return False

        job.status = "running"
        job.attempts += 1
        job.updated_at = utc_now()
        self.db.commit()
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
                        retry_job.updated_at = utc_now()
                        self.db.commit()
                return False
            job.status = "completed"
            job.last_error_code = None
            job.last_error_message = None
            job.updated_at = utc_now()
            self.db.commit()
            return True
        except QuotaExhaustedError as exc:
            self._reschedule(job, str(exc), exc.code, 600)
        except RateLimitError as exc:
            self._reschedule(job, str(exc), "rate_limited", exc.retry_after or 60)
        except ConfigurationError as exc:
            job.status = "failed"
            job.last_error_code = exc.code or "provider_error"
            job.last_error_message = str(exc)
            self._pause_worker(str(exc))
            self._mark_feedback_manual(job)
            self.db.commit()
        except ContentRejectedError as exc:
            job.status = "failed"
            job.last_error_code = exc.code or "content_rejected"
            job.last_error_message = str(exc)
            self._mark_feedback_manual(job)
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
            self.db.commit()
        except CandidateValidationError as exc:
            job.status = "failed"
            job.last_error_code = "content_validation"
            job.last_error_message = str(exc)[:1000]
            self._mark_feedback_manual(job)
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
                retry_job.updated_at = utc_now()
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

    def _reschedule(
        self,
        job: models.AiJob,
        message: str,
        code: Optional[str],
        seconds: float,
    ) -> None:
        job.status = "pending"
        job.available_at = utc_now() + timedelta(seconds=max(1, seconds))
        job.last_error_code = code
        job.last_error_message = message[:1000]
        self.db.commit()

    def _pause_worker(self, reason: str) -> None:
        flags = self._flags()
        flags.ai_worker_paused = True
        flags.ai_worker_pause_reason = reason[:1000]
        flags.ai_worker_paused_at = utc_now()
        flags.revision = (flags.revision or 1) + 1

    def requeue_failed(self, *, commit: bool = True) -> int:
        """Explicit admin recovery for failed background work after a fix."""

        jobs = self.db.query(models.AiJob).filter(
            models.AiJob.status == "failed",
            models.AiJob.kind.in_(("bundle_text", "bundle_refresh", "image", "audio")),
            or_(
                models.AiJob.last_error_code.is_(None),
                ~models.AiJob.last_error_code.in_(("1026", "1027", "content_rejected")),
            ),
        ).all()
        now = utc_now()
        for job in jobs:
            job.status = "pending"
            job.attempts = 0
            job.available_at = now
            job.last_error_code = None
            job.last_error_message = None
            job.updated_at = now
        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return len(jobs)

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
    ) -> MemoryBundleCandidate:
        last_error: Optional[Exception] = None
        validation_feedback = ""
        for _ in range(2):
            try:
                options = {"feedback_context": feedback_context}
                if validation_feedback:
                    options["validation_feedback"] = validation_feedback
                return await AiService(self.db).generate_memory_candidate(
                    word,
                    **options,
                )
            except (ValueError, TypeError, RuntimeError) as exc:
                last_error = exc
                validation_feedback = str(exc)[:600]
        raise CandidateValidationError(
            f"AI Schema/quality validation failed twice: {last_error}"
        )

    async def _generate_initial_bundle(self, job: models.AiJob) -> None:
        word = self._word(job.target_id)
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

        candidate = await self._validated_candidate(word)
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
                priority=priority + (5 if asset_type == "audio" else 0),
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
    """Persistent text and media lanes; each lane executes one request at a time."""

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._heartbeat_at: Optional[datetime] = None
        self._last_success_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._lane_errors: dict[str, Optional[str]] = {
            "text": None,
            "media": None,
        }

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
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
                await asyncio.wait_for(self._stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass

    async def _supervise(self) -> None:
        while not self._stop.is_set():
            try:
                with self.session_factory() as db:
                    AiJobProcessor(db).recover_interrupted()
                await asyncio.gather(
                    self._consume_lane("text", TEXT_JOB_KINDS),
                    self._consume_lane("media", MEDIA_JOB_KINDS),
                )
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

    async def _consume_lane(
        self,
        lane: str,
        kinds: tuple[str, ...],
    ) -> None:
        while not self._stop.is_set():
            processed = False
            with self.session_factory() as db:
                try:
                    processor = AiJobProcessor(db)
                    processor.recover_stale()
                    processed = await processor.process_next(kinds)
                    if processed:
                        self._last_success_at = utc_now()
                        self._lane_errors[lane] = None
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
            delay = 0.25 if processed else 5
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    def status(self) -> dict:
        alive = bool(self._task and not self._task.done())
        return {
            "alive": alive,
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
            "heartbeat_at": None,
            "last_success_at": None,
            "last_error": "后台执行器尚未启动",
            "lanes": {},
        }
    return _worker.status()
