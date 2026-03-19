from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Date, Text
from datetime import datetime
import time

SQLALCHEMY_DATABASE_URL = "sqlite:///./wordmaster.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# 获取本地时间的辅助函数
def get_local_datetime():
    return datetime.fromtimestamp(time.time())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=get_local_datetime)


class WordBank(Base):
    __tablename__ = "word_banks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_local_datetime)


class Word(Base):
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, index=True)
    bank_id = Column(Integer, ForeignKey("word_banks.id"), nullable=False)
    seq_num = Column(Integer, nullable=False)
    word = Column(String, nullable=False)
    phonetic = Column(String)
    meaning = Column(String, nullable=False)


class StudyGroup(Base):
    __tablename__ = "study_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bank_id = Column(Integer, ForeignKey("word_banks.id"), nullable=False)
    name = Column(String, nullable=False)
    start_seq = Column(Integer, nullable=False)
    end_seq = Column(Integer, nullable=False)
    status = Column(String, default="new")
    created_at = Column(DateTime, default=get_local_datetime)
    completed_at = Column(DateTime, nullable=True)


class StudyRecord(Base):
    __tablename__ = "study_records"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    round = Column(Integer, nullable=False)
    correct = Column(Boolean, nullable=False)
    study_type = Column(String, default="new")  # 'new' 或 'review'
    plan_id = Column(Integer, ForeignKey("review_plans.id"), nullable=True)  # 复习计划ID，新学时为null
    studied_at = Column(DateTime, default=datetime.utcnow)


class ReviewPlan(Base):
    __tablename__ = "review_plans"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False)
    review_date = Column(Date, nullable=False)  # 当前计划复习日期（可能已延期）
    original_date = Column(Date, nullable=False)  # 原始计划复习日期
    review_round = Column(Integer, nullable=False)
    status = Column(String, default="pending")  # pending, completed
    postponed_days = Column(Integer, default=0)  # 延期天数
    completed_at = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
