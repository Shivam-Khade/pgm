"""Tests for the memory retrieval system."""

import pytest
from typing import Any

from pgm.config import MemoryCategory, MemoryStatus
from pgm.models import ExtractedMemory


class TestRetrieval:
    @pytest.mark.asyncio
    async def test_basic_search(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Search returns relevant memories."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        await repository.create_memory(mem, user_id)
        await session.flush()

        results = await retriever.search("user's city is Pune", user_id, min_score=-10.0, top_k=5)
        assert len(results) >= 1
        assert any("Pune" in r.memory.current_text for r in results)

    @pytest.mark.asyncio
    async def test_returns_current_text_only(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Search returns current_text (the current precision level), not original."""
        from pgm.db.tables import Ladder

        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        # Add a generalized rung and generalize
        rung = Ladder(
            memory_id=memory.id, level=1, text="India",
            population_fraction=1.0, info_bits=0.0, source="ontology",
        )
        session.add(rung)
        await session.flush()
        await repository.generalize_memory(str(memory.id), to_level=1)
        await session.flush()

        results = await retriever.search("India city Pune", user_id, min_score=-10.0, top_k=5)
        texts = [r.memory.current_text for r in results]
        # Should contain "India" (generalized), NOT "Pune" (original)
        assert "India" in texts
        assert "Pune" not in texts

    @pytest.mark.asyncio
    async def test_forgotten_not_returned(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Forgotten memories are not returned by search."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        await repository.forget_memory(str(memory.id))
        await session.flush()

        results = await retriever.search("Pune", user_id, min_score=-10.0, top_k=5)
        assert all(r.memory.status != MemoryStatus.FORGOTTEN for r in results)

    @pytest.mark.asyncio
    async def test_category_filter(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Category filter limits results."""
        mem1 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        mem2 = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="employer",
            value="Infosys",
            confidence=0.85,
        )
        await repository.create_memory(mem1, user_id)
        await repository.create_memory(mem2, user_id)
        await session.flush()

        results = await retriever.search(
            "work",
            user_id,
            top_k=5,
            category=MemoryCategory.EMPLOYMENT,
        )
        for r in results:
            assert r.memory.category == MemoryCategory.EMPLOYMENT

    @pytest.mark.asyncio
    async def test_access_stats_updated(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Retrieval updates access count and timestamp."""
        mem = ExtractedMemory(
            category=MemoryCategory.PREFERENCES,
            slot_key="food",
            value="biryani",
            confidence=0.95,
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()

        await retriever.search("favorite food", user_id, min_score=-10.0, top_k=5)
        await session.flush()
        await session.refresh(memory)

        assert memory.access_count >= 1
        assert memory.last_accessed_at is not None

    @pytest.mark.asyncio
    async def test_slot_lookup(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Direct slot lookup returns exact match."""
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9,
        )
        await repository.create_memory(mem, user_id)
        await session.flush()

        result = await retriever.search_by_slot(
            user_id, MemoryCategory.LOCATION, "city"
        )
        assert result is not None
        assert result.current_text == "Pune"

    @pytest.mark.asyncio
    async def test_empty_store_returns_empty(self, retriever: Any, user_id: str) -> None:
        """Search on an empty store returns no results."""
        results = await retriever.search("anything", user_id, min_score=-10.0, top_k=5)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_scores_are_sorted(self, repository: Any, retriever: Any, session: Any, user_id: str) -> None:
        """Results are sorted by score in descending order."""
        for val in ["Pune", "Mumbai", "Delhi", "Chennai"]:
            mem = ExtractedMemory(
                category=MemoryCategory.LOCATION,
                slot_key=f"city_{val.lower()}",
                value=val,
                confidence=0.9,
            )
            await repository.create_memory(mem, user_id)
        await session.flush()

        results = await retriever.search("Indian city", user_id, min_score=-10.0, top_k=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
