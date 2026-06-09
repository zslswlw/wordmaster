import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List
import random


def _web_image_url(filepath: str) -> str | None:
    """Convert filesystem path to web URL for frontend"""
    if not filepath:
        return None
    filename = os.path.basename(filepath)
    return f"/ai-images/{filename}"
import json

from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..schemas import StudyCheckRequest, StudyCheckResponse, ReviewPlanResponse
from ..auth import get_current_user
from .study_refactored import get_study_words

router = APIRouter(prefix="/api/study", tags=["study"])

EBINGHAUS_INTERVALS = [1, 3, 7, 15, 30]
MASTERY_THRESHOLD = 3  # 连续正确此次数后跳过复习


def _get_consecutive_correct(db: Session, word_id: int, group_id: int) -> int:
    """返回单词在指定学习组中连续正确的次数 (按 studied_at 倒序)"""
    records = (
        db.query(StudyRecord)
        .filter(StudyRecord.word_id == word_id, StudyRecord.group_id == group_id)
        .order_by(StudyRecord.studied_at.desc())
        .all()
    )
    count = 0
    for r in records:
        if r.correct:
            count += 1
        else:
            break
    return count


def _adapt_next_review_interval(db: Session, group_id: int, group: StudyGroup) -> None:
    """自适应调整下一次复习计划的间隔。

    根据全组单词的掌握程度 (连续正确率) 延长下次复习的天数。
    掌握度越高，间隔延长越多 (最多 ×1.5)。
    """
    words = db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq
    ).all()
    if not words:
        return

    # 计算掌握率：连续正确 ≥ MASTERY_THRESHOLD 的单词占比
    mastered = sum(1 for w in words if _get_consecutive_correct(db, w.id, group_id) >= MASTERY_THRESHOLD)
    mastery_rate = mastered / len(words)

    # 低于 60% 不延长；60%-100% 线性映射到 ×1.0-×1.5
    if mastery_rate < 0.6:
        return

    factor = 1.0 + (mastery_rate - 0.6) * 1.25  # 0.6→1.0, 1.0→1.5

    next_plan = (
        db.query(ReviewPlan)
        .filter(
            ReviewPlan.group_id == group_id,
            ReviewPlan.status == "pending"
        )
        .order_by(ReviewPlan.review_date.asc())
        .first()
    )
    if not next_plan:
        return

    # 计算当前间隔 (original_date 到 review_date 的天数)
    current_interval = (next_plan.review_date - next_plan.original_date).days
    if current_interval <= 0:
        return

    new_interval = max(current_interval, int(current_interval * factor))
    extra_days = new_interval - current_interval
    if extra_days <= 0:
        return

    next_plan.review_date = next_plan.review_date + timedelta(days=extra_days)
    next_plan.postponed_days = (next_plan.postponed_days or 0) + extra_days
    db.commit()


@router.post("/start/{group_id}")
def start_study(
    group_id: int,
    is_review: bool = False,
    is_enhance: bool = False,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if not is_review and not is_enhance:
        if group.status == "completed":
            raise HTTPException(status_code=400, detail="Group already completed")
        group.status = "learning"
        db.commit()
    
    words = db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq
    ).all()
    
    word_ids = [w.id for w in words]
    
    # 根据模式选择查询的学习类型
    query_study_type = "review" if is_review else ("enhance" if is_enhance else "new")
    
    # 构建查询 - 复习模式时如果提供了plan_id，则只查询该计划的记录
    records_query = db.query(StudyRecord).filter(
        StudyRecord.group_id == group_id,
        StudyRecord.study_type == query_study_type
    )
    
    # 如果提供了plan_id，只查询该复习计划的记录；否则只查询plan_id为null的记录（避免数据污染）
    if plan_id:
        records_query = records_query.filter(StudyRecord.plan_id == plan_id)
    else:
        records_query = records_query.filter(StudyRecord.plan_id == None)
    
    existing_records = records_query.all()
    
    # 使用统一的学习逻辑
    study_word_ids, current_round, is_completed = get_study_words(
        all_word_ids=word_ids,
        existing_records=existing_records,
        study_type=query_study_type
    )

    # 自适应复习: 跳过已掌握单词 (连续正确 ≥ MASTERY_THRESHOLD)
    skipped_mastered: list[int] = []
    if is_review and study_word_ids:
        to_skip = []
        for wid in study_word_ids:
            if _get_consecutive_correct(db, wid, group_id) >= MASTERY_THRESHOLD:
                to_skip.append(wid)
        if to_skip:
            study_word_ids = [w for w in study_word_ids if w not in to_skip]
            skipped_mastered = to_skip
        # 全部跳过 → 视为完成
        if not study_word_ids:
            is_completed = True

    random.shuffle(study_word_ids) if study_word_ids else None

    return {
        "group_id": group_id,
        "group_name": group.name,
        "total_words": len(study_word_ids),
        "skipped_mastered": len(skipped_mastered),
        "current_round": current_round,
        "word_ids": study_word_ids,
        "is_completed": is_completed
    }


@router.get("/word/{word_id}", response_model=dict)
def get_word(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    return {
        "id": word.id,
        "word": word.word,
        "phonetic": word.phonetic,
        "meaning": word.meaning,
        "example_l1": word.example_l1,
        "example_l2": word.example_l2,
        "example_l3": word.example_l3,
        "mnemonic": word.mnemonic,
        "etymology": word.etymology,
        "word_family": word.word_family,
        "synonyms": word.synonyms,
        "image_url": _web_image_url(word.image_url),
        "image_prompt": word.image_prompt,
        "context_audio": word.context_audio,
        "enriched": word.enriched,
    }


@router.post("/check", response_model=StudyCheckResponse)
def check_answer(
    request: StudyCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 验证学习组是否存在且属于当前用户
    group = db.query(StudyGroup).filter(
        StudyGroup.id == request.group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    word = db.query(Word).filter(Word.id == request.word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    
    correct = request.user_input.strip().lower() == word.word.strip().lower()
    
    try:
        record = StudyRecord(
            group_id=request.group_id,
            word_id=request.word_id,
            round=request.round,
            correct=correct,
            study_type=request.study_type,
            plan_id=request.plan_id
        )
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save record: {str(e)}")
    
    return StudyCheckResponse(
        correct=correct,
        correct_answer=word.word,
        word=word.word
    )


@router.post("/complete/{group_id}")
def complete_round(
    group_id: int,
    is_enhance: bool = False,
    is_review: bool = False,
    study_type: str = None,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 复习模式：像新学一样多轮进行，直到所有单词正确
    if is_review or study_type == "review":
        # 根据参数构建查询
        query = db.query(StudyRecord).filter(StudyRecord.group_id == group_id)
        if study_type:
            query = query.filter(StudyRecord.study_type == study_type)
        # 如果提供了plan_id，只查询该复习计划的记录；否则只查询plan_id为null的记录
        if plan_id:
            query = query.filter(StudyRecord.plan_id == plan_id)
        else:
            query = query.filter(StudyRecord.plan_id == None)
        
        records = query.all()
        
        if not records:
            return {"message": "No records", "next_step": "continue"}
        
        current_round = max(r.round for r in records)
        wrong_count = sum(1 for r in records if not r.correct and r.round == current_round)
        
        if wrong_count == 0:
            # 当前轮次全部正确，复习完成
            if plan_id:
                review_plan = db.query(ReviewPlan).filter(
                    ReviewPlan.id == plan_id,
                    ReviewPlan.group_id == group_id
                ).first()
                if review_plan:
                    review_plan.status = "completed"
                    review_plan.completed_at = datetime.utcnow()
                    db.commit()

                    # 自适应间隔：根据掌握程度延长下次复习间隔
                    _adapt_next_review_interval(db, group_id, group)
            return {"message": "Review completed successfully", "status": "completed", "next_step": "completed"}
        else:
            # 复习还有错误，继续下一轮复习（像新学一样）
            return {"message": f"{wrong_count} words wrong", "next_step": "continue"}
    
    # 强化听写模式
    if is_enhance:
        # 查询强化听写模式的记录
        enhance_records = db.query(StudyRecord).filter(
            StudyRecord.group_id == group_id,
            StudyRecord.study_type == "enhance"
        ).all()
        
        if not enhance_records:
            return {"message": "No records", "next_step": "continue"}
        
        current_round = max(r.round for r in enhance_records)
        wrong_count = sum(1 for r in enhance_records if not r.correct and r.round == current_round)
        
        if wrong_count == 0:
            # 强化学习完成，标记为完成状态
            group.status = "completed"
            group.completed_at = datetime.utcnow()
            
            today = date.today()
            for round_num, interval in enumerate(EBINGHAUS_INTERVALS, 1):
                review_date = today + timedelta(days=interval)
                plan = ReviewPlan(
                    group_id=group_id,
                    review_date=review_date,
                    original_date=review_date,
                    review_round=round_num,
                    postponed_days=0
                )
                db.add(plan)
            
            db.commit()
            return {"message": "Group completed successfully", "status": "completed", "next_step": "completed"}
        else:
            # 强化学习还有错误，需要继续强化
            return {"message": f"{wrong_count} words wrong in enhance round", "next_step": "continue"}
    
    # 新学模式
    # 根据参数构建查询，默认只统计新学模式
    query = db.query(StudyRecord).filter(StudyRecord.group_id == group_id)
    if study_type:
        query = query.filter(StudyRecord.study_type == study_type)
    else:
        query = query.filter(StudyRecord.study_type == "new")
    if plan_id:
        query = query.filter(StudyRecord.plan_id == plan_id)
    
    records = query.all()
    
    if not records:
        return {"message": "No records", "next_step": "continue"}
    
    current_round = max(r.round for r in records)
    wrong_count = sum(1 for r in records if not r.correct and r.round == current_round)
    
    if wrong_count == 0:
        return {"message": "All words correct", "next_step": "enhance"}
    else:
        return {"message": f"{wrong_count} words wrong", "next_step": "continue"}


@router.get("/round/{group_id}")
def get_round_stats(
    group_id: int,
    study_type: str = None,
    plan_id: int = None,
    current_round: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 获取学习组信息
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 获取学习组总单词数
    total_words = db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq
    ).count()
    
    query = db.query(StudyRecord).filter(
        StudyRecord.group_id == group_id
    )
    
    # 如果指定了学习类型，进行过滤；否则默认只统计新学模式
    if study_type:
        query = query.filter(StudyRecord.study_type == study_type)
    else:
        query = query.filter(StudyRecord.study_type == "new")
    
    # 如果指定了复习计划ID，进行过滤；否则只查询plan_id为null的记录
    if plan_id:
        query = query.filter(StudyRecord.plan_id == plan_id)
    else:
        query = query.filter(StudyRecord.plan_id == None)

    records = query.all()
    
    if not records:
        return {
            "current_round": current_round or 1,
            "total_rounds": 0,
            "total_words": total_words,
            "rounds": {}
        }
    
    # 使用字典去重，每个单词每轮只统计一次（取最新记录）
    round_words = {}  # {round: {word_id: (correct, record_id)}}
    for r in records:
        if r.round not in round_words:
            round_words[r.round] = {}
        # 如果同一个单词有多个记录，保留最新的（ID最大的）
        if r.word_id not in round_words[r.round] or r.id > round_words[r.round][r.word_id][1]:
            round_words[r.round][r.word_id] = (r.correct, r.id)
    
    # 统计每轮数据
    rounds = {}
    for round_num, words_data in round_words.items():
        rounds[round_num] = {"correct": 0, "wrong": 0, "total": len(words_data)}
        for correct, _ in words_data.values():
            if correct:
                rounds[round_num]["correct"] += 1
            else:
                rounds[round_num]["wrong"] += 1
    
    # 确定当前轮次
    actual_current_round = current_round or max(rounds.keys())
    current_round_data = rounds.get(actual_current_round, {"correct": 0, "wrong": 0, "total": 0})
    
    # 计算本轮单词数：使用实际统计的单词数（正确+错误）
    current_round_total = current_round_data.get("correct", 0) + current_round_data.get("wrong", 0)
    
    return {
        "current_round": actual_current_round,
        "total_words": total_words,
        "rounds": rounds,
        "current_round_stats": {
            "correct": current_round_data["correct"],
            "wrong": current_round_data["wrong"],
            "total": current_round_total
        }
    }
