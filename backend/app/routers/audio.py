"""
音频管理模块
提供音频同步、状态查询、下载管理等功能
"""

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import requests
import sqlite3
from pathlib import Path
from datetime import datetime

from ..models import get_db, Word
from ..auth import get_current_user

router = APIRouter(prefix="/api/audio", tags=["audio"])

# 音频源（免费）
AUDIO_SOURCES = [
    "https://ssl.gstatic.com/dictionary/static/sounds/oxford/{word}--_us_1.mp3",
    "https://dict.youdao.com/dictvoice?type=2&audio={word}",
]

# 音频存储路径
AUDIO_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "audio"


def get_audio_path(word: str) -> Path:
    """获取单词音频文件的存储路径"""
    word = word.lower().strip()
    first_letter = word[0] if word else 'a'
    target_dir = AUDIO_DIR / first_letter
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{word}.mp3"


def audio_exists(word: str) -> bool:
    """检查单词音频是否存在"""
    return get_audio_path(word).exists()


def download_audio(word: str) -> bool:
    """
    下载单个单词的音频
    返回：是否成功
    """
    word = word.lower().strip()
    if not word:
        return False
    
    target_file = get_audio_path(word)
    
    # 已存在则跳过
    if target_file.exists():
        return True
    
    # 尝试多个源下载
    for source in AUDIO_SOURCES:
        try:
            url = source.format(word=word)
            response = requests.get(url, timeout=10)
            # 检查响应是否有效（文件大小大于1KB）
            if response.status_code == 200 and len(response.content) > 1000:
                with open(target_file, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            continue
    
    return False


@router.post("/sync")
async def sync_audio(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    同步所有单词的音频（后台任务）
    自动下载缺失的音频文件
    """
    # 获取所有唯一单词
    words = db.query(Word.word).distinct().all()
    word_list = [w[0] for w in words if w[0]]
    
    # 后台任务下载音频
    background_tasks.add_task(download_missing_audio_task, word_list)
    
    return {
        "message": "音频同步任务已启动",
        "total_words": len(word_list),
        "status": "processing"
    }


@router.post("/sync-word/{word}")
async def sync_single_word(
    word: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    同步单个单词的音频
    """
    success = download_audio(word)
    
    if success:
        return {
            "word": word,
            "status": "success",
            "path": str(get_audio_path(word))
        }
    else:
        raise HTTPException(status_code=404, detail=f"无法下载单词 '{word}' 的音频")


@router.get("/status")
async def get_audio_status(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取音频同步状态
    返回总单词数、已有音频数、缺失数等统计信息
    """
    words = db.query(Word.word).distinct().all()
    total = len(words)
    
    if total == 0:
        return {
            "total_words": 0,
            "has_audio": 0,
            "missing": 0,
            "coverage": "0%",
            "audio_dir": str(AUDIO_DIR)
        }
    
    # 检查哪些单词有音频
    existing = 0
    missing_words = []
    
    for word_tuple in words:
        word = word_tuple[0]
        if word and audio_exists(word):
            existing += 1
        else:
            missing_words.append(word)
    
    return {
        "total_words": total,
        "has_audio": existing,
        "missing": total - existing,
        "coverage": f"{existing/total*100:.1f}%",
        "audio_dir": str(AUDIO_DIR),
        "missing_sample": missing_words[:10]  # 前10个缺失的单词
    }


@router.get("/check/{word}")
async def check_audio(
    word: str,
    current_user = Depends(get_current_user)
):
    """
    检查单个单词的音频是否存在
    """
    exists = audio_exists(word)
    path = get_audio_path(word) if exists else None
    
    return {
        "word": word,
        "exists": exists,
        "path": str(path) if path else None
    }


@router.get("/missing")
async def get_missing_audio(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    获取缺失音频的单词列表
    """
    words = db.query(Word.word).distinct().all()
    missing = []
    
    for word_tuple in words:
        word = word_tuple[0]
        if word and not audio_exists(word):
            missing.append(word)
            if len(missing) >= limit:
                break
    
    return {
        "missing_count": len(missing),
        "missing_words": missing
    }


def download_missing_audio_task(word_list: List[str]):
    """
    后台任务：下载缺失的音频
    """
    success_count = 0
    failed_count = 0
    
    for word in word_list:
        if audio_exists(word):
            continue
            
        if download_audio(word):
            success_count += 1
        else:
            failed_count += 1
    
    # 可以在这里添加日志记录
    print(f"[Audio Sync] Completed: {success_count} success, {failed_count} failed")


@router.post("/batch-download")
async def batch_download(
    words: List[str],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    批量下载指定单词的音频
    """
    background_tasks.add_task(download_missing_audio_task, words)
    
    return {
        "message": "批量下载任务已启动",
        "word_count": len(words)
    }
