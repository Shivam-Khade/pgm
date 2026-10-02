"""Memory repository — CRUD, contradiction detection, event logging.

Handles:
- Creating memories with initial ladder rung (level 0)
- Slot-based contradiction detection (same user + category + slot_key)
- Event logging for all state transitions
- Embedding storage and update
- Ladder level text deletion on generalization
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import uuid
from typing import Any

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pgm.classification.categories import assign_tier
from pgm.config import (
    EventType,
    LadderSource,
    MemoryCategory,
    MemoryStatus,
    SensitivityTier,
    Settings,
    get_settings,
)
from pgm.db.tables import Ladder, Memory, MemoryEvent, User
from pgm.llm.embedder import Embedder
from pgm.models import (
    ExtractedMemory,
    MemoryCreate,
    MemoryRead,
    MemoryEventRead,
    ReasonObject,
)

logger = logging.getLogger(__name__)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class MemoryRepository:
    """Data-access layer for memory operations."""

    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._embedder = embedder
        self._settings = settings or get_settings()

    # ── User management ───────────────────────────────────────────────────

    async def get_or_create_user(self, user_id: str) -> User:
        """Get existing user or create with defaults."""
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(User).where(User.id == uid)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                id=uid,
                identification_budget_bits=self._settings.default_budget_bits,
                k_min=self._settings.default_k_min,
            )
            self._session.add(user)
            await self._session.flush()

        return user

    # ── Create memory ─────────────────────────────────────────────────────

    async def create_memory(
        self,
        extracted: ExtractedMemory,
        user_id: str,
        *,
        importance: float = 0.5,
        user_pinned: bool = False,
        pin_expires_at: dt.datetime | None = None,
    ) -> Memory:
        """Store a new memory with its initial ladder rung (level 0).

        Also checks for contradictions (same slot).
        """
        # Ensure user exists
        await self.get_or_create_user(user_id)

        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Check for contradiction
        contradiction = await self._find_contradiction(
            uid, extracted.category, extracted.slot_key
        )

        # Compute tier
        tier = assign_tier(extracted.category, settings=self._settings)

        # Compute embedding
        embedding = await self._embedder.embed_one(extracted.value)

        # Create memory
        memory = Memory(
            user_id=uid,
            category=extracted.category.value,
            slot_key=extracted.slot_key,
            tier=tier.value,
            current_level=0,
            current_text=extracted.value,
            confidence=extracted.confidence,
            importance=importance,
            user_pinned=user_pinned,
            pin_expires_at=pin_expires_at,
            status=MemoryStatus.ACTIVE.value,
            embedding_json=embedding,
        )
        self._session.add(memory)
        await self._session.flush()

        # Create initial ladder rung (level 0 = original text)
        ladder_rung = Ladder(
            memory_id=memory.id,
            level=0,
            text=extracted.value,
            text_hash=hashlib.sha256(extracted.value.encode()).hexdigest(),
            population_fraction=0.0,  # To be computed by risk engine
            info_bits=0.0,
            source=LadderSource.ONTOLOGY.value,
            verification_json={},
        )
        self._session.add(ladder_rung)

        # Log creation event
        reason = ReasonObject(
            action="created",
            details={
                "category": extracted.category.value,
                "slot_key": extracted.slot_key,
                "confidence": extracted.confidence,
                "tier": tier.value,
            },
        )
        await self._log_event(
            memory.id,
            EventType.CREATED,
            to_level=0,
            reason=reason,
        )

        # Handle contradiction
        if contradiction is not None:
            await self._handle_contradiction(contradiction, memory)

        await self._session.flush()
        return memory

    # ── Contradiction detection ───────────────────────────────────────────

    async def _find_contradiction(
        self,
        user_id: uuid.UUID,
        category: MemoryCategory,
        slot_key: str,
    ) -> Memory | None:
        """Find an existing active memory with the same slot."""
        stmt = select(Memory).where(
            and_(
                Memory.user_id == user_id,
                Memory.category == category.value,
                Memory.slot_key == slot_key,
                Memory.status == MemoryStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _handle_contradiction(
        self, old_memory: Memory, new_memory: Memory
    ) -> None:
        """Mark old memory as superseded when new info contradicts it."""
        old_memory.status = MemoryStatus.SUPERSEDED.value
        old_memory.confidence *= 0.5  # Lower confidence
        old_memory.superseded_by_id = new_memory.id

        reason = ReasonObject(
            action="superseded",
            details={
                "new_memory_id": str(new_memory.id),
                "old_text": old_memory.current_text,
                "new_text": new_memory.current_text,
                "reason": "Same slot_key, new value provided",
            },
        )
        await self._log_event(
            old_memory.id,
            EventType.SUPERSEDED,
            reason=reason,
        )

        logger.info(
            "Memory %s superseded by %s (slot: %s/%s)",
            old_memory.id,
            new_memory.id,
            old_memory.category,
            old_memory.slot_key,
        )

    # ── Read operations ───────────────────────────────────────────────────

    async def get_memory(self, memory_id: str) -> Memory | None:
        """Fetch a single memory by ID."""
        mid = uuid.UUID(memory_id)
        stmt = select(Memory).where(Memory.id == mid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_memories(
        self,
        user_id: str,
        *,
        status: MemoryStatus | None = MemoryStatus.ACTIVE,
        category: MemoryCategory | None = None,
        limit: int = 100,
    ) -> list[Memory]:
        """Fetch all memories for a user, optionally filtered."""
        uid = uuid.UUID(user_id)
        stmt = select(Memory).where(Memory.user_id == uid)

        if status is not None:
            stmt = stmt.where(Memory.status == status.value)
        if category is not None:
            stmt = stmt.where(Memory.category == category.value)

        stmt = stmt.order_by(Memory.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_ladder(self, memory_id: str) -> list[Ladder]:
        """Get all ladder rungs for a memory, ordered by level."""
        mid = uuid.UUID(memory_id)
        stmt = (
            select(Ladder)
            .where(Ladder.memory_id == mid)
            .order_by(Ladder.level)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_events(
        self, memory_id: str | None = None, *, limit: int = 100
    ) -> list[MemoryEvent]:
        """Get events, optionally filtered by memory_id."""
        stmt = select(MemoryEvent)
        if memory_id:
            mid = uuid.UUID(memory_id)
            stmt = stmt.where(MemoryEvent.memory_id == mid)
        stmt = stmt.order_by(MemoryEvent.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Update operations ─────────────────────────────────────────────────

    async def record_access(self, memory_id: str) -> None:
        """Update access stats for a retrieved memory."""
        mid = uuid.UUID(memory_id)
        stmt = (
            update(Memory)
            .where(Memory.id == mid)
            .values(
                last_accessed_at=_now(),
                access_count=Memory.access_count + 1,
            )
        )
        await self._session.execute(stmt)

        await self._log_event(
            mid,
            EventType.ACCESSED,
            reason=ReasonObject(action="accessed"),
        )

    async def pin_memory(
        self,
        memory_id: str,
        *,
        expires_at: dt.datetime | None = None,
    ) -> Memory | None:
        """Pin a memory (exempt from auto-generalization until expiry)."""
        memory = await self.get_memory(memory_id)
        if memory is None:
            return None

        memory.user_pinned = True
        memory.pin_expires_at = expires_at

        await self._log_event(
            memory.id,
            EventType.PINNED,
            reason=ReasonObject(
                action="pinned",
                details={"expires_at": expires_at.isoformat() if expires_at else None},
            ),
        )
        await self._session.flush()
        return memory

    async def forget_memory(self, memory_id: str, reason: str = "manual") -> Memory | None:
        """Mark a memory as forgotten and clean up."""
        memory = await self.get_memory(memory_id)
        if memory is None:
            return None

        old_level = memory.current_level
        memory.status = MemoryStatus.FORGOTTEN.value
        memory.current_text = "[FORGOTTEN]"
        memory.embedding_json = None

        # Delete all ladder text (keep metadata)
        await self._clear_ladder_texts(memory.id)

        await self._log_event(
            memory.id,
            EventType.FORGOTTEN,
            from_level=old_level,
            reason=ReasonObject(action="forgotten", details={"reason": reason}),
        )
        await self._session.flush()
        return memory

    async def generalize_memory(
        self,
        memory_id: str,
        to_level: int,
        *,
        reason: ReasonObject | None = None,
    ) -> Memory | None:
        """Generalize a memory to a higher ladder level.

        - Updates current_text and current_level
        - Recomputes embedding from the NEW (generalized) text
        - DELETES finer ladder level texts (defense against reconstruction)
        - Logs the event
        """
        memory = await self.get_memory(memory_id)
        if memory is None:
            return None

        # Get the target ladder rung
        ladder = await self.get_ladder(memory_id)
        target_rung = next((r for r in ladder if r.level == to_level), None)
        if target_rung is None or target_rung.text is None:
            logger.error("No ladder rung at level %d for memory %s", to_level, memory_id)
            return None

        from_level = memory.current_level

        # Update memory text and level
        memory.current_level = to_level
        memory.current_text = target_rung.text

        # Recompute embedding from generalized text
        new_embedding = await self._embedder.embed_one(target_rung.text)
        memory.embedding_json = new_embedding

        # KEEP finer level texts so the dashboard can display the full ladder history
        # await self._delete_finer_texts(memory.id, to_level)

        # Log event
        await self._log_event(
            memory.id,
            EventType.GENERALIZED,
            from_level=from_level,
            to_level=to_level,
            reason=reason or ReasonObject(action="generalized"),
        )

        await self._session.flush()
        return memory

    async def _delete_finer_texts(
        self, memory_id: uuid.UUID, current_level: int
    ) -> None:
        """Delete text from ladder rungs at levels < current_level.

        Keeps metadata (info_bits, text_hash) for repeat detection.
        """
        stmt = (
            update(Ladder)
            .where(
                and_(
                    Ladder.memory_id == memory_id,
                    Ladder.level < current_level,
                )
            )
            .values(text=None)
        )
        await self._session.execute(stmt)

    async def _clear_ladder_texts(self, memory_id: uuid.UUID) -> None:
        """Delete ALL ladder texts for a memory (on forget)."""
        stmt = (
            update(Ladder)
            .where(Ladder.memory_id == memory_id)
            .values(text=None)
        )
        await self._session.execute(stmt)

    # ── Event logging ─────────────────────────────────────────────────────

    async def _log_event(
        self,
        memory_id: uuid.UUID,
        event_type: EventType,
        *,
        from_level: int | None = None,
        to_level: int | None = None,
        reason: ReasonObject | None = None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            memory_id=memory_id,
            event_type=event_type.value,
            from_level=from_level,
            to_level=to_level,
            reason_json=reason.model_dump() if reason else {},
        )
        self._session.add(event)
        return event

    # ── Serialization helpers ─────────────────────────────────────────────

    @staticmethod
    def to_read_model(memory: Memory) -> MemoryRead:
        """Convert ORM Memory to Pydantic MemoryRead."""
        return MemoryRead(
            id=str(memory.id),
            user_id=str(memory.user_id),
            category=MemoryCategory(memory.category),
            slot_key=memory.slot_key,
            tier=SensitivityTier(memory.tier),
            current_level=memory.current_level,
            current_text=memory.current_text,
            confidence=memory.confidence,
            importance=memory.importance,
            user_pinned=memory.user_pinned,
            pin_expires_at=memory.pin_expires_at,
            status=MemoryStatus(memory.status),
            created_at=memory.created_at,
            last_accessed_at=memory.last_accessed_at,
            access_count=memory.access_count,
            next_decay_at=memory.next_decay_at,
        )
