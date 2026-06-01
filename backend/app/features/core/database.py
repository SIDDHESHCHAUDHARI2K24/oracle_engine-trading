"""Async SQLAlchemy 2.0 database access for the MBI Oracle Engine backend.

Provides an async engine configured for PostgreSQL + TimescaleDB via
asyncpg, an async_sessionmaker for session-per-request, and a FastAPI
dependency that yields and closes sessions.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.core.config import settings

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


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession per request; closed on exit."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
