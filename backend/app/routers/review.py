from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..clock import BusinessClock, get_clock
from ..models import ReviewPlan, StudyGroup, User, WordBank, get_db
from .study import complete_round, start_study


router = APIRouter(prefix="/api/review", tags=["review"])


def _user_groups(db: Session, user_id: int) -> list[StudyGroup]:
    return db.query(StudyGroup).filter(StudyGroup.user_id == user_id).all()


def _earliest_pending_by_group(
    db: Session,
    group_ids: list[int],
) -> dict[int, ReviewPlan]:
    if not group_ids:
        return {}
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.group_id.in_(group_ids),
        ReviewPlan.status == "pending",
    ).order_by(
        ReviewPlan.group_id.asc(),
        ReviewPlan.review_round.asc(),
        ReviewPlan.review_date.asc(),
        ReviewPlan.id.asc(),
    ).all()
    earliest: dict[int, ReviewPlan] = {}
    for plan in plans:
        earliest.setdefault(plan.group_id, plan)
    return earliest


def _serialize_plan(
    plan: ReviewPlan,
    group: StudyGroup,
    bank: Optional[WordBank],
    clock: BusinessClock,
    earliest: Optional[ReviewPlan],
) -> dict:
    today = clock.today()
    is_pending = plan.status == "pending"
    is_earliest = earliest is not None and earliest.id == plan.id
    overdue_days = max((today - plan.review_date).days, 0) if is_pending else 0
    return {
        "plan_id": plan.id,
        "group_id": group.id,
        "group_name": group.name,
        "bank_name": bank.name if bank else "Unknown",
        "review_round": plan.review_round,
        "review_date": plan.review_date.isoformat(),
        "original_date": (plan.original_date or plan.review_date).isoformat(),
        "start_seq": group.start_seq,
        "end_seq": group.end_seq,
        "status": plan.status,
        "postponed_days": plan.postponed_days or 0,
        "overdue_days": overdue_days,
        "is_today": plan.review_date == today,
        "is_overdue": overdue_days > 0,
        "is_future": plan.review_date > today,
        "can_review": is_pending and is_earliest and plan.review_date <= today,
        "blocked_by_plan_id": (
            earliest.id if is_pending and earliest is not None and not is_earliest else None
        ),
    }


def _plans_for_groups(
    db: Session,
    groups: list[StudyGroup],
    clock: BusinessClock,
    *,
    due_only: bool = False,
) -> list[dict]:
    if not groups:
        return []
    group_map = {group.id: group for group in groups}
    group_ids = list(group_map)
    query = db.query(ReviewPlan).filter(ReviewPlan.group_id.in_(group_ids))
    if due_only:
        query = query.filter(
            ReviewPlan.status == "pending",
            ReviewPlan.review_date <= clock.today(),
        )
    plans = query.order_by(
        ReviewPlan.review_date.asc(),
        ReviewPlan.review_round.asc(),
        ReviewPlan.id.asc(),
    ).all()
    earliest = _earliest_pending_by_group(db, group_ids)
    bank_ids = {group.bank_id for group in groups}
    banks = {
        bank.id: bank
        for bank in db.query(WordBank).filter(WordBank.id.in_(bank_ids)).all()
    }
    return [
        _serialize_plan(
            plan,
            group_map[plan.group_id],
            banks.get(group_map[plan.group_id].bank_id),
            clock,
            earliest.get(plan.group_id),
        )
        for plan in plans
    ]


@router.get("/group/{group_id}", response_model=List[dict])
def get_group_reviews(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == current_user.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="学习组不存在")
    return _plans_for_groups(db, [group], clock)


@router.get("/today", response_model=List[dict])
def get_today_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    return _plans_for_groups(db, _user_groups(db, current_user.id), clock, due_only=True)


@router.get("/all", response_model=List[dict])
def get_all_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    return _plans_for_groups(db, _user_groups(db, current_user.id), clock)


@router.post("/start/{plan_id}")
def start_review(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    plan = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Review plan not found")
    group = db.query(StudyGroup).filter(
        StudyGroup.id == plan.group_id,
        StudyGroup.user_id == current_user.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return start_study(
        group_id=group.id,
        is_review=True,
        plan_id=plan.id,
        db=db,
        current_user=current_user,
        clock=clock,
    )


@router.post("/complete/{plan_id}")
def complete_review(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    plan = db.query(ReviewPlan).filter(ReviewPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Review plan not found")
    group = db.query(StudyGroup).filter(
        StudyGroup.id == plan.group_id,
        StudyGroup.user_id == current_user.id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return complete_round(
        group_id=group.id,
        is_review=True,
        study_type="review",
        plan_id=plan.id,
        db=db,
        current_user=current_user,
        clock=clock,
    )
