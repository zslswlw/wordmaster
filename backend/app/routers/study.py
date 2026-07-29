import os
import random
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..clock import BusinessClock, get_clock
from ..models import (
    MemoryExposure,
    ReviewPlan,
    StudyGroup,
    StudyRecord,
    User,
    Word,
    get_db,
)
from ..schemas import StudyCheckRequest, StudyCheckResponse
from ..services.learning_content import (
    LearningContentResolver,
    prioritize_group_resources,
)
from .study_refactored import (
    VALID_STUDY_TYPES,
    calculate_study_state,
    get_round_state,
    summarize_rounds,
)


router = APIRouter(prefix="/api/study", tags=["study"])
EBINGHAUS_INTERVALS = [1, 3, 7, 15, 30]


def _group_words_query(db: Session, group: StudyGroup):
    return db.query(Word).filter(
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq,
    )


def _group_word_ids(db: Session, group: StudyGroup) -> list[int]:
    return [
        word.id
        for word in _group_words_query(db, group).order_by(Word.seq_num.asc(), Word.id.asc()).all()
    ]


def _records_query(
    db: Session,
    group_id: int,
    study_type: str,
    plan_id: Optional[int] = None,
):
    query = db.query(StudyRecord).filter(
        StudyRecord.group_id == group_id,
        StudyRecord.study_type == study_type,
    )
    if plan_id is None:
        return query.filter(StudyRecord.plan_id.is_(None))
    return query.filter(StudyRecord.plan_id == plan_id)


def _shuffle_word_ids(word_ids: list[int]) -> list[int]:
    result = list(word_ids)
    if os.getenv("ENV") == "test":
        random.Random(int(os.getenv("TEST_RANDOM_SEED", "0"))).shuffle(result)
    else:
        random.shuffle(result)
    return result


def _get_group(db: Session, group_id: int, user_id: int) -> StudyGroup:
    group = db.query(StudyGroup).filter(
        StudyGroup.id == group_id,
        StudyGroup.user_id == user_id,
    ).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


def _get_review_plan(db: Session, group_id: int, plan_id: Optional[int]) -> ReviewPlan:
    if not plan_id:
        raise HTTPException(status_code=400, detail="Review plan is required")
    plan = db.query(ReviewPlan).filter(
        ReviewPlan.id == plan_id,
        ReviewPlan.group_id == group_id,
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Review plan not found")
    return plan


def _earliest_pending_plan(db: Session, group_id: int) -> Optional[ReviewPlan]:
    return db.query(ReviewPlan).filter(
        ReviewPlan.group_id == group_id,
        ReviewPlan.status == "pending",
    ).order_by(
        ReviewPlan.review_round.asc(),
        ReviewPlan.review_date.asc(),
        ReviewPlan.id.asc(),
    ).first()


def _validate_review_available(
    db: Session,
    plan: ReviewPlan,
    clock: BusinessClock,
) -> None:
    if plan.status == "completed":
        raise HTTPException(status_code=409, detail="Review plan already completed")
    earliest = _earliest_pending_plan(db, plan.group_id)
    if earliest and earliest.id != plan.id:
        raise HTTPException(
            status_code=409,
            detail=f"请先完成第{earliest.review_round}轮复习",
        )
    if plan.review_date > clock.today():
        raise HTTPException(status_code=400, detail="复习计划尚未到期")


def _resolve_mode(
    *,
    is_review: bool = False,
    is_enhance: bool = False,
    study_type: Optional[str] = None,
) -> str:
    requested = [is_review, is_enhance]
    if sum(bool(value) for value in requested) > 1:
        raise HTTPException(status_code=400, detail="Study mode is invalid")
    inferred = "review" if is_review else ("enhance" if is_enhance else "new")
    mode = study_type or inferred
    if mode not in VALID_STUDY_TYPES:
        raise HTTPException(status_code=400, detail="Study mode is invalid")
    if study_type and (is_review or is_enhance) and mode != inferred:
        raise HTTPException(status_code=400, detail="Study mode parameters conflict")
    return mode


def _create_review_plans(
    db: Session,
    group_id: int,
    base_date,
) -> None:
    existing_rounds = {
        plan.review_round
        for plan in db.query(ReviewPlan).filter(ReviewPlan.group_id == group_id).all()
    }
    for review_round, interval in enumerate(EBINGHAUS_INTERVALS, 1):
        if review_round in existing_rounds:
            continue
        review_date = base_date + timedelta(days=interval)
        db.add(ReviewPlan(
            group_id=group_id,
            review_date=review_date,
            original_date=review_date,
            review_round=review_round,
            status="pending",
            postponed_days=0,
        ))


def _validate_enhance_unlocked(
    db: Session,
    group: StudyGroup,
    all_word_ids: list[int],
) -> None:
    new_records = _records_query(db, group.id, "new").all()
    if not calculate_study_state(all_word_ids, new_records).phase_complete:
        raise HTTPException(status_code=409, detail="请先完成新学阶段")


@router.post("/start/{group_id}")
def start_study(
    group_id: int,
    is_review: bool = False,
    is_enhance: bool = False,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    mode = _resolve_mode(is_review=is_review, is_enhance=is_enhance)
    group = _get_group(db, group_id, current_user.id)
    review_plan = None

    if mode == "review":
        review_plan = _get_review_plan(db, group_id, plan_id)
        if review_plan.status == "completed":
            return {
                "group_id": group.id,
                "group_name": group.name,
                "total_words": 0,
                "current_round": review_plan.review_round,
                "word_ids": [],
                "is_completed": True,
            }
        _validate_review_available(db, review_plan, clock)
    elif plan_id is not None:
        raise HTTPException(status_code=400, detail="Plan is only valid for review mode")

    if mode == "new":
        if group.status == "completed":
            raise HTTPException(status_code=400, detail="Group already completed")
        if group.status != "learning":
            group.status = "learning"
            db.commit()

    prioritize_group_resources(db, group)
    all_word_ids = _group_word_ids(db, group)
    if not all_word_ids:
        raise HTTPException(status_code=400, detail="Study group contains no words")

    if mode == "enhance":
        _validate_enhance_unlocked(db, group, all_word_ids)

    records = _records_query(db, group_id, mode, plan_id if mode == "review" else None).all()
    state = calculate_study_state(all_word_ids, records)
    remaining = _shuffle_word_ids(state.remaining_word_ids)

    return {
        "group_id": group.id,
        "group_name": group.name,
        "total_words": len(remaining),
        "current_round": state.current_round,
        "word_ids": remaining,
        "is_completed": state.phase_complete,
    }


@router.get("/word/{word_id}", response_model=dict)
def get_word(
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    word = db.query(Word).filter(Word.id == word_id).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")
    content = LearningContentResolver(db).resolve(word)
    return {
        "id": word.id,
        "word": word.word,
        "phonetic": word.phonetic,
        "meaning": word.meaning,
        "example_l1": word.example_l1,
        "example_l2": word.example_l2,
        "example_l3": word.example_l3,
        "mnemonic": content["memory_anchor"],
        "etymology": word.etymology,
        "word_family": word.word_family,
        "synonyms": word.synonyms,
        "image_url": content["image_url"],
        "image_prompt": word.image_prompt,
        "context_audio": content["narration_audio_url"],
        "enriched": word.enriched,
        "learning_content": content,
    }


def _existing_answer(
    db: Session,
    request: StudyCheckRequest,
) -> Optional[StudyRecord]:
    query = db.query(StudyRecord).filter(
        StudyRecord.group_id == request.group_id,
        StudyRecord.word_id == request.word_id,
        StudyRecord.round == request.round,
        StudyRecord.study_type == request.study_type,
    )
    if request.plan_id is None:
        query = query.filter(StudyRecord.plan_id.is_(None))
    else:
        query = query.filter(StudyRecord.plan_id == request.plan_id)
    return query.order_by(StudyRecord.id.desc()).first()


@router.post("/check", response_model=StudyCheckResponse)
def check_answer(
    request: StudyCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    group = _get_group(db, request.group_id, current_user.id)
    word = db.query(Word).filter(
        Word.id == request.word_id,
        Word.bank_id == group.bank_id,
        Word.seq_num >= group.start_seq,
        Word.seq_num <= group.end_seq,
    ).first()
    if not word:
        raise HTTPException(status_code=404, detail="Word not found in group")

    review_plan = None
    if request.study_type == "review":
        review_plan = _get_review_plan(db, request.group_id, request.plan_id)
    elif request.plan_id is not None:
        raise HTTPException(status_code=400, detail="Plan is only valid for review mode")

    existing = _existing_answer(db, request)
    if existing:
        return StudyCheckResponse(
            correct=existing.correct,
            correct_answer=word.word,
            word=word.word,
        )

    if request.study_type == "review":
        _validate_review_available(db, review_plan, clock)
    elif request.study_type == "new" and group.status == "completed":
        raise HTTPException(status_code=409, detail="Group already completed")

    all_word_ids = _group_word_ids(db, group)
    if request.study_type == "enhance":
        _validate_enhance_unlocked(db, group, all_word_ids)
    records = _records_query(
        db,
        request.group_id,
        request.study_type,
        request.plan_id if request.study_type == "review" else None,
    ).all()
    state = calculate_study_state(all_word_ids, records)
    if state.phase_complete:
        raise HTTPException(status_code=409, detail="Study phase already completed")
    if request.round != state.current_round:
        raise HTTPException(status_code=409, detail=f"Current round is {state.current_round}")
    if request.word_id not in state.remaining_word_ids:
        raise HTTPException(status_code=409, detail="Word is not pending in the current round")

    correct = request.user_input.strip().lower() == word.word.strip().lower()
    record = StudyRecord(
        group_id=request.group_id,
        word_id=request.word_id,
        round=request.round,
        correct=correct,
        study_type=request.study_type,
        plan_id=request.plan_id,
        user_input=request.user_input,
        studied_at=clock.utcnow(),
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = _existing_answer(db, request)
        if not existing:
            raise HTTPException(status_code=409, detail="Answer was submitted concurrently")
        correct = existing.correct

    exposure = db.query(MemoryExposure).filter(
        MemoryExposure.user_id == current_user.id,
        MemoryExposure.word_id == request.word_id,
        MemoryExposure.next_result.is_(None),
    ).order_by(MemoryExposure.exposed_at.desc()).first()
    if exposure:
        exposure.next_result = correct
        db.commit()

    return StudyCheckResponse(correct=correct, correct_answer=word.word, word=word.word)


@router.post("/complete/{group_id}")
def complete_round(
    group_id: int,
    is_enhance: bool = False,
    is_review: bool = False,
    study_type: str = None,
    plan_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: BusinessClock = Depends(get_clock),
):
    mode = _resolve_mode(
        is_review=is_review,
        is_enhance=is_enhance,
        study_type=study_type,
    )
    group = _get_group(db, group_id, current_user.id)
    review_plan = None

    if mode == "review":
        review_plan = _get_review_plan(db, group_id, plan_id)
        if review_plan.status == "completed":
            return {
                "message": "Review completed successfully",
                "status": "completed",
                "next_step": "completed",
            }
        _validate_review_available(db, review_plan, clock)
    elif plan_id is not None:
        raise HTTPException(status_code=400, detail="Plan is only valid for review mode")

    all_word_ids = _group_word_ids(db, group)
    if not all_word_ids:
        raise HTTPException(status_code=400, detail="Study group contains no words")
    if mode == "enhance":
        _validate_enhance_unlocked(db, group, all_word_ids)
    records = _records_query(db, group_id, mode, plan_id if mode == "review" else None).all()
    state = calculate_study_state(all_word_ids, records)
    if not state.phase_complete:
        return {
            "message": f"{len(state.remaining_word_ids)} words remaining",
            "next_step": "continue",
            "remaining_count": len(state.remaining_word_ids),
            "current_round": state.current_round,
        }

    if mode == "new":
        return {"message": "All words correct", "next_step": "enhance"}

    if mode == "enhance":
        if group.status != "completed":
            group.status = "completed"
            group.completed_at = clock.utcnow()
        _create_review_plans(db, group_id, clock.today())
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            _create_review_plans(db, group_id, clock.today())
            db.commit()
        return {
            "message": "Group completed successfully",
            "status": "completed",
            "next_step": "completed",
        }

    review_plan.status = "completed"
    if review_plan.completed_at is None:
        review_plan.completed_at = clock.utcnow()
    db.commit()
    return {
        "message": "Review completed successfully",
        "status": "completed",
        "next_step": "completed",
    }


@router.get("/round/{group_id}")
def get_round_stats(
    group_id: int,
    study_type: str = None,
    plan_id: int = None,
    current_round: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mode = _resolve_mode(study_type=study_type)
    group = _get_group(db, group_id, current_user.id)
    if mode == "review":
        _get_review_plan(db, group_id, plan_id)
    elif plan_id is not None:
        raise HTTPException(status_code=400, detail="Plan is only valid for review mode")

    all_word_ids = _group_word_ids(db, group)
    records = _records_query(db, group_id, mode, plan_id if mode == "review" else None).all()
    state = calculate_study_state(all_word_ids, records)
    rounds = summarize_rounds(all_word_ids, records)
    selected_round = current_round or state.current_round
    selected_state = get_round_state(all_word_ids, records, selected_round)
    selected = rounds.get(selected_round, {
        "correct": 0,
        "wrong": 0,
        "total": 0,
        "expected": len(selected_state.target_word_ids) if selected_state else 0,
        "remaining": len(selected_state.remaining_word_ids) if selected_state else 0,
    })

    return {
        "current_round": selected_round,
        "total_rounds": len(rounds),
        "total_words": len(all_word_ids),
        "rounds": rounds,
        "is_completed": state.phase_complete,
        "current_round_stats": selected,
    }
