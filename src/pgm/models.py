"""Pydantic v2 models shared across PGM modules."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field

from pgm.config import EventType, LadderSource, MemoryCategory, MemoryStatus, SensitivityTier


# ── Extraction ────────────────────────────────────────────────────────────────


class ExtractedMemory(BaseModel):
    """A single memory extracted from a dialogue turn."""

    category: MemoryCategory
    slot_key: str = Field(..., description="Attribute key, e.g. 'city', 'employer'")
    value: str = Field(..., description="The extracted value text")
    confidence: float = Field(ge=0.0, le=1.0, description="LLM-estimated confidence")


class ExtractionResult(BaseModel):
    """Output of the extraction pipeline for one message."""

    memories: list[ExtractedMemory] = Field(default_factory=list)
    redacted_secrets: list[str] = Field(
        default_factory=list,
        description="Descriptions of redacted secrets (not the secrets themselves)",
    )
    original_text: str = ""
    cleaned_text: str = ""


# ── Secret Gate ───────────────────────────────────────────────────────────────


class SecretDetection(BaseModel):
    """A single secret detected by the gate."""

    pattern_name: str
    matched_text_hash: str = Field(description="SHA-256 hash of matched text (never store raw)")
    start: int
    end: int
    detection_method: str = Field(description="'regex', 'entropy', or 'llm'")


class SecretGateResult(BaseModel):
    """Output of the secret gate."""

    contains_secrets: bool = False
    detections: list[SecretDetection] = Field(default_factory=list)
    cleaned_text: str = ""
    original_text: str = ""


# ── Memory CRUD ───────────────────────────────────────────────────────────────


class MemoryCreate(BaseModel):
    """Input for creating a new memory."""

    user_id: str
    category: MemoryCategory
    slot_key: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    user_pinned: bool = False
    pin_expires_at: dt.datetime | None = None


class MemoryRead(BaseModel):
    """Serialized memory for API responses."""

    id: str
    user_id: str
    category: MemoryCategory
    slot_key: str
    tier: SensitivityTier
    current_level: int
    current_text: str
    confidence: float
    importance: float
    user_pinned: bool
    pin_expires_at: dt.datetime | None
    status: MemoryStatus
    created_at: dt.datetime
    last_accessed_at: dt.datetime | None
    access_count: int
    next_decay_at: dt.datetime | None

    model_config = {"from_attributes": True}


# ── Ladder ────────────────────────────────────────────────────────────────────


class LadderRung(BaseModel):
    """A single rung in a generalization ladder."""

    level: int = Field(ge=0)
    text: str
    population_fraction: float = Field(ge=0.0, le=1.0)
    info_bits: float = Field(ge=0.0)
    source: LadderSource
    verification_json: dict[str, Any] = Field(default_factory=dict)
    verified_at: dt.datetime | None = None


# ── Events ────────────────────────────────────────────────────────────────────


class MemoryEventRead(BaseModel):
    """Serialized memory event for API responses."""

    id: str
    memory_id: str
    event_type: EventType
    from_level: int | None
    to_level: int | None
    reason_json: dict[str, Any]
    created_at: dt.datetime

    model_config = {"from_attributes": True}


# ── Reason Object ─────────────────────────────────────────────────────────────


class ReasonObject(BaseModel):
    """Machine-readable explanation of a decision."""

    action: str
    binding_constraint: str | None = None
    utilities: dict[str, float] = Field(default_factory=dict)
    risks: dict[str, float] = Field(default_factory=dict)
    alternatives_rejected: list[dict[str, Any]] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


# ── Retrieval ─────────────────────────────────────────────────────────────────


class RetrievalResult(BaseModel):
    """A single retrieval hit."""

    memory: MemoryRead
    score: float = Field(description="Similarity score")
    match_type: str = Field(description="'vector', 'keyword', or 'hybrid'")


# ── Risk ──────────────────────────────────────────────────────────────────────


class RiskSnapshot(BaseModel):
    """Aggregate risk snapshot."""

    user_id: str
    k_hat: float
    r_agg_bits: float
    quasi_identifiers: list[dict[str, Any]]
    created_at: dt.datetime

    model_config = {"from_attributes": True}
