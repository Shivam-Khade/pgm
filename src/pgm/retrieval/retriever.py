"""Memory retriever — hybrid vector + keyword search, level-aware.

Retrieval always returns the CURRENT precision text only (never finer levels).
Updates last_accessed_at and access_count on retrieval.
"""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pgm.config import MemoryCategory, MemoryStatus, Settings, get_settings
from pgm.db.tables import Memory
from pgm.llm.embedder import Embedder
from pgm.models import MemoryRead, RetrievalResult
from pgm.storage.repository import MemoryRepository

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    dot = np.dot(va, vb)
    norm = np.linalg.norm(va) * np.linalg.norm(vb)
    if norm < 1e-9:
        return 0.0
    return float(dot / norm)


class MemoryRetriever:
    """Hybrid retrieval: vector similarity + keyword filtering.

    Level-aware: only returns current_text at the current precision level.
    Automatically updates access stats for retrieved memories.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedder: Embedder,
        repository: MemoryRepository,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._embedder = embedder
        self._repo = repository
        self._settings = settings or get_settings()

    async def search(
        self,
        query: str,
        user_id: str,
        *,
        top_k: int = 10,
        category: MemoryCategory | None = None,
        min_score: float = 0.0,
        update_access: bool = True,
    ) -> list[RetrievalResult]:
        """Search memories for *user_id* matching *query*.

        Uses hybrid scoring:
        - Vector similarity (cosine) on embedding_json
        - Keyword match boost on category + slot_key

        Only returns ACTIVE memories at their current precision level.
        """
        import uuid

        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Get query embedding
        query_embedding = await self._embedder.embed_one(query)

        # Fetch candidate memories
        stmt = select(Memory).where(
            and_(
                Memory.user_id == uid,
                Memory.status == MemoryStatus.ACTIVE.value,
                Memory.embedding_json.isnot(None),
            )
        )
        if category is not None:
            stmt = stmt.where(Memory.category == category.value)

        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())

        if not candidates:
            return []

        # Score each candidate
        scored: list[tuple[Memory, float, str]] = []

        query_lower = query.lower()
        for mem in candidates:
            # Vector similarity
            if mem.embedding_json:
                vec_score = _cosine_similarity(query_embedding, mem.embedding_json)
            else:
                vec_score = 0.0

            # Keyword boost: check if query contains slot_key or category
            keyword_boost = 0.0
            if mem.slot_key.lower() in query_lower:
                keyword_boost += 0.1
            if mem.category.lower() in query_lower:
                keyword_boost += 0.05

            # Text overlap boost
            if mem.current_text and any(
                word in query_lower
                for word in mem.current_text.lower().split()
                if len(word) > 3
            ):
                keyword_boost += 0.05

            combined = vec_score + keyword_boost
            match_type = "hybrid" if keyword_boost > 0 else "vector"

            scored.append((mem, combined, match_type))

        # Sort by score, take top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        # Filter by min_score
        top = [(m, s, t) for m, s, t in top if s >= min_score]

        # Update access stats
        results: list[RetrievalResult] = []
        for mem, score, match_type in top:
            if update_access:
                await self._repo.record_access(str(mem.id))

            results.append(
                RetrievalResult(
                    memory=MemoryRepository.to_read_model(mem),
                    score=score,
                    match_type=match_type,
                )
            )

        return results

    async def search_by_slot(
        self,
        user_id: str,
        category: MemoryCategory,
        slot_key: str,
    ) -> MemoryRead | None:
        """Direct slot lookup (exact match on category + slot_key)."""
        import uuid

        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        stmt = select(Memory).where(
            and_(
                Memory.user_id == uid,
                Memory.category == category.value,
                Memory.slot_key == slot_key,
                Memory.status == MemoryStatus.ACTIVE.value,
            )
        )
        result = await self._session.execute(stmt)
        mem = result.scalar_one_or_none()
        if mem is None:
            return None

        await self._repo.record_access(str(mem.id))
        return MemoryRepository.to_read_model(mem)
