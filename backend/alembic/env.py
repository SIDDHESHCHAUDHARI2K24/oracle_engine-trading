"""Alembic environment configuration for the MBI Oracle Engine backend.

Imports all feature models so autogenerate discovers every table.
Uses a sync engine (Alembic requirement) derived from the async URL
in DATABASE_URL.  The first migration enables the TimescaleDB extension.
"""

import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from alembic import context

backend_dir = Path(__file__).resolve().parent.parent
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("DATABASE_URL")
sync_url = None
if database_url:
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    sync_url = sync_url.replace("postgresql+psycopg://", "postgresql://")
    sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
    config.set_main_option("sqlalchemy.url", sync_url)

from app.features.core.base import Base  # noqa: E402
import app.features.auth.models  # noqa: E402, F401
import app.features.universes.models  # noqa: E402, F401
import app.features.data_ingestion.models  # noqa: E402, F401
import app.features.feature_engineering.models  # noqa: E402, F401
import app.features.ml_models.models  # noqa: E402, F401
import app.features.backtesting.models  # noqa: E402, F401
import app.features.conviction_tickets.models  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or sync_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = sync_url or config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
