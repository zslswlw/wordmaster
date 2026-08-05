from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user
from ..clock import MutableBusinessClock, get_test_clock
from ..models import ReviewPlan, StudyGroup, StudyRecord, User, Word, WordBank, get_db
from .study import EBINGHAUS_INTERVALS


router = APIRouter(prefix="/api/test", tags=["test-lab"])


class ClockSetRequest(BaseModel):
    now: datetime


class ClockAdvanceRequest(BaseModel):
    days: int = Field(default=0, ge=-3650, le=3650)
    minutes: int = Field(default=0, ge=-5256000, le=5256000)


def _clock_payload(clock: MutableBusinessClock) -> dict:
    current = clock.now()
    return {
        "now": current.isoformat(),
        "business_date": current.date().isoformat(),
        "timezone": clock.timezone_name,
    }


@router.get("/clock")
def read_clock(
    clock: MutableBusinessClock = Depends(get_test_clock),
    _current_user: User = Depends(get_current_user),
):
    return _clock_payload(clock)


@router.put("/clock")
def set_clock(
    request: ClockSetRequest,
    clock: MutableBusinessClock = Depends(get_test_clock),
    _current_user: User = Depends(get_current_user),
):
    clock.set(request.now)
    return _clock_payload(clock)


@router.post("/clock/advance")
def advance_clock(
    request: ClockAdvanceRequest,
    clock: MutableBusinessClock = Depends(get_test_clock),
    _current_user: User = Depends(get_current_user),
):
    clock.advance(days=request.days, minutes=request.minutes)
    return _clock_payload(clock)


@router.delete("/clock")
def reset_clock(
    clock: MutableBusinessClock = Depends(get_test_clock),
    _current_user: User = Depends(get_current_user),
):
    clock.reset()
    return _clock_payload(clock)


def _clear_user_data(db: Session, user_id: int) -> None:
    db.query(models.MemoryExposure).filter(
        models.MemoryExposure.user_id == user_id
    ).delete(synchronize_session=False)
    db.query(models.MemoryFeedback).filter(
        models.MemoryFeedback.user_id == user_id
    ).delete(synchronize_session=False)
    group_ids = [
        row[0]
        for row in db.query(StudyGroup.id).filter(StudyGroup.user_id == user_id).all()
    ]
    if group_ids:
        db.query(StudyRecord).filter(StudyRecord.group_id.in_(group_ids)).delete(
            synchronize_session=False
        )
        db.query(ReviewPlan).filter(ReviewPlan.group_id.in_(group_ids)).delete(
            synchronize_session=False
        )
        db.query(StudyGroup).filter(StudyGroup.id.in_(group_ids)).delete(
            synchronize_session=False
        )

    bank_ids = [
        row[0]
        for row in db.query(WordBank.id).filter(WordBank.user_id == user_id).all()
    ]
    if bank_ids:
        word_ids = [
            row[0]
            for row in db.query(Word.id).filter(Word.bank_id.in_(bank_ids)).all()
        ]
        if word_ids:
            db.query(models.WordMemoryLink).filter(
                models.WordMemoryLink.word_id.in_(word_ids)
            ).delete(synchronize_session=False)
        job_ids = db.query(models.AiJob.id).filter(
            models.AiJob.bank_id.in_(bank_ids)
        )
        db.query(models.AiJobAttempt).filter(
            models.AiJobAttempt.job_id.in_(job_ids)
        ).delete(synchronize_session=False)
        db.query(models.AiJob).filter(
            models.AiJob.bank_id.in_(bank_ids)
        ).delete(synchronize_session=False)
        db.query(models.AiLaneState).filter(
            models.AiLaneState.cursor_bank_id.in_(bank_ids)
        ).update({"cursor_bank_id": None}, synchronize_session=False)
        db.query(Word).filter(Word.bank_id.in_(bank_ids)).delete(
            synchronize_session=False
        )
        db.query(WordBank).filter(WordBank.id.in_(bank_ids)).delete(
            synchronize_session=False
        )
    db.commit()


def _seed_bank_and_group(
    db: Session,
    user: User,
    clock: MutableBusinessClock,
    word_count: int = 3,
) -> tuple[WordBank, StudyGroup, list[Word]]:
    fixtures = [
        ("apple", "/apl/", "苹果"),
        ("book", "/buk/", "书"),
        ("cloud", "/klaud/", "云"),
        ("dream", "/dri:m/", "梦想"),
        ("earth", "/erth/", "地球"),
        ("flower", "/flauer/", "花"),
        ("green", "/gri:n/", "绿色"),
        ("house", "/haus/", "房子"),
        ("island", "/ailand/", "岛"),
        ("juice", "/dju:s/", "果汁"),
    ]
    bank = WordBank(
        name=f"{word_count}词测试词库",
        user_id=user.id,
        word_count=word_count,
        created_at=clock.utcnow(),
    )
    db.add(bank)
    db.flush()
    words = [
        Word(
            bank_id=bank.id,
            seq_num=index,
            word=word,
            phonetic=phonetic,
            meaning=meaning,
        )
        for index, (word, phonetic, meaning) in enumerate(fixtures[:word_count], 1)
    ]
    db.add_all(words)
    db.flush()
    group = StudyGroup(
        user_id=user.id,
        bank_id=bank.id,
        name=f"测试组_{clock.now().strftime('%Y%m%d_%H%M')}",
        start_seq=1,
        end_seq=word_count,
        status="new",
        created_at=clock.utcnow(),
    )
    db.add(group)
    db.flush()
    return bank, group, words


def _add_correct_round(
    db: Session,
    group: StudyGroup,
    words: list[Word],
    study_type: str,
    clock: MutableBusinessClock,
) -> None:
    for word in words:
        db.add(StudyRecord(
            group_id=group.id,
            word_id=word.id,
            round=1,
            correct=True,
            study_type=study_type,
            studied_at=clock.utcnow(),
        ))


def _add_review_plans(
    db: Session,
    group: StudyGroup,
    base_date,
) -> None:
    for review_round, interval in enumerate(EBINGHAUS_INTERVALS, 1):
        review_date = base_date + timedelta(days=interval)
        db.add(ReviewPlan(
            group_id=group.id,
            review_date=review_date,
            original_date=review_date,
            review_round=review_round,
            status="pending",
            postponed_days=0,
        ))


@router.post("/scenarios/{scenario}")
def load_scenario(
    scenario: Literal[
        "fresh",
        "partial-round",
        "completed-day0",
        "overdue-backlog",
        "ten-word-review",
    ],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    clock: MutableBusinessClock = Depends(get_test_clock),
):
    _clear_user_data(db, current_user.id)
    word_count = 10 if scenario == "ten-word-review" else 3
    bank, group, words = _seed_bank_and_group(
        db,
        current_user,
        clock,
        word_count=word_count,
    )

    if scenario == "partial-round":
        group.status = "learning"
        db.add_all([
            StudyRecord(
                group_id=group.id,
                word_id=words[0].id,
                round=1,
                correct=True,
                study_type="new",
                studied_at=clock.utcnow(),
            ),
            StudyRecord(
                group_id=group.id,
                word_id=words[1].id,
                round=1,
                correct=False,
                study_type="new",
                studied_at=clock.utcnow(),
            ),
        ])
    elif scenario in {"completed-day0", "overdue-backlog", "ten-word-review"}:
        base_date = clock.today()
        if scenario == "overdue-backlog":
            base_date -= timedelta(days=16)
        elif scenario == "ten-word-review":
            base_date -= timedelta(days=1)
        group.status = "completed"
        group.completed_at = clock.utcnow()
        _add_correct_round(db, group, words, "new", clock)
        _add_correct_round(db, group, words, "enhance", clock)
        _add_review_plans(db, group, base_date)

    db.commit()
    plans = db.query(ReviewPlan).filter(
        ReviewPlan.group_id == group.id
    ).order_by(ReviewPlan.review_round).all()
    return {
        "scenario": scenario,
        "bank_id": bank.id,
        "group_id": group.id,
        "group_status": group.status,
        "word_ids": [word.id for word in words],
        "review_dates": [plan.review_date.isoformat() for plan in plans],
        "clock": _clock_payload(clock),
    }
