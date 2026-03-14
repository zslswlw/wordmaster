from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
import random

from ..models import get_db, User, WordBank, Word, StudyGroup, StudyRecord, ReviewPlan
from ..schemas import (
    StudyGroupCreate, StudyGroupResponse, 
    StudyCheckRequest, StudyCheckResponse,
    ReviewPlanResponse
)
from ..auth import get_current_user

router = APIRouter(prefix="/api/groups", tags=["study_groups"])


@router.get("", response_model=list[StudyGroupResponse])
def get_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(StudyGroup).filter(
        StudyGroup.user_id == current_user.id
    ).order_by(StudyGroup.created_at.desc()).all()


@router.post("", response_model=StudyGroupResponse)
def create_group(
    group: StudyGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    bank = db.query(WordBank).filter(
        WordBank.id == group.bank_id,
        WordBank.user_id == current_user.id
    ).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    if group.start_seq < 1 or group.end_seq > bank.word_count or group.start_seq > group.end_seq:
        raise HTTPException(status_code=400, detail="Invalid sequence range")
    
    # 生成有意义的名称：词库名_范围_年月日_时分
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    name = f"{bank.name}_{group.start_seq}-{group.end_seq}_{timestamp}"
    
    new_group = StudyGroup(
        user_id=current_user.id,
        bank_id=group.bank_id,
        name=name,
        start_seq=group.start_seq,
        end_seq=group.end_seq,
        status="new"
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    
    return new_group


@router.get("/{group_id}", response_model=StudyGroupResponse)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除学习组，同时级联删除相关的学习计划和学习记录"""
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 删除相关的学习计划
    db.query(ReviewPlan).filter(ReviewPlan.group_id == group_id).delete()
    
    # 删除相关的学习记录
    db.query(StudyRecord).filter(StudyRecord.group_id == group_id).delete()
    
    # 删除学习组
    db.delete(group)
    db.commit()
    
    return {"message": "学习组已删除"}
