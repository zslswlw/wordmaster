from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class WordBankCreate(BaseModel):
    name: str


class WordBankResponse(BaseModel):
    id: int
    name: str
    user_id: int
    word_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class WordResponse(BaseModel):
    id: int
    seq_num: int
    word: str
    phonetic: Optional[str]
    meaning: str

    class Config:
        from_attributes = True


class StudyGroupCreate(BaseModel):
    bank_id: int
    start_seq: int
    end_seq: int


class StudyGroupResponse(BaseModel):
    id: int
    user_id: int
    bank_id: int
    name: str
    start_seq: int
    end_seq: int
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    today_review_status: Optional[str] = None  # 'completed', 'pending', 'none'

    class Config:
        from_attributes = True


class StudyCheckRequest(BaseModel):
    group_id: int
    word_id: int
    user_input: str
    round: int
    study_type: str = "new"  # 'new' 或 'review'
    plan_id: Optional[int] = None  # 复习计划ID


class StudyCheckResponse(BaseModel):
    correct: bool
    correct_answer: str
    word: str


class ReviewPlanResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    review_date: date
    review_round: int
    status: str

    class Config:
        from_attributes = True
