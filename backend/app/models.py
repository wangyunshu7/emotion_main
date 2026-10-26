import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, now


def pk():
    return mapped_column(primary_key=True, default=uuid.uuid4)


def owner():
    return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class Stamp:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Stamp, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(String(30))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    adult_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    terms_version: Mapped[str] = mapped_column(String(32))
    privacy_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    data_version: Mapped[int] = mapped_column(BigInteger, default=1)
    consent_version: Mapped[int] = mapped_column(BigInteger, default=1)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("data_version > 0 AND consent_version > 0"),)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = pk()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ConsentEvent(Base):
    __tablename__ = "consent_events"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    action: Mapped[str] = mapped_column(String(16))
    policy_version: Mapped[str] = mapped_column(String(32))
    provider_key: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(64), default="diary_analysis")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Journal(Stamp, Base):
    __tablename__ = "journals"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    client_request_id: Mapped[uuid.UUID]
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    mood_score: Mapped[int] = mapped_column(Integer)
    emotions: Mapped[list] = mapped_column(JSONB)
    body: Mapped[str] = mapped_column(Text, default="")
    event_tags: Mapped[list] = mapped_column(JSONB, default=list)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id"),
        UniqueConstraint("id", "user_id"),
        CheckConstraint("mood_score BETWEEN 1 AND 5 AND version > 0"),
        CheckConstraint("char_length(body) <= 10000"),
        CheckConstraint(
            "jsonb_array_length(emotions) BETWEEN 1 AND 5 AND jsonb_array_length(event_tags) <= 5"
        ),
        Index("ix_journal_user_time", "user_id", "occurred_at", "id"),
        Index("ix_journal_tags", "event_tags", postgresql_using="gin"),
    )


class EntryAnalysis(Base):
    __tablename__ = "entry_analyses"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    journal_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    journal_version: Mapped[int]
    consent_version: Mapped[int] = mapped_column(BigInteger)
    summary: Mapped[str] = mapped_column(Text)
    reflection_question: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(32), default="entry.v1")
    provider_key: Mapped[str] = mapped_column(String(64))
    model_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["journal_id", "user_id"], ["journals.id", "journals.user_id"], ondelete="CASCADE"
        ),
    )


class Factor(Stamp, Base):
    __tablename__ = "analysis_factors"
    id: Mapped[uuid.UUID] = pk()
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entry_analyses.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(100))
    hypothesis: Mapped[str] = mapped_column(Text)
    evidence_quote: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(16), default="unreviewed")
    user_text: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (
        CheckConstraint("review_status IN ('unreviewed','matches','partial','rejected')"),
    )


class Activity(Stamp, Base):
    __tablename__ = "activities"
    id: Mapped[uuid.UUID] = pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    version: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20))
    duration_minutes: Mapped[int]
    scenes: Mapped[list] = mapped_column(JSONB)
    steps: Mapped[list] = mapped_column(JSONB)
    audio_asset_key: Mapped[str | None] = mapped_column(Text)
    suitability_note: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_note: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 1 AND 60"),
        CheckConstraint("status IN ('draft','published','archived')"),
        CheckConstraint(
            "status <> 'published' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL AND review_due_at IS NOT NULL)"
        ),
    )


class CareSession(Stamp, Base):
    __tablename__ = "care_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="RESTRICT"))
    journal_id: Mapped[uuid.UUID | None]
    client_request_id: Mapped[uuid.UUID]
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    activity_snapshot: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="running")
    version: Mapped[int] = mapped_column(default=1)
    elapsed_seconds: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    before_score: Mapped[int | None]
    after_score: Mapped[int | None]
    helpfulness: Mapped[str | None] = mapped_column(String(20))
    feedback_note: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id"),
        ForeignKeyConstraint(["journal_id", "user_id"], ["journals.id", "journals.user_id"]),
        CheckConstraint(
            "status IN ('running','paused','completed','stopped') AND elapsed_seconds >= 0 AND version > 0"
        ),
        CheckConstraint("before_score IS NULL OR before_score BETWEEN 1 AND 5"),
        CheckConstraint("after_score IS NULL OR after_score BETWEEN 1 AND 5"),
    )


class Job(Stamp, Base):
    __tablename__ = "jobs"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    kind: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[uuid.UUID | None]
    input_meta: Mapped[dict] = mapped_column(JSONB)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    attempt: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=2)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None]
    result_id: Mapped[uuid.UUID | None]
    error_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        Index("ix_jobs_queue", "status", "available_at", "created_at"),
        Index(
            "ix_jobs_active_unique",
            "user_id",
            "kind",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
        ),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')"),
    )


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    start_date: Mapped[date]
    end_date: Mapped[date]
    timezone: Mapped[str] = mapped_column(String(64))
    source_data_version: Mapped[int] = mapped_column(BigInteger)
    consent_version: Mapped[int] = mapped_column(BigInteger)
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    statistics: Mapped[dict] = mapped_column(JSONB)
    insight_eligible: Mapped[bool]
    narrative: Mapped[str | None] = mapped_column(Text)
    observations: Mapped[list] = mapped_column(JSONB, default=list)
    ai_status: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(32), default="review.v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("user_id", "input_fingerprint"),
        CheckConstraint("end_date = start_date + 6"),
    )


class SupportResource(Base):
    __tablename__ = "support_resources"
    id: Mapped[uuid.UUID] = pk()
    region_code: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    contact_text: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    verified_by: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    review_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft")


class RateLimit(Base):
    __tablename__ = "rate_limit_counters"
    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Usage(Stamp, Base):
    __tablename__ = "ai_usage_reservations"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = owner()
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    attempt: Mapped[int]
    budget_date: Mapped[date]
    currency: Mapped[str] = mapped_column(String(8))
    reserved_amount: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    settled_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(16))
    __table_args__ = (UniqueConstraint("job_id", "attempt"),)


class DailyCost(Base):
    __tablename__ = "ai_daily_costs"
    budget_date: Mapped[date] = mapped_column(primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(0))
