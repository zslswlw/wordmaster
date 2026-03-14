from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date
from typing import List
import random

from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..schemas import ReviewPlanResponse
from ..auth import get_current_user

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/group/{group_id}", response_model=List[dict])
def get_group_reviews(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """根据学习组ID获取该组的复习计划"""
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    
    if not group:
        raise HTTPException(status_code=404, detail="学习组不存在")
    
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.group_id == group_id
    ).order_by(ReviewPlan.review_date).all()
    
    today = date.today()
    
    result = []
    for plan in plans:
        result.append({
            "plan_id": plan.id,
            "group_id": group_id,
            "group_name": group.name,
            "review_round": plan.review_round,
            "review_date": plan.review_date.isoformat(),
            "status": plan.status,
            "is_today": plan.review_date == today,
            "is_overdue": plan.review_date < today,
            "is_future": plan.review_date > today,
            "can_review": plan.review_date <= today and plan.status == "pending"
        })
    
    return result


@router.get("/today", response_model=List[dict])
def get_today_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取今天的复习计划（向后兼容）"""
    today = date.today()
    
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.review_date == today,
        ReviewPlan.status == "pending"
    ).all()
    
    result = []
    for plan in plans:
        group = db.query(StudyGroup).filter(
            StudyGroup.id == plan.group_id,
            StudyGroup.user_id == current_user.id
        ).first()
        
        if group:
            bank = db.query(WordBank).filter(WordBank.id == group.bank_id).first()
            result.append({
                "plan_id": plan.id,
                "group_id": group.id,
                "group_name": group.name,
                "bank_name": bank.name if bank else "Unknown",
                "review_round": plan.review_round,
                "review_date": plan.review_date.isoformat(),
                "start_seq": group.start_seq,
                "end_seq": group.end_seq,
                "status": plan.status,
                "is_today": plan.review_date == today,
                "is_overdue": plan.review_date < today,
                "is_future": plan.review_date > today,
                "can_review": plan.review_date <= today and plan.status == "pending"
            })
    
    return result


@router.get("/all", response_model=List[dict])
def get_all_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有复习计划，按日期分组"""
    today = date.today()
    
    # 获取当前用户的所有学习组
    user_groups = db.query(StudyGroup).filter(
        StudyGroup.user_id == current_user.id
    ).all()
    
    group_ids = [g.id for g in user_groups]
    
    # 获取这些学习组的所有复习计划
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.group_id.in_(group_ids)
    ).order_by(ReviewPlan.review_date.asc(), ReviewPlan.review_round.asc()).all()
    
    result = []
    for plan in plans:
        group = db.query(StudyGroup).filter(StudyGroup.id == plan.group_id).first()
        if group:
            bank = db.query(WordBank).filter(WordBank.id == group.bank_id).first()
            result.append({
                "plan_id": plan.id,
                "group_id": group.id,
                "group_name": group.name,
                "bank_name": bank.name if bank else "Unknown",
                "review_round": plan.review_round,
                "review_date": plan.review_date.isoformat(),
                "start_seq": group.start_seq,
                "end_seq": group.end_seq,
                "status": plan.status,
                "is_today": plan.review_date == today,
                "is_overdue": plan.review_date < today,
                "is_future": plan.review_date > today,
                "can_review": plan.review_date <= today and plan.status == "pending"
            })
    
    return result


@router.post("/start/{plan_id}")
def start_review(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plan = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Review plan not found")
    
    # 检查是否到期
    if plan.review_date > date.today():
        raise HTTPException(status_code=400, detail="复习计划尚未到期")
    
    group = db.query(StudyGroup).filter(
        StudyGroup.id == plan.group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 查询该复习计划已有的记录
    existing_records = db.query(StudyRecord).filter(
        StudyRecord.plan_id == plan_id,
        StudyRecord.study_type == "review"
    ).all()
    
    if existing_records:
        # 获取当前轮次
        current_round = max(r.round for r in existing_records)
        # 获取当前轮次的错误单词ID
        wrong_word_ids = [r.word_id for r in existing_records if not r.correct and r.round == current_round]
        
        if wrong_word_ids:
            # 继续复习：只返回错误单词
            word_ids = wrong_word_ids
        else:
            # 全部正确，返回该组所有单词（可能是新的一轮复习）
            words = db.query(Word).filter(
                Word.bank_id == group.bank_id,
                Word.seq_num >= group.start_seq,
                Word.seq_num <= group.end_seq
            ).all()
            word_ids = [w.id for w in words]
    else:
        # 首次复习：返回该组所有单词
        words = db.query(Word).filter(
            Word.bank_id == group.bank_id,
            Word.seq_num >= group.start_seq,
            Word.seq_num <= group.end_seq
        ).all()
        word_ids = [w.id for w in words]
    
    random.shuffle(word_ids)
    
    return {
        "plan_id": plan_id,
        "group_id": group.id,
        "group_name": group.name,
        "review_round": plan.review_round,
        "total_words": len(word_ids),
        "word_ids": word_ids
    }


@router.post("/complete/{plan_id}")
def complete_review(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plan = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Review plan not found")
    
    # 查询该复习计划当前的最新轮次
    records = db.query(StudyRecord).filter(
        StudyRecord.plan_id == plan_id,
        StudyRecord.study_type == "review"
    ).all()
    
    if not records:
        return {"message": "No records", "next_step": "continue"}
    
    # 获取当前轮次
    current_round = max(r.round for r in records)
    
    # 获取当前轮次的错误单词
    wrong_records = [r for r in records if not r.correct and r.round == current_round]
    wrong_word_ids = [str(r.word_id) for r in wrong_records]
    
    # 如果还有错误单词，说明复习未完成，继续复习
    if wrong_word_ids:
        return {
            "message": f"{len(wrong_word_ids)} words wrong, need to continue",
            "next_step": "continue",
            "wrong_word_ids": ",".join(wrong_word_ids),
            "wrong_count": len(wrong_word_ids)
        }
    
    # 全部正确，标记复习计划为完成
    plan.status = "completed"
    db.commit()
    
    return {"message": "Review completed successfully", "next_step": "completed", "wrong_count": 0}
