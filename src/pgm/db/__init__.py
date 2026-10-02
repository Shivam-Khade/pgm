"""Database engine and session factory (async SQLAlchemy 2)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine

from pgm.config import get_settings


def _build_engine(url: str | None = None) -> AsyncEngine:
    settings = get_settings()
    db_url = url or settings.database_url
    return create_async_engine(db_url, echo=False, pool_pre_ping=True)


_engine = None
_session_factory = None


def get_engine(url: str | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _build_engine(url)
    return _engine


def get_session_factory(url: str | None = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = get_engine(url)
        _session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """Yield a session — use as an async context manager or FastAPI dependency."""
    factory = get_session_factory()
    async with factory() as session:
        yield session  # type: ignore[misc]


def reset_engine() -> None:
    """Reset the global engine (for tests)."""
    global _engine, _session_factory
    if _engine is not None:
        # engine disposal should be awaited; caller handles it
        pass
    _engine = None
    _session_factory = None
