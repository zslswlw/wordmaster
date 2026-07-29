import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from .clock import utc_now

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./wordmaster.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    created_at = Column(DateTime, default=utc_now)


class WordBank(Base):
    __tablename__ = "word_banks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # 共享词库，admin 管理
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now)


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
    context_audio = Column(String)            # AI 语境发音路径 (MiniMax TTS)
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
    created_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)


class StudyRecord(Base):
    __tablename__ = "study_records"
    __table_args__ = (
        Index(
            "uq_study_records_no_plan",
            "group_id", "word_id", "round", "study_type",
            unique=True,
            sqlite_where=text("plan_id IS NULL"),
        ),
        Index(
            "uq_study_records_with_plan",
            "plan_id", "word_id", "round",
            unique=True,
            sqlite_where=text("plan_id IS NOT NULL"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    round = Column(Integer, nullable=False)
    correct = Column(Boolean, nullable=False)
    study_type = Column(String, default="new")  # 'new' 或 'review'
    plan_id = Column(Integer, ForeignKey("review_plans.id"), nullable=True)  # 复习计划ID，新学时为null
    user_input = Column(String, nullable=True)
    studied_at = Column(DateTime, default=utc_now)


class ReviewPlan(Base):
    __tablename__ = "review_plans"
    __table_args__ = (
        Index("uq_review_plans_group_round", "group_id", "review_round", unique=True),
    )

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


class FeatureFlags(Base):
    """AI 功能开关 — 全局单行配置，admin 管理"""
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    example_enabled = Column(Boolean, default=True)
    image_enabled = Column(Boolean, default=True)
    mnemonic_enabled = Column(Boolean, default=True)
    error_analysis_enabled = Column(Boolean, default=True)
    story_enabled = Column(Boolean, default=False)
    ai_worker_paused = Column(Boolean, default=False)
    quota_reserve_percent = Column(Integer, default=30)
    feedback_reserve_percent = Column(Integer, default=20)
    priority_bank_id = Column(Integer, ForeignKey("word_banks.id"), nullable=True)


class MemoryBundle(Base):
    """Versioned learning copy. It never replaces immutable Word facts."""

    __tablename__ = "memory_bundles"
    __table_args__ = (
        Index(
            "uq_memory_bundle_version",
            "lexeme_key",
            "content_version",
            unique=True,
        ),
        Index("ix_memory_bundles_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lexeme_key = Column(String(64), nullable=False, index=True)
    word_text = Column(String, nullable=False)
    normalized_pos = Column(String, nullable=True)
    primary_meaning = Column(String, nullable=False)
    strategy = Column(String, nullable=True)
    memory_anchor = Column(String(45), nullable=True)
    scene_summary = Column(String, nullable=True)
    image_prompt = Column(Text, nullable=True)
    narration_text = Column(String(64), nullable=False)
    prompt_version = Column(String, default="memory-v1", nullable=False)
    content_version = Column(Integer, default=1, nullable=False)
    text_model = Column(String, nullable=True)
    quality_scores = Column(Text, nullable=True)
    status = Column(String, default="draft", nullable=False)
    source_bundle_id = Column(
        Integer,
        ForeignKey("memory_bundles.id"),
        nullable=True,
    )
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MemoryAsset(Base):
    """Generated image/audio files belonging to a memory bundle version."""

    __tablename__ = "memory_assets"
    __table_args__ = (
        Index(
            "uq_memory_asset_version",
            "bundle_id",
            "asset_type",
            "version",
            unique=True,
        ),
        Index("ix_memory_assets_bundle_status", "bundle_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    bundle_id = Column(Integer, ForeignKey("memory_bundles.id"), nullable=False)
    asset_type = Column(String, nullable=False)  # image | audio
    file_path = Column(String, nullable=False)
    sha256 = Column(String(64), nullable=False)
    mime_type = Column(String, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    model = Column(String, nullable=True)
    generation_params = Column(Text, nullable=True)
    status = Column(String, default="ready", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class WordMemoryLink(Base):
    """Maps each original word row to the currently enabled reusable bundle."""

    __tablename__ = "word_memory_links"

    id = Column(Integer, primary_key=True, index=True)
    word_id = Column(
        Integer,
        ForeignKey("words.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    active_bundle_id = Column(
        Integer,
        ForeignKey("memory_bundles.id"),
        nullable=True,
    )
    status = Column(String, default="pending", nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MemoryFeedback(Base):
    """User feedback stays attached to the exact exposed resource version."""

    __tablename__ = "memory_feedback"
    __table_args__ = (
        Index("ix_memory_feedback_status_created", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    bundle_id = Column(Integer, ForeignKey("memory_bundles.id"), nullable=True)
    component = Column(String, nullable=False)  # image | memory_anchor
    reason = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    replacement_bundle_id = Column(
        Integer,
        ForeignKey("memory_bundles.id"),
        nullable=True,
    )
    auto_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class MemoryExposure(Base):
    """Records which version was seen before the following spelling result."""

    __tablename__ = "memory_exposures"
    __table_args__ = (
        Index("ix_memory_exposures_word_time", "word_id", "exposed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id"), nullable=False)
    bundle_id = Column(Integer, ForeignKey("memory_bundles.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("study_groups.id"), nullable=True)
    plan_id = Column(Integer, ForeignKey("review_plans.id"), nullable=True)
    study_type = Column(String, nullable=True)
    exposed_at = Column(DateTime, default=utc_now, nullable=False)
    next_result = Column(Boolean, nullable=True)


class AiJob(Base):
    """Persistent, restart-safe AI work queue."""

    __tablename__ = "ai_jobs"
    __table_args__ = (
        Index("ix_ai_jobs_dispatch", "status", "priority", "available_at"),
    )

    id = Column(String(36), primary_key=True)
    kind = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)
    bank_id = Column(Integer, ForeignKey("word_banks.id"), nullable=True)
    priority = Column(Integer, default=100, nullable=False)
    status = Column(String, default="pending", nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    available_at = Column(DateTime, default=utc_now, nullable=False)
    payload = Column(Text, nullable=True)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)
    last_error_code = Column(String, nullable=True)
    last_error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class AiQuotaSnapshot(Base):
    __tablename__ = "ai_quota_snapshots"
    __table_args__ = (
        Index("ix_ai_quota_provider_checked", "provider", "checked_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    remaining_percent = Column(Float, nullable=True)
    status = Column(String, nullable=False)
    reset_at = Column(DateTime, nullable=True)
    raw_payload = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=utc_now, nullable=False)


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
