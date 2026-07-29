import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..clock import utc_now


PROMPT_VERSION = "memory-v1"

POS_LABELS = {
    "vt": "及物动词",
    "vi": "不及物动词",
    "aux": "助动词",
    "adj": "形容词",
    "adv": "副词",
    "prep": "介词",
    "pron": "代词",
    "conj": "连词",
    "num": "数词",
    "art": "冠词",
    "int": "感叹词",
    "v": "动词",
    "n": "名词",
}
_POS_PATTERN = re.compile(
    r"(?<![A-Za-z])(" + "|".join(sorted(POS_LABELS, key=len, reverse=True)) + r")\.(?![A-Za-z])",
    re.IGNORECASE,
)
_BRACKET_PATTERN = re.compile(r"\([^)]*\)|（[^）]*）|\[[^\]]*\]")
_ENGLISH_EXAMPLE_PATTERN = re.compile(r"\b(?:e\.g\.|example|such as)\b", re.IGNORECASE)
_LATIN_SENTENCE_PATTERN = re.compile(r"(?:\b[A-Za-z][A-Za-z'-]*\b[\s,.:;!?]*){3,}")
_CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class NormalizedMeaning:
    normalized_pos: Optional[str]
    primary_meaning: str
    narration_text: str


class MeaningNormalizer:
    """Turns dirty dictionary meaning text into stable display and narration copy."""

    max_meaning_chars = 24

    @classmethod
    def normalize(cls, meaning: str) -> NormalizedMeaning:
        source = (meaning or "").strip()
        pos_codes = [match.group(1).lower() for match in _POS_PATTERN.finditer(source)]
        normalized_pos = POS_LABELS.get(pos_codes[0]) if pos_codes else None

        cleaned = _BRACKET_PATTERN.sub(" ", source)
        cleaned = _POS_PATTERN.sub(" ", cleaned)
        cleaned = cleaned.replace("\\n", "\n")
        candidates = re.split(r"[\n;；|/]+", cleaned)

        meanings: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if _ENGLISH_EXAMPLE_PATTERN.search(candidate):
                candidate = _ENGLISH_EXAMPLE_PATTERN.split(candidate, maxsplit=1)[0]
            candidate = _LATIN_SENTENCE_PATTERN.sub(" ", candidate)
            candidate = re.sub(r"^\s*(?:\d+[.)、]?\s*)+", "", candidate)
            candidate = re.sub(r"[A-Za-z]+(?:['-][A-Za-z]+)*", " ", candidate)
            candidate = re.sub(r"[“”\"'`<>_=+*#@~^]+", " ", candidate)

            for part in re.split(r"[,，、]+", candidate):
                part = re.sub(r"\s+", "", part)
                part = part.strip("。；;：:！？!?·-—")
                if not part or not _CHINESE_PATTERN.search(part):
                    continue
                if part.startswith(("例如", "例：", "例:")):
                    continue
                key = re.sub(r"[的地得]", "", part)
                if key in seen:
                    continue
                seen.add(key)
                meanings.append(part)
                if len(meanings) == 2:
                    break
            if len(meanings) == 2:
                break

        if not meanings:
            fallback = re.sub(r"\s+", " ", cleaned).strip(" ,，。；;：:")
            primary = fallback or source or "释义待整理"
        else:
            primary = "；".join(meanings)
        primary = cls._truncate_chinese(primary, cls.max_meaning_chars)
        narration = f"{normalized_pos}，{primary}" if normalized_pos else primary
        return NormalizedMeaning(normalized_pos, primary, narration)

    @staticmethod
    def _truncate_chinese(value: str, max_chars: int) -> str:
        value = value.strip()
        chinese_seen = 0
        output: list[str] = []
        for char in value:
            if _CHINESE_PATTERN.match(char):
                chinese_seen += 1
                if chinese_seen > max_chars:
                    break
            output.append(char)
        return "".join(output).rstrip("；;，,、 ")


def build_lexeme_key(word: str, normalized_pos: Optional[str], primary_meaning: str) -> str:
    canonical = "|".join(
        [
            (word or "").strip().casefold(),
            (normalized_pos or "").strip(),
            re.sub(r"\s+", "", primary_meaning or ""),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _legacy_media_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith(("http://", "https://", "/ai-images/")):
        return path
    return f"/ai-images/{os.path.basename(path)}"


def _asset_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return f"/ai-media/{path.lstrip('/')}"


class LearningContentResolver:
    """The only place that decides which learning resource version is displayed."""

    def __init__(self, db: Session):
        self.db = db

    def resolve(self, word: models.Word) -> dict:
        normalized = MeaningNormalizer.normalize(word.meaning)
        link = self.db.query(models.WordMemoryLink).filter(
            models.WordMemoryLink.word_id == word.id,
        ).first()
        bundle = None
        if link and link.active_bundle_id:
            bundle = self.db.query(models.MemoryBundle).filter(
                models.MemoryBundle.id == link.active_bundle_id,
                models.MemoryBundle.status == "active",
            ).first()

        assets: dict[str, models.MemoryAsset] = {}
        if bundle:
            rows = self.db.query(models.MemoryAsset).filter(
                models.MemoryAsset.bundle_id == bundle.id,
                models.MemoryAsset.status == "ready",
            ).order_by(
                models.MemoryAsset.version.desc(),
                models.MemoryAsset.id.desc(),
            ).all()
            for row in rows:
                assets.setdefault(row.asset_type, row)

        image_asset = assets.get("image")
        audio_asset = assets.get("audio")
        has_legacy_text = any(
            [word.mnemonic, word.image_prompt, word.example_l1, word.example_l2]
        )
        source = "ai" if bundle else ("organized" if has_legacy_text else "local")
        display_meaning = bundle.primary_meaning if bundle else normalized.primary_meaning
        narration_text = bundle.narration_text if bundle else normalized.narration_text
        memory_anchor = bundle.memory_anchor if bundle else word.mnemonic
        image_url = (
            _asset_url(image_asset.file_path)
            if image_asset
            else _legacy_media_url(word.image_url)
        )
        narration_audio_url = _asset_url(audio_asset.file_path) if audio_asset else None

        feedback_pending = False
        if bundle:
            feedback_pending = self.db.query(models.MemoryFeedback.id).filter(
                models.MemoryFeedback.word_id == word.id,
                models.MemoryFeedback.bundle_id == bundle.id,
                models.MemoryFeedback.status.in_(["pending", "generating", "manual_review"]),
            ).first() is not None

        return {
            "source": source,
            "bundle_id": bundle.id if bundle else None,
            "version": bundle.content_version if bundle else 0,
            "display_meaning": display_meaning,
            "normalized_pos": bundle.normalized_pos if bundle else normalized.normalized_pos,
            "primary_meaning": display_meaning,
            "memory_anchor": memory_anchor,
            "image_url": image_url,
            "narration_text": narration_text,
            "narration_audio_url": narration_audio_url,
            "text_status": "ready" if memory_anchor else "fallback",
            "image_status": "ready" if image_url else "pending",
            "audio_status": "ready" if narration_audio_url else "fallback",
            "feedback_status": "pending" if feedback_pending else "none",
            "prompt_version": bundle.prompt_version if bundle else None,
        }


def queue_ai_job(
    db: Session,
    *,
    kind: str,
    target_type: str,
    target_id: int,
    idempotency_key: str,
    bank_id: Optional[int] = None,
    priority: int = 100,
    payload: Optional[dict] = None,
) -> models.AiJob:
    for pending in db.new:
        if (
            isinstance(pending, models.AiJob)
            and pending.idempotency_key == idempotency_key
        ):
            pending.priority = min(pending.priority, priority)
            return pending
    existing = db.query(models.AiJob).filter(
        models.AiJob.idempotency_key == idempotency_key,
    ).first()
    if existing:
        existing.priority = min(existing.priority, priority)
        if existing.status == "failed" and existing.attempts < existing.max_attempts:
            existing.status = "pending"
            existing.available_at = utc_now()
        return existing

    job = models.AiJob(
        id=str(uuid.uuid4()),
        kind=kind,
        target_type=target_type,
        target_id=target_id,
        bank_id=bank_id,
        priority=priority,
        status="pending",
        available_at=utc_now(),
        payload=json.dumps(payload or {}, ensure_ascii=False),
        idempotency_key=idempotency_key,
    )
    db.add(job)
    return job


def seed_word_evolution(
    db: Session,
    word: models.Word,
    *,
    priority: int = 100,
) -> str:
    """Reuse a matching active bundle or enqueue text generation for this word."""

    normalized = MeaningNormalizer.normalize(word.meaning)
    lexeme_key = build_lexeme_key(
        word.word,
        normalized.normalized_pos,
        normalized.primary_meaning,
    )
    reusable = db.query(models.MemoryBundle).filter(
        models.MemoryBundle.lexeme_key == lexeme_key,
        models.MemoryBundle.status == "active",
    ).order_by(models.MemoryBundle.content_version.desc()).first()
    link = db.query(models.WordMemoryLink).filter(
        models.WordMemoryLink.word_id == word.id,
    ).first()
    if not link:
        link = models.WordMemoryLink(word_id=word.id, status="pending")
        db.add(link)
    if reusable:
        link.active_bundle_id = reusable.id
        ready_types = {
            row[0]
            for row in db.query(models.MemoryAsset.asset_type).filter(
                models.MemoryAsset.bundle_id == reusable.id,
                models.MemoryAsset.status == "ready",
            ).all()
        }
        for asset_type, asset_priority in (("image", priority + 20), ("audio", priority + 25)):
            if asset_type not in ready_types:
                queue_ai_job(
                    db,
                    kind=asset_type,
                    target_type="bundle",
                    target_id=reusable.id,
                    bank_id=word.bank_id,
                    priority=asset_priority,
                    idempotency_key=f"bundle:{reusable.id}:{asset_type}:v1",
                )
        link.status = "ready" if {"image", "audio"}.issubset(ready_types) else "generating_assets"
        if reusable.prompt_version != PROMPT_VERSION:
            queue_ai_job(
                db,
                kind="bundle_refresh",
                target_type="word",
                target_id=word.id,
                bank_id=word.bank_id,
                priority=priority + 10,
                idempotency_key=(
                    f"bundle:{reusable.id}:refresh:{PROMPT_VERSION}"
                ),
                payload={"source_bundle_id": reusable.id},
            )
        return "reused"

    queue_ai_job(
        db,
        kind="bundle_text",
        target_type="word",
        target_id=word.id,
        bank_id=word.bank_id,
        priority=priority,
        idempotency_key=f"word:{word.id}:bundle:{PROMPT_VERSION}",
    )
    return "queued"


def seed_bank_evolution(
    db: Session,
    bank_id: int,
    *,
    priority: int = 100,
) -> dict:
    words = db.query(models.Word).filter(models.Word.bank_id == bank_id).all()
    result = {"total": len(words), "queued": 0, "reused": 0}
    for word in words:
        state = seed_word_evolution(db, word, priority=priority)
        result[state] += 1
    db.commit()
    return result


def prioritize_group_resources(db: Session, group: models.StudyGroup) -> None:
    words = db.query(models.Word).filter(
        models.Word.bank_id == group.bank_id,
        models.Word.seq_num >= group.start_seq,
        models.Word.seq_num <= group.end_seq,
    ).all()
    for word in words:
        seed_word_evolution(db, word, priority=10)
    db.commit()


def coverage_for_bank(db: Session, bank_id: int) -> dict:
    words = db.query(models.Word).filter(models.Word.bank_id == bank_id).all()
    visual_ready = 0
    complete_ready = 0
    resolver = LearningContentResolver(db)
    for word in words:
        content = resolver.resolve(word)
        image_and_text = (
            content["image_status"] == "ready"
            and content["text_status"] == "ready"
        )
        if image_and_text:
            visual_ready += 1
        if image_and_text and content["audio_status"] == "ready":
            complete_ready += 1
    total = len(words)
    return {
        "bank_id": bank_id,
        "total": total,
        "visual_ready": visual_ready,
        "complete_ready": complete_ready,
        "visual_ready_percent": round(visual_ready * 100 / total, 1) if total else 0,
        "complete_ready_percent": round(complete_ready * 100 / total, 1) if total else 0,
    }


def _legacy_image_file(path: str) -> Optional[Path]:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    legacy_root = Path(__file__).resolve().parents[2] / "ai_images"
    fallback = legacy_root / os.path.basename(path)
    return fallback if fallback.is_file() else None


def _copy_legacy_image(bundle_id: int, source: Path) -> tuple[str, str, str]:
    content = source.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    suffix = source.suffix.lower()
    if content.startswith(b"\x89PNG"):
        suffix, mime_type = ".png", "image/png"
    elif content.startswith(b"\xff\xd8"):
        suffix, mime_type = ".jpg", "image/jpeg"
    elif content.startswith(b"RIFF"):
        suffix, mime_type = ".webp", "image/webp"
    else:
        raise ValueError("Unsupported legacy image format")
    root = Path(
        os.getenv(
            "AI_MEDIA_DIR",
            str(Path(__file__).resolve().parents[2] / "data" / "ai-media"),
        )
    )
    relative = f"images/legacy-bundle-{bundle_id}-{digest[:12]}{suffix}"
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(content)
        os.replace(temporary, destination)
    return relative, digest, mime_type


def backfill_legacy_memory(db: Session) -> dict:
    """Register old AI columns as v1 without deleting or overwriting them."""

    words = db.query(models.Word).outerjoin(
        models.WordMemoryLink,
        models.WordMemoryLink.word_id == models.Word.id,
    ).filter(
        models.WordMemoryLink.id.is_(None),
    ).all()
    result = {"linked": 0, "created": 0, "queued": 0}
    for word in words:
        has_legacy_resource = bool(
            word.mnemonic or word.image_url or word.image_prompt
        )
        if not has_legacy_resource:
            seed_word_evolution(db, word)
            result["queued"] += 1
            continue

        normalized = MeaningNormalizer.normalize(word.meaning)
        lexeme_key = build_lexeme_key(
            word.word,
            normalized.normalized_pos,
            normalized.primary_meaning,
        )
        bundle = db.query(models.MemoryBundle).filter(
            models.MemoryBundle.lexeme_key == lexeme_key,
            models.MemoryBundle.status == "active",
        ).order_by(models.MemoryBundle.content_version.desc()).first()
        if not bundle:
            latest = db.query(models.MemoryBundle).filter(
                models.MemoryBundle.lexeme_key == lexeme_key,
            ).order_by(models.MemoryBundle.content_version.desc()).first()
            bundle = models.MemoryBundle(
                lexeme_key=lexeme_key,
                word_text=word.word,
                normalized_pos=normalized.normalized_pos,
                primary_meaning=normalized.primary_meaning,
                strategy="legacy",
                memory_anchor=word.mnemonic,
                scene_summary=None,
                image_prompt=word.image_prompt,
                narration_text=normalized.narration_text,
                prompt_version="legacy-v1",
                content_version=(latest.content_version if latest else 0) + 1,
                text_model="legacy",
                status="active",
            )
            db.add(bundle)
            db.flush()
            result["created"] += 1
            if word.image_url:
                source = _legacy_image_file(word.image_url)
                if source:
                    try:
                        relative, digest, mime_type = _copy_legacy_image(
                            bundle.id,
                            source,
                        )
                        db.add(models.MemoryAsset(
                            bundle_id=bundle.id,
                            asset_type="image",
                            file_path=relative,
                            sha256=digest,
                            mime_type=mime_type,
                            version=1,
                            model="legacy",
                            status="ready",
                        ))
                    except (OSError, ValueError):
                        pass
        db.add(models.WordMemoryLink(
            word_id=word.id,
            active_bundle_id=bundle.id,
            status="generating_assets",
        ))
        db.flush()
        seed_word_evolution(db, word)
        result["linked"] += 1
    db.commit()
    return result
