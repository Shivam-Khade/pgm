"""SQLAlchemy 2 ORM models for PGM tables."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Boolean,
    Enum as SAEnum,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from pgm.config import EventType, LadderSource, MemoryCategory, MemoryStatus, SensitivityTier


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    """Shared base for all ORM models."""
    pass


# ── Users ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    identification_budget_bits: Mapped[float] = mapped_column(Float, default=20.0)
    k_min: Mapped[int] = mapped_column(Integer, default=100)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)

    memories: Mapped[list[Memory]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ── Memories ──────────────────────────────────────────────────────────────────


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    slot_key: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=0)
    current_level: Mapped[int] = mapped_column(Integer, default=0)
    current_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    user_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    pin_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=MemoryStatus.ACTIVE.value)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_accessed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    next_decay_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Embedding stored as JSON array (fallback when pgvector not available)
    # When pgvector is installed, a migration adds a vector column.
    embedding_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="memories")
    ladder_rungs: Mapped[list[Ladder]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", order_by="Ladder.level"
    )
    events: Mapped[list[MemoryEvent]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", order_by="MemoryEvent.created_at"
    )

    __table_args__ = (
        Index("ix_memories_user_category", "user_id", "category"),
        Index("ix_memories_user_slot", "user_id", "category", "slot_key"),
        Index("ix_memories_status", "status"),
    )


# ── Ladders ───────────────────────────────────────────────────────────────────


class Ladder(Base):
    __tablename__ = "ladders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    population_fraction: Mapped[float] = mapped_column(Float, default=0.0)
    info_bits: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(20), default=LadderSource.LLM.value)
    verification_json: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memory: Mapped[Memory] = relationship(back_populates="ladder_rungs")

    __table_args__ = (
        Index("ix_ladders_memory_level", "memory_id", "level", unique=True),
    )


# ── Memory Events ─────────────────────────────────────────────────────────────


class MemoryEvent(Base):
    __tablename__ = "memory_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    memory: Mapped[Memory] = relationship(back_populates="events")


# ── Risk Snapshots ────────────────────────────────────────────────────────────


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    k_hat: Mapped[float] = mapped_column(Float, default=0.0)
    r_agg_bits: Mapped[float] = mapped_column(Float, default=0.0)
    quasi_identifiers_json: Mapped[dict] = mapped_column(JSON, default=dict)


# ── Eval Runs ─────────────────────────────────────────────────────────────────


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    results_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
