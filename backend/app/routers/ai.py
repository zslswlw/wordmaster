"""Compatibility AI APIs routed through the persistent evolution queue."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_admin_user, get_current_user
from ..models import AiJob, User, Word, get_db
from ..services.ai import AiService, InteractiveAiGenerationError
from ..services.learning_content import (
    coverage_for_bank,
    seed_bank_evolution,
    seed_word_evolution,
)


router = APIRouter(prefix="/api/ai", tags=["ai"])


class EnrichError(BaseModel):
    word: str = Field(min_length=1, max_length=128)
    correct: str = Field(min_length=1, max_length=128)
    user: str = Field(max_length=128)
    meaning: Optional[str] = Field(default=None, max_length=500)


class AnalyzeErrorsRequest(BaseModel):
    errors: list[EnrichError] = Field(max_length=50)


class StoryRequest(BaseModel):
    words: list[str] = Field(max_length=20)


class DistinguishRequest(BaseModel):
    word1: str
    meaning1: str = ""
    word2: str
    meaning2: str = ""


def _queue_bank(db: Session, bank_id: int, message: str, priority: int = 30):
    words = db.query(Word).filter(Word.bank_id == bank_id).count()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")
    result = seed_bank_evolution(db, bank_id, priority=priority)
    return {**result, "message": message}


def _raise_interactive_ai_error(exc: InteractiveAiGenerationError) -> None:
    status_code = 502 if exc.code == "invalid_ai_output" else 503
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.public_message},
    ) from exc


@router.post("/generate-bank-images/{bank_id}")
def generate_bank_images(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    return _queue_bank(db, bank_id, "缺失图文资源已加入静默队列")


@router.post("/enrich-bank/{bank_id}")
def enrich_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    return _queue_bank(db, bank_id, "词库整理任务已加入静默队列")


@router.post("/generate-context-audio/{bank_id}")
def generate_context_audio(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    return _queue_bank(db, bank_id, "缺失中文播报已加入静默队列")


@router.post("/reprocess-bank/{bank_id}")
def reprocess_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    return _queue_bank(db, bank_id, "缺失资源已重新排队", priority=20)


@router.get("/bank-pipeline/{bank_id}")
def bank_pipeline_status(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    words = db.query(Word).filter(Word.bank_id == bank_id).count()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")
    coverage = coverage_for_bank(db, bank_id)
    pending = db.query(AiJob).filter(
        AiJob.bank_id == bank_id,
        AiJob.status.in_(["pending", "running"]),
    ).count()
    return {
        "status": "running" if pending else "done",
        "pending_jobs": pending,
        "enrich": {
            "status": "done",
            "total": words,
            "success": coverage["visual_ready"],
            "failed": 0,
        },
        "images": {
            "status": "done",
            "total": words,
            "success": coverage["visual_ready"],
            "failed": 0,
        },
        "audio": {
            "status": "done",
            "total": words,
            "success": coverage["complete_ready"],
            "failed": 0,
        },
    }


@router.get("/enrich-bank/{bank_id}/status")
def enrich_bank_status(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coverage = coverage_for_bank(db, bank_id)
    return {
        "total": coverage["total"],
        "enriched": coverage["visual_ready"],
        "remaining": coverage["total"] - coverage["visual_ready"],
        "images": coverage["visual_ready"],
        "context_audio": coverage["complete_ready"],
    }


@router.get("/enrich-status/{task_id}")
def enrich_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(AiJob).filter(AiJob.id == task_id).first()
    if not job:
        raise HTTPException(404, "任务不存在")
    return {
        "id": job.id,
        "status": job.status,
        "attempts": job.attempts,
        "error": job.last_error_message,
    }


@router.post("/enrich-word/{word_id}")
def enrich_word(
    word_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(404, "单词不存在")
    state = seed_word_evolution(db, word, priority=5)
    db.commit()
    return {"message": "单词已加入静默队列", "state": state}


@router.post("/generate-image/{word_id}")
def generate_image(
    word_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(404, "单词不存在")
    state = seed_word_evolution(db, word, priority=5)
    db.commit()
    return {
        "message": "图片已加入静默队列",
        "state": state,
        "image_url": None,
    }


@router.post("/analyze-errors")
async def analyze_errors(
    req: AnalyzeErrorsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not req.errors:
        return {"patterns": [], "summary": "没有错题"}
    errors = [
        {
            "word": item.word,
            "user": item.user,
            "correct": item.correct,
            "meaning": item.meaning or "",
        }
        for item in req.errors
    ]
    try:
        return await AiService(db).analyze_errors(errors)
    except InteractiveAiGenerationError as exc:
        _raise_interactive_ai_error(exc)


@router.post("/story")
async def generate_story(
    req: StoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    words = list(dict.fromkeys(word.strip() for word in req.words if word.strip()))
    if len(words) < 3:
        raise HTTPException(400, "请至少提供 3 个不同的错词")
    service = AiService(db)
    try:
        story = await service.generate_story(words)
    except InteractiveAiGenerationError as exc:
        _raise_interactive_ai_error(exc)
    return {
        "story": story,
        "word_count": len(words),
        "status": "ready" if story else "disabled",
    }


@router.post("/distinguish")
async def distinguish_words(
    req: DistinguishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not req.word1 or not req.word2:
        raise HTTPException(400, "请提供两个单词")
    return await AiService(db).distinguish_words(
        req.word1,
        req.meaning1,
        req.word2,
        req.meaning2,
    )
