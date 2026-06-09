"""AI 增强 API — 单词语境生成、错题分析、微故事、近义词辨析"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..models import get_db, Word, StudyRecord, User
from ..services.ai import AiService
from ..services.ai.base import RateLimitError
from ..auth import get_current_user, get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

# 简单的任务跟踪 (生产环境应改用 Celery/Redis)
_enrich_tasks: dict = {}
_pipeline_tasks: dict = {}  # key=bank_id, 跟踪每个词库的完整流水线状态


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
    admin: User = Depends(get_admin_user),
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

    asyncio.create_task(_run_generate_bank_images(task_id, bank_id))

    return {"task_id": task_id, "total": len(ungenerated), "message": f"开始生成 {len(ungenerated)} 张视觉词卡"}


async def _run_generate_bank_images(task_id: str, bank_id: int):
    """后台执行批量图片生成"""
    db = next(get_db())
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
    finally:
        db.close()


@router.post("/enrich-bank/{bank_id}")
async def enrich_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
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
    asyncio.create_task(_run_enrich_bank(task_id, bank_id))

    return {"task_id": task_id, "total": len(unenriched), "message": f"开始增强 {len(unenriched)} 个单词"}


async def _run_enrich_bank(task_id: str, bank_id: int):
    """后台执行批量增强"""
    db = next(get_db())
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
    finally:
        db.close()


@router.post("/generate-context-audio/{bank_id}")
async def generate_context_audio(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """批量生成词库的 AI 语境发音 (MiniMax TTS)"""
    ai = AiService(db)
    if not ai.minimax:
        raise HTTPException(400, "MiniMax API 未配置,请先在设置中配置")

    words = db.query(Word).filter(
        Word.bank_id == bank_id,
        Word.enriched == True,
        Word.example_l2 != None,
        Word.example_l2 != "",
    ).all()
    if not words:
        raise HTTPException(400, "词库没有已增强的单词，请先进行文本增强")

    ungenerated = [w for w in words if not w.context_audio]
    if not ungenerated:
        return {"message": "所有单词已有语境发音", "total": len(words), "success": 0, "failed": 0, "skipped": len(words)}

    task_id = f"context_audio_{bank_id}_{len(_enrich_tasks)}"
    _enrich_tasks[task_id] = {"status": "running", "progress": 0, "total": len(ungenerated), "success": 0, "failed": 0}

    asyncio.create_task(_run_generate_context_audio(task_id, bank_id))

    return {"task_id": task_id, "total": len(ungenerated), "message": f"开始生成 {len(ungenerated)} 个语境发音"}


async def _run_generate_context_audio(task_id: str, bank_id: int):
    """后台执行批量语境发音生成"""
    db = next(get_db())
    try:
        ai = AiService(db)

        def progress(done, total):
            _enrich_tasks[task_id].update({"progress": done, "total": total})

        result = await ai.generate_context_audio_batch(bank_id, progress_callback=progress)
        _enrich_tasks[task_id].update({"status": "done", **result})
    except Exception as e:
        logger.error(f"Context audio generation for bank {bank_id} failed: {e}")
        _enrich_tasks[task_id]["status"] = "error"
        _enrich_tasks[task_id]["error"] = str(e)
    finally:
        db.close()


async def _wait_for_rate_limit(retry_after: float, stage_name: str, bank_id: int):
    """遇限流时记录到 pipeline 状态并等待. UI 可见'限流暂停中'."""
    wait_seconds = max(int(retry_after), 1)
    _pipeline_tasks[bank_id]["status"] = "rate_limited"
    _pipeline_tasks[bank_id]["rate_limit"] = {
        "stage": stage_name,
        "wait_seconds": wait_seconds,
        "resumes_at": __import__("datetime").datetime.now().timestamp() + wait_seconds,
    }
    logger.info(f"Bank {bank_id} {stage_name} rate limited, waiting {wait_seconds}s")
    await asyncio.sleep(wait_seconds)
    # 唤醒后恢复为上一阶段
    if "rate_limit" in _pipeline_tasks[bank_id]:
        del _pipeline_tasks[bank_id]["rate_limit"]


async def _run_enrich_stage(db, ai, bank_id, words, unprocessed) -> dict:
    """Stage 1: 文本增强, 遇 RateLimitError 自动等待后重试"""
    if not unprocessed:
        return {"status": "done", "total": len(words), "success": len(words), "failed": 0}
    _pipeline_tasks[bank_id]["status"] = "enrich"
    _pipeline_tasks[bank_id].update({"progress": 0, "total": len(unprocessed)})
    result = await ai.enrich_bank(bank_id, progress_callback=lambda d, t: _pipeline_tasks[bank_id].update({"progress": d, "total": t}))
    return {"status": "done", **result}


async def _run_images_stage(db, ai, bank_id) -> dict:
    """Stage 2: 图片生成"""
    if not ai.minimax:
        return {"status": "skipped", "reason": "MiniMax not configured"}
    words = db.query(Word).filter(
        Word.bank_id == bank_id,
        Word.enriched == True,
        Word.image_prompt != None,
        Word.image_prompt != "",
    ).all()
    ungenerated = [w for w in words if not w.image_url]
    if not ungenerated:
        return {"status": "done", "total": len(words), "success": len(words), "failed": 0, "skipped": 0}
    _pipeline_tasks[bank_id]["status"] = "images"
    _pipeline_tasks[bank_id].update({"progress": 0, "total": len(ungenerated)})
    result = await ai.generate_bank_images(
        bank_id,
        progress_callback=lambda d, t: _pipeline_tasks[bank_id].update({"progress": d, "total": t}),
    )
    return {"status": "done", **result}


async def _run_audio_stage(db, ai, bank_id) -> dict:
    """Stage 3: 语境发音"""
    if not ai.minimax:
        return {"status": "skipped", "reason": "MiniMax not configured"}
    words = db.query(Word).filter(
        Word.bank_id == bank_id,
        Word.enriched == True,
        Word.example_l2 != None,
        Word.example_l2 != "",
    ).all()
    ungenerated = [w for w in words if not w.context_audio]
    if not ungenerated:
        return {"status": "done", "total": len(words), "success": len(words), "failed": 0, "skipped": 0}
    _pipeline_tasks[bank_id]["status"] = "audio"
    _pipeline_tasks[bank_id].update({"progress": 0, "total": len(ungenerated)})
    result = await ai.generate_context_audio_batch(
        bank_id,
        progress_callback=lambda d, t: _pipeline_tasks[bank_id].update({"progress": d, "total": t}),
    )
    return {"status": "done", **result}


async def _run_full_pipeline(bank_id: int):
    """后台执行完整预处理流水线: 文本增强 → 图片生成 → 语境发音.
    每个 stage 独立 try/except; 遇 RateLimitError 自动等待下个窗口, 不影响其他 stage.
    """
    if bank_id in _pipeline_tasks and _pipeline_tasks[bank_id].get("status") in ("enrich", "images", "audio", "rate_limited"):
        logger.info(f"Pipeline already running for bank {bank_id}, skipping")
        return

    _pipeline_tasks[bank_id] = {"status": "starting"}
    db = next(get_db())
    try:
        ai = AiService(db)

        # Stage 1: 文本增强
        try:
            words = db.query(Word).filter(Word.bank_id == bank_id).all()
            unprocessed = [w for w in words if not w.enriched]
            if not ai.deepseek:
                _pipeline_tasks[bank_id]["enrich"] = {"status": "skipped", "reason": "DeepSeek not configured"}
            else:
                # 循环重试, 遇限流就等待
                while True:
                    try:
                        result = await _run_enrich_stage(db, ai, bank_id, words, unprocessed)
                        _pipeline_tasks[bank_id]["enrich"] = result
                        break
                    except RateLimitError as e:
                        await _wait_for_rate_limit(e.retry_after or 60.0, "enrich", bank_id)
        except Exception as e:
            logger.error(f"Enrich stage failed for bank {bank_id}: {e}")
            _pipeline_tasks[bank_id]["enrich"] = {"status": "error", "error": str(e)}

        # 重建 AiService (新 stage 重新读 provider 配置/flags)
        db.commit()
        ai = AiService(db)

        # Stage 2: 图片生成
        try:
            while True:
                try:
                    result = await _run_images_stage(db, ai, bank_id)
                    _pipeline_tasks[bank_id]["images"] = result
                    break
                except RateLimitError as e:
                    await _wait_for_rate_limit(e.retry_after or 60.0, "images", bank_id)
        except Exception as e:
            logger.error(f"Images stage failed for bank {bank_id}: {e}")
            _pipeline_tasks[bank_id]["images"] = {"status": "error", "error": str(e)}

        db.commit()
        ai = AiService(db)

        # Stage 3: 语境发音
        try:
            while True:
                try:
                    result = await _run_audio_stage(db, ai, bank_id)
                    _pipeline_tasks[bank_id]["audio"] = result
                    break
                except RateLimitError as e:
                    await _wait_for_rate_limit(e.retry_after or 60.0, "audio", bank_id)
        except Exception as e:
            logger.error(f"Audio stage failed for bank {bank_id}: {e}")
            _pipeline_tasks[bank_id]["audio"] = {"status": "error", "error": str(e)}

        _pipeline_tasks[bank_id]["status"] = "done"
        logger.info(f"Pipeline done for bank {bank_id}")
    except Exception as e:
        logger.error(f"Pipeline fatal error for bank {bank_id}: {e}")
        _pipeline_tasks[bank_id]["status"] = "error"
        _pipeline_tasks[bank_id]["error"] = str(e)
    finally:
        db.close()


@router.get("/bank-pipeline/{bank_id}")
def bank_pipeline_status(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询词库的完整预处理流水线状态"""
    state = _pipeline_tasks.get(bank_id)
    if state:
        return state

    # 无内存状态时从 DB 合成
    words = db.query(Word).filter(Word.bank_id == bank_id).all()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")
    enriched = sum(1 for w in words if w.enriched)
    images = sum(1 for w in words if w.image_url)
    audio = sum(1 for w in words if w.context_audio)
    return {
        "status": "done",
        "enrich": {"status": "done", "total": len(words), "success": enriched, "failed": 0},
        "images": {"status": "done", "total": enriched, "success": images, "failed": 0},
        "audio": {"status": "done", "total": enriched, "success": audio, "failed": 0},
    }


@router.post("/reprocess-bank/{bank_id}")
async def reprocess_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """重新运行词库的完整预处理流水线"""
    words = db.query(Word).filter(Word.bank_id == bank_id).all()
    if not words:
        raise HTTPException(404, "词库不存在或无单词")

    # 清除旧状态
    _pipeline_tasks.pop(bank_id, None)

    asyncio.create_task(_run_full_pipeline(bank_id))
    return {"message": "预处理流水线已启动", "bank_id": bank_id}


@router.get("/enrich-status/{task_id}")
def enrich_status(task_id: str, current_user: User = Depends(get_current_user)):
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
    images = sum(1 for w in words if w.image_url)
    audio = sum(1 for w in words if w.context_audio)
    return {
        "total": len(words),
        "enriched": enriched,
        "remaining": len(words) - enriched,
        "images": images,
        "context_audio": audio,
    }


@router.post("/enrich-word/{word_id}")
async def enrich_word(
    word_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
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
    admin: User = Depends(get_admin_user),
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
