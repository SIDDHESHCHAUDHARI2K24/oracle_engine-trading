"""Per-test database isolation with testcontainers.

Session-scoped container: spins up Postgres+TimescaleDB once per test run.
Function-scoped session: wraps each test in a transaction rolled back on teardown.

All imports are deferred to avoid pulling in application config before the
container fixture sets DATABASE_URL.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def database_url():
    """Session-scoped: spins up Postgres+TimescaleDB, runs migrations, yields URL.

    Container is started once per test session and destroyed at teardown.
    TimescaleDB extension is available via the ``timescale/timescaledb:latest-pg16``
    image (extension must be created by the relevant Alembic migration).
    """
    postgres = PostgresContainer(
        image="timescale/timescaledb:latest-pg16",
        dbname="oracle_test",
        username="test",
        password="test",
    )
    postgres.start()

    sync_url = postgres.get_connection_url()
    # Convert to plain postgresql:// so database.py can convert it to postgresql+asyncpg://
    plain_url = sync_url.replace("postgresql+psycopg2://", "postgresql://")
    os.environ["DATABASE_URL"] = plain_url

    # Clear settings cache and reset DB engine so create_app() picks up test DB
    from app.features.core.config import get_settings

    get_settings.cache_clear()
    from app.features.core.database import _reset_engine

    _reset_engine()

    alembic_cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")

    # Seed admin user in the test DB so endpoint integration tests work
    from argon2 import PasswordHasher
    from sqlalchemy import create_engine as create_sync_engine
    from sqlalchemy.orm import sessionmaker as sync_sessionmaker

    sync_engine = create_sync_engine(sync_url)
    SyncSessionLocal = sync_sessionmaker(bind=sync_engine)
    ph = PasswordHasher()

    with SyncSessionLocal() as s:
        from sqlalchemy import text

        existing = s.execute(
            text("SELECT 1 FROM users WHERE email = :email"),
            {"email": "admin@mbilabs.io"},
        ).first()
        if existing is None:
            s.execute(
                text(
                    "INSERT INTO users (email, hashed_password, is_admin, full_name) "
                    "VALUES (:email, :pw, true, :name)"
                ),
                {
                    "email": "admin@mbilabs.io",
                    "pw": ph.hash("change-me-on-first-login"),
                    "name": "Admin User",
                },
            )
            s.commit()
    sync_engine.dispose()

    yield sync_url

    postgres.stop()
    del os.environ["DATABASE_URL"]


@pytest.fixture
async def db_session(database_url: str):
    """Function-scoped: wraps each test in a transaction rolled back at teardown.

    Provides an async SQLAlchemy session bound to a connection-level
    transaction.  All writes are rolled back after the test completes so
    every test sees a clean database.
    """
    async_url = database_url.replace(
        "postgresql+psycopg2://", "postgresql+asyncpg://"
    ).replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_url, echo=False, pool_pre_ping=True)

    async with engine.connect() as connection:
        async with connection.begin() as transaction:
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with session_factory() as session:
                yield session
                await transaction.rollback()

    await engine.dispose()
