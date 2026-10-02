"""Shared test fixtures for PGM.

All async fixtures are function-scoped to avoid cross-test event loop issues
with asyncpg on Windows. Schema is created/dropped per test via metadata ops.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)

from pgm.config import Settings, MemoryCategory
from pgm.db.tables import Base
from pgm.llm import MockLLMClient
from pgm.llm.embedder import MockEmbedder
from pgm.storage.repository import MemoryRepository
from pgm.retrieval.retriever import MemoryRetriever
from pgm.models import ExtractedMemory


# ── Test settings ─────────────────────────────────────────────────────────────

TEST_DB_URL = "postgresql+asyncpg://postgres:Shivam10%40162006@localhost:5432/pgm"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings pointing at the test database."""
    return Settings(
        database_url=TEST_DB_URL,
        llm_provider="mock",
        embedder_provider="mock",
        embedding_dim=64,
        _env_file=None,
    )


# ── Database ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test engine per test function and set up tables."""
    eng = create_async_engine(TEST_DB_URL, echo=False, pool_size=1, max_overflow=0)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        # Truncate all tables instead of drop to avoid schema recreation overhead
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a session for each test."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


# ── Mock services ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm() -> MockLLMClient:
    """A mock LLM client with no pre-loaded responses."""
    return MockLLMClient()


@pytest.fixture
def mock_embedder() -> MockEmbedder:
    """A mock embedder with 64-dim vectors."""
    return MockEmbedder(dim=64)


@pytest.fixture
def repository(session: AsyncSession, mock_embedder: MockEmbedder, test_settings: Settings) -> MemoryRepository:
    """A MemoryRepository backed by the test session."""
    return MemoryRepository(session, mock_embedder, settings=test_settings)


@pytest.fixture
def retriever(
    session: AsyncSession,
    mock_embedder: MockEmbedder,
    repository: MemoryRepository,
    test_settings: Settings,
) -> MemoryRetriever:
    """A MemoryRetriever backed by the test session."""
    return MemoryRetriever(session, mock_embedder, repository, settings=test_settings)


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
def user_id() -> str:
    """A unique user UUID for each test."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_memory() -> ExtractedMemory:
    """A sample extracted memory for tests."""
    return ExtractedMemory(
        category=MemoryCategory.LOCATION,
        slot_key="city",
        value="Pune",
        confidence=0.9,
    )
