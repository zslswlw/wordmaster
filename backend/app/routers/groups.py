from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..models import get_db, User, WordBank, StudyGroup, StudyRecord, ReviewPlan
from ..clock import BusinessClock, get_clock
from ..schemas import StudyGroupCreate, StudyGroupResponse
from ..auth import get_current_user
from ..services.learning_content import prioritize_group_resources

router = APIRouter(prefix="/api/groups", tags=["study_groups"])


@router.get("", response_model=list[StudyGroupResponse])
def get_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    groups = db.query(StudyGroup).filter(
        StudyGroup.user_id == current_user.id
    ).order_by(StudyGroup.created_at.desc()).all()
    
    today = clock.today()
    day_start_utc, day_end_utc = clock.local_day_bounds_utc(today)
    result = []
    for group in groups:
        group_dict = {
            "id": group.id,
            "user_id": group.user_id,
            "bank_id": group.bank_id,
            "name": group.name,
            "start_seq": group.start_seq,
            "end_seq": group.end_seq,
            "status": group.status,
            "created_at": group.created_at,
            "completed_at": group.completed_at,
            "today_review_status": None
        }
        
        # 只有已完成的学习组才检查复习状态
        if group.status == "completed":
            # 逾期计划也应该在学习组列表展示为待复习，避免用户看不到入口
            due_plan = db.query(ReviewPlan).filter(
                ReviewPlan.group_id == group.id,
                ReviewPlan.status == "pending",
                ReviewPlan.review_date <= today
            ).first()

            completed_today = db.query(ReviewPlan).filter(
                ReviewPlan.group_id == group.id,
                ReviewPlan.status == "completed",
                ReviewPlan.completed_at >= day_start_utc,
                ReviewPlan.completed_at < day_end_utc,
            ).first()
            
            if due_plan:
                group_dict["today_review_status"] = "pending"
            elif completed_today:
                group_dict["today_review_status"] = "completed"
            else:
                group_dict["today_review_status"] = "none"
        
        result.append(group_dict)
    
    return result


@router.post("", response_model=StudyGroupResponse)
def create_group(
    group: StudyGroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    bank = db.query(WordBank).filter(
        WordBank.id == group.bank_id
    ).first()
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    
    if group.start_seq < 1 or group.end_seq > bank.word_count or group.start_seq > group.end_seq:
        raise HTTPException(status_code=400, detail="Invalid sequence range")
    
    # 生成有意义的名称：词库名_范围_年月日_时分
    timestamp = clock.now().strftime("%Y%m%d_%H%M")
    name = f"{bank.name}_{group.start_seq}-{group.end_seq}_{timestamp}"
    
    new_group = StudyGroup(
        user_id=current_user.id,
        bank_id=group.bank_id,
        name=name,
        start_seq=group.start_seq,
        end_seq=group.end_seq,
        status="new",
        created_at=clock.utcnow(),
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)
    prioritize_group_resources(db, new_group)
    
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


@router.get("/{group_id}/review-progress")
def get_group_review_progress(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    """
    获取学习组的艾宾浩斯复习进度
    返回5个复习阶段的详细进度信息
    """
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # 艾宾浩斯间隔天数
    EBINGHAUS_INTERVALS = [1, 3, 7, 15, 30]
    
    # 获取该学习组的所有复习计划
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.group_id == group_id
    ).order_by(ReviewPlan.review_round.asc()).all()
    
    today = clock.today()
    
    # 构建5个阶段的进度信息
    progress = []
    for i, interval in enumerate(EBINGHAUS_INTERVALS, 1):
        plan = next((p for p in plans if p.review_round == i), None)
        
        if plan:
            # 计算状态
            if plan.status == "completed":
                status = "completed"
                display_date = plan.completed_at.strftime("%Y-%m-%d") if plan.completed_at else plan.review_date.isoformat()
            elif plan.review_date < today:
                status = "overdue"
                display_date = plan.review_date.isoformat()
            elif plan.review_date == today:
                status = "today"
                display_date = plan.review_date.isoformat()
            else:
                status = "pending"
                display_date = plan.review_date.isoformat()
            
            progress.append({
                "round": i,
                "interval_days": interval,
                "status": status,
                "original_date": (plan.original_date or plan.review_date).isoformat(),
                "review_date": plan.review_date.isoformat(),
                "display_date": display_date,
                "postponed_days": plan.postponed_days,
                "completed_at": plan.completed_at.isoformat() if plan.completed_at else None
            })
        else:
            # 计划尚未创建（学习组未完成学习）
            progress.append({
                "round": i,
                "interval_days": interval,
                "status": "not_created",
                "original_date": None,
                "review_date": None,
                "display_date": None,
                "postponed_days": 0,
                "completed_at": None
            })
    
    # 计算总体进度
    completed_count = sum(1 for p in progress if p["status"] == "completed")
    total_count = len(progress)
    
    return {
        "group_id": group_id,
        "group_name": group.name,
        "group_status": group.status,
        "completed_at": group.completed_at.isoformat() if group.completed_at else None,
        "overall_progress": {
            "completed": completed_count,
            "total": total_count,
            "percentage": round(completed_count / total_count * 100, 1) if total_count > 0 else 0
        },
        "ebinghaus_progress": progress
    }


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
