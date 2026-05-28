import os
import time
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Date, Text

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./wordmaster.db")

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

    # AI 增强字段 (后台预处理填充)
    example_l1 = Column(String)          # 简单例句(含 ____ 填空)
    example_l2 = Column(String)          # 完整例句
    example_l3 = Column(String)          # 高级例句
    image_prompt = Column(String)        # MiniMax 生图 prompt
    image_url = Column(String)           # 本地图片缓存路径
    mnemonic = Column(String)            # 中文记忆锚点
    etymology = Column(String)           # 词根词源拆解
    word_family = Column(String)         # 词族 JSON: ["inspector","inspection"]
    synonyms = Column(String)            # 近义词 JSON
    enriched = Column(Boolean, default=False)  # 是否已完成 AI 增强


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


class ApiConfig(Base):
    """用户 AI API 配置"""
    __tablename__ = "api_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)       # "deepseek" | "minimax"
    api_key_encrypted = Column(String, nullable=False)
    api_base = Column(String, nullable=False)
    text_model = Column(String)
    image_model = Column(String)
    speech_model = Column(String)
    is_enabled = Column(Boolean, default=False)


class WordErrorPattern(Base):
    """AI 分类的拼写错误模式"""
    __tablename__ = "word_error_patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    user_input = Column(String)
    error_type = Column(String)
    count = Column(Integer, default=1)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
