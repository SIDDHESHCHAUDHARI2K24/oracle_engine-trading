"""Async SQLAlchemy 2.0 database access for the MBI Oracle Engine backend.

Provides an async engine configured for PostgreSQL + TimescaleDB via
asyncpg, an async_sessionmaker for session-per-request, and a FastAPI
dependency that yields and closes sessions.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.core.config import get_settings

_async_engine = None
async_session_factory = None


def _init_engine():
    global _async_engine, async_session_factory
    if _async_engine is not None:
        return
    settings = get_settings()
    _async_engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        pool_size=10,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
        connect_args={
            "server_settings": {"statement_timeout": "30000"},
        },
    )
    async_session_factory = async_sessionmaker(
        _async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _reset_engine():
    """Reset the engine and session factory. Used in tests to switch databases."""
    global _async_engine, async_session_factory
    if _async_engine is not None:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is None:
            _async_engine.sync_engine.dispose()
    _async_engine = None
    async_session_factory = None


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; closed on exit."""
    _init_engine()
    if async_session_factory is not None:
        async with async_session_factory() as session:
            try:
                yield session
            finally:
                await session.close()
