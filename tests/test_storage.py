"""Tests for memory storage (repository CRUD, contradictions, generalization)."""

import uuid
import hashlib
import pytest
from typing import Any

from pgm.config import MemoryCategory, MemoryStatus, EventType
from pgm.db.tables import Ladder, Memory
from pgm.models import ExtractedMemory, ReasonObject

from sqlalchemy import select


class TestMemoryCreate:
    @pytest.mark.asyncio
    async def test_create_memory(self, repository: Any, session: Any, user_id: str) -> None:
        """Create a memory and verify it's stored."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        result = await repository.create_memory(mem, user_id)
        await session.flush()

        assert result.current_text == "Pune"
        assert result.category == "location"
        assert result.slot_key == "city"
        assert result.confidence == 0.9
        assert result.status == MemoryStatus.ACTIVE.value
        assert result.current_level == 0
        assert result.embedding_json is not None

    @pytest.mark.asyncio
    async def test_initial_ladder_rung_created(self, repository: Any, session: Any, user_id: str) -> None:
        """Creating a memory also creates ladder level 0."""
        mem = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="employer",
            value="Infosys",
            confidence=0.85,
        )
        result = await repository.create_memory(mem, user_id)
        await session.flush()

        ladder = await repository.get_ladder(str(result.id))
        assert len(ladder) == 1
        assert ladder[0].level == 0
        assert ladder[0].text == "Infosys"
        assert ladder[0].text_hash == hashlib.sha256(b"Infosys").hexdigest()

    @pytest.mark.asyncio
    async def test_creation_event_logged(self, repository: Any, session: Any, user_id: str) -> None:
        """A 'created' event is logged when a memory is created."""
        mem = ExtractedMemory(
            category=MemoryCategory.PREFERENCES,
            slot_key="food",
            value="biryani",
            confidence=0.95,
        )
        result = await repository.create_memory(mem, user_id)
        await session.flush()

        events = await repository.get_events(str(result.id))
        assert len(events) >= 1
        assert any(e.event_type == EventType.CREATED.value for e in events)

    @pytest.mark.asyncio
    async def test_tier_assigned_from_category(self, repository: Any, session: Any, user_id: str) -> None:
        """Tier is auto-assigned based on category defaults."""
        mem = ExtractedMemory(
            category=MemoryCategory.HEALTH,
            slot_key="condition",
            value="diabetes",
            confidence=0.9,
        )
        result = await repository.create_memory(mem, user_id)
        await session.flush()

        assert result.tier == 3  # S3 for health


class TestContradiction:
    @pytest.mark.asyncio
    async def test_same_slot_supersedes(self, repository: Any, session: Any, user_id: str) -> None:
        """New memory with same slot supersedes the old one."""
        mem1 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        old = await repository.create_memory(mem1, user_id)
        await session.flush()

        mem2 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Mumbai",
            confidence=0.95,
        )
        new = await repository.create_memory(mem2, user_id)
        await session.flush()

        # Refresh old memory
        await session.refresh(old)
        assert old.status == MemoryStatus.SUPERSEDED.value
        assert old.confidence < 0.9  # Lowered
        assert old.superseded_by_id == new.id

    @pytest.mark.asyncio
    async def test_supersession_event_logged(self, repository: Any, session: Any, user_id: str) -> None:
        """A 'superseded' event is logged on the old memory."""
        mem1 = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="employer",
            value="Infosys",
            confidence=0.9,
        )
        old = await repository.create_memory(mem1, user_id)
        await session.flush()

        mem2 = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="employer",
            value="Google",
            confidence=0.95,
        )
        await repository.create_memory(mem2, user_id)
        await session.flush()

        events = await repository.get_events(str(old.id))
        assert any(e.event_type == EventType.SUPERSEDED.value for e in events)

    @pytest.mark.asyncio
    async def test_different_slot_no_conflict(self, repository: Any, session: Any, user_id: str) -> None:
        """Different slot_keys in same category don't conflict."""
        mem1 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        await repository.create_memory(mem1, user_id)
        await session.flush()

        mem2 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="state",
            value="Maharashtra",
            confidence=0.9,
        )
        await repository.create_memory(mem2, user_id)
        await session.flush()

        memories = await repository.get_user_memories(user_id)
        active = [m for m in memories if m.status == MemoryStatus.ACTIVE.value]
        assert len(active) == 2


class TestGeneralization:
    @pytest.mark.asyncio
    async def test_generalize_updates_text_and_level(self, repository: Any, session: Any, user_id: str) -> None:
        """Generalization updates current_text and current_level."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        # Add a level-1 rung manually
        rung = Ladder(
            memory_id=memory.id,
            level=1,
            text="Maharashtra, India",
            population_fraction=0.09,
            info_bits=3.5,
            source="ontology",
        )
        session.add(rung)
        await session.flush()

        # Generalize to level 1
        updated = await repository.generalize_memory(str(memory.id), to_level=1)
        await session.flush()

        assert updated.current_level == 1
        assert updated.current_text == "Maharashtra, India"

    @pytest.mark.asyncio
    async def test_generalize_recomputes_embedding(self, repository: Any, session: Any, user_id: str, mock_embedder: Any) -> None:
        """Embedding is recomputed from generalized text."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        old_embedding = memory.embedding_json.copy()
        await session.flush()

        rung = Ladder(
            memory_id=memory.id, level=1, text="India",
            population_fraction=1.0, info_bits=0.0, source="ontology",
        )
        session.add(rung)
        await session.flush()

        updated = await repository.generalize_memory(str(memory.id), to_level=1)
        await session.flush()

        # Embedding should change (different text → different hash → different mock vector)
        assert updated.embedding_json != old_embedding

    @pytest.mark.asyncio
    async def test_finer_level_texts_kept(self, repository: Any, session: Any, user_id: str) -> None:
        """After generalization, finer level texts are kept for UI visibility."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        rung = Ladder(
            memory_id=memory.id, level=1, text="India",
            population_fraction=1.0, info_bits=0.0, source="ontology",
        )
        session.add(rung)
        await session.flush()

        await repository.generalize_memory(str(memory.id), to_level=1)
        await session.flush()

        # Check that level 0 text is KEPT
        ladder = await repository.get_ladder(str(memory.id))
        level_0 = next(r for r in ladder if r.level == 0)
        assert level_0.text is not None  # Text kept!
        assert level_0.text_hash is not None  # Hash kept for repeat detection

    @pytest.mark.asyncio
    async def test_generalization_event_logged(self, repository: Any, session: Any, user_id: str) -> None:
        """A 'generalized' event is logged."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        rung = Ladder(
            memory_id=memory.id, level=1, text="India",
            population_fraction=1.0, info_bits=0.0, source="ontology",
        )
        session.add(rung)
        await session.flush()

        await repository.generalize_memory(str(memory.id), to_level=1)
        await session.flush()

        events = await repository.get_events(str(memory.id))
        gen_events = [e for e in events if e.event_type == EventType.GENERALIZED.value]
        assert len(gen_events) == 1
        assert gen_events[0].from_level == 0
        assert gen_events[0].to_level == 1


class TestForget:
    @pytest.mark.asyncio
    async def test_forget_clears_text_and_embedding(self, repository: Any, session: Any, user_id: str) -> None:
        """Forgetting clears text, embedding, and ladder texts."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        result = await repository.forget_memory(str(memory.id))
        await session.flush()

        assert result.status == MemoryStatus.FORGOTTEN.value
        assert result.current_text == "[FORGOTTEN]"
        assert result.embedding_json is None

        # Ladder text also cleared
        ladder = await repository.get_ladder(str(memory.id))
        for rung in ladder:
            assert rung.text is None


class TestPin:
    @pytest.mark.asyncio
    async def test_pin_memory(self, repository: Any, session: Any, user_id: str) -> None:
        """Pinning a memory sets the flag and logs an event."""
        mem = ExtractedMemory(
            category=MemoryCategory.PREFERENCES,
            slot_key="food",
            value="biryani",
            confidence=0.95,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        result = await repository.pin_memory(str(memory.id))
        await session.flush()

        assert result.user_pinned is True
        events = await repository.get_events(str(memory.id))
        assert any(e.event_type == EventType.PINNED.value for e in events)


class TestAccessTracking:
    @pytest.mark.asyncio
    async def test_record_access_increments_count(self, repository: Any, session: Any, user_id: str) -> None:
        """Accessing a memory increments access_count."""
        mem = ExtractedMemory(
            category=MemoryCategory.PREFERENCES,
            slot_key="food",
            value="biryani",
            confidence=0.95,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        await repository.record_access(str(memory.id))
        await session.flush()
        await session.refresh(memory)

        assert memory.access_count == 1
        assert memory.last_accessed_at is not None
