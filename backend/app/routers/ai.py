"""AI 增强 API — 单词语境生成、错题分析、微故事、近义词辨析"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..models import get_db, Word, StudyRecord, User
from ..services.ai import AiService
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

# 简单的任务跟踪 (生产环境应改用 Celery/Redis)
_enrich_tasks: dict = {}


class EnrichError(BaseModel):
    word: str
    correct: str
    user: str
    meaning: Optional[str] = None


class AnalyzeErrorsRequest(BaseModel):
    errors: list[EnrichError]


class StoryRequest(BaseModel):
    words: list[str]


class DistinguishRequest(BaseModel):
    word1: str
    meaning1: str = ""
    word2: str
    meaning2: str = ""


@router.post("/generate-bank-images/{bank_id}")
async def generate_bank_images(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量生成整个词库的视觉词卡 (后台异步执行)"""
    ai = AiService(db)
    if not ai.minimax:
        raise HTTPException(400, "MiniMax API 未配置,请先在设置中配置")

    words = db.query(Word).filter(
        Word.bank_id == bank_id,
        Word.enriched == True,
        Word.image_prompt != None,
        Word.image_prompt != "",
    ).all()
    if not words:
        raise HTTPException(400, "词库没有可生成图片的单词，请先进行文本增强")

    ungenerated = [w for w in words if not w.image_url]
    if not ungenerated:
        return {"message": "所有单词已有视觉词卡", "total": len(words), "success": 0, "failed": 0, "skipped": len(words)}

    task_id = f"bank_images_{bank_id}_{len(_enrich_tasks)}"
    _enrich_tasks[task_id] = {"status": "running", "progress": 0, "total": len(ungenerated), "success": 0, "failed": 0}

    asyncio.create_task(_run_generate_bank_images(task_id, bank_id, db))

    return {"task_id": task_id, "total": len(ungenerated), "message": f"开始生成 {len(ungenerated)} 张视觉词卡"}


async def _run_generate_bank_images(task_id: str, bank_id: int, db: Session):
    """后台执行批量图片生成"""
    try:
        ai = AiService(db)

        def progress(done, total):
            _enrich_tasks[task_id].update({"progress": done, "total": total})

        result = await ai.generate_bank_images(bank_id, progress_callback=progress)
        _enrich_tasks[task_id].update({"status": "done", **result})
    except Exception as e:
        logger.error(f"Generate bank images {bank_id} failed: {e}")
        _enrich_tasks[task_id]["status"] = "error"
        _enrich_tasks[task_id]["error"] = str(e)


@router.post("/enrich-bank/{bank_id}")
async def enrich_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量增强整个词库 (后台异步执行)"""
    ai = AiService(db)
    if not ai.deepseek:
        raise HTTPException(400, "DeepSeek API 未配置,请先在设置中配置")

    words = db.query(Word).filter(Word.bank_id == bank_id).all()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")

    unenriched = [w for w in words if not w.enriched]
    if not unenriched:
        return {"message": "所有单词已完成增强", "total": len(words), "success": len(words), "failed": 0}

    task_id = f"bank_{bank_id}_{len(_enrich_tasks)}"
    _enrich_tasks[task_id] = {"status": "running", "progress": 0, "total": len(unenriched), "success": 0, "failed": 0}

    # 在后台异步运行
    asyncio.create_task(_run_enrich_bank(task_id, bank_id, db))

    return {"task_id": task_id, "total": len(unenriched), "message": f"开始增强 {len(unenriched)} 个单词"}


async def _run_enrich_bank(task_id: str, bank_id: int, db: Session):
    """后台执行批量增强"""
    try:
        ai = AiService(db)

        def progress(done, total):
            _enrich_tasks[task_id].update({"progress": done, "total": total})

        result = await ai.enrich_bank(bank_id, progress_callback=progress)
        _enrich_tasks[task_id].update({"status": "done", **result})
    except Exception as e:
        logger.error(f"Enrich bank {bank_id} failed: {e}")
        _enrich_tasks[task_id]["status"] = "error"
        _enrich_tasks[task_id]["error"] = str(e)


@router.get("/enrich-status/{task_id}")
def enrich_status(task_id: str):
    """查询增强任务进度"""
    task = _enrich_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/enrich-bank/{bank_id}/status")
def enrich_bank_status(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询词库的增强进度"""
    words = db.query(Word).filter(Word.bank_id == bank_id).all()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")
    enriched = sum(1 for w in words if w.enriched)
    return {"total": len(words), "enriched": enriched, "remaining": len(words) - enriched}


@router.post("/enrich-word/{word_id}")
async def enrich_word(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """增强单个单词"""
    ai = AiService(db)
    if not ai.deepseek:
        raise HTTPException(400, "DeepSeek API 未配置")

    ok = await ai.enrich_word(word_id)
    if not ok:
        raise HTTPException(500, "增强失败,请检查 API 配置和日志")

    word = db.query(Word).filter(Word.id == word_id).first()
    return {
        "message": "增强成功",
        "enriched": {
            "example_l1": word.example_l1,
            "example_l2": word.example_l2,
            "mnemonic": word.mnemonic,
            "etymology": word.etymology,
        }
    }


@router.post("/generate-image/{word_id}")
async def generate_image(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为单词生成视觉词卡图片"""
    ai = AiService(db)
    if not ai.minimax:
        raise HTTPException(400, "MiniMax API 未配置")
    if not ai.deepseek:
        raise HTTPException(400, "DeepSeek API 未配置(需先生成 image_prompt)")

    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(404, "单词不存在")

    # 如果没有 image_prompt, 先 enrich
    if not word.image_prompt:
        await ai.enrich_word(word_id)

    path = await ai.generate_word_image(word_id)
    if not path:
        raise HTTPException(500, "图片生成失败")

    return {"image_url": f"/ai-images/{word.word.lower().replace(' ', '_')}.png"}


@router.post("/analyze-errors")
async def analyze_errors(
    req: AnalyzeErrorsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分析错题模式"""
    if not req.errors:
        return {"patterns": [], "summary": "没有错题"}

    ai = AiService(db)
    errors = [{"word": e.word, "user": e.user, "correct": e.correct, "meaning": e.meaning or ""} for e in req.errors]
    return await ai.analyze_errors(errors)


@router.post("/story")
async def generate_story(
    req: StoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成错词微故事"""
    if not req.words:
        raise HTTPException(400, "请提供单词列表")

    ai = AiService(db)
    story = await ai.generate_story(req.words)
    return {"story": story, "word_count": len(req.words)}


@router.post("/distinguish")
async def distinguish_words(
    req: DistinguishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """近义词辨析"""
    if not req.word1 or not req.word2:
        raise HTTPException(400, "请提供两个单词")

    ai = AiService(db)
    result = await ai.distinguish_words(req.word1, req.meaning1, req.word2, req.meaning2)
    return result
