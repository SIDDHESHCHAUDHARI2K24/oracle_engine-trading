#!/usr/bin/env python3
"""Create the separate `prefect` database on the existing Postgres instance.

Usage:
    uv run python scripts/setup_prefect_db.py
"""

import asyncio
import sys
from urllib.parse import urlparse

import typer

app = typer.Typer()


@app.command()
def setup():
    """Create the prefect database if it doesn't exist."""
    asyncio.run(_create_prefect_db())


async def _create_prefect_db():
    from dotenv import load_dotenv
    import os

    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    parsed = urlparse(database_url)
    target_db = "prefect"

    user = parsed.username or "postgres"
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432

    try:
        import asyncpg
    except ImportError:
        print("ERROR: asyncpg not installed")
        sys.exit(1)

    conn = await asyncpg.connect(
        user=user, password=password, host=host, port=port, database="postgres"
    )

    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target_db
        )

        if exists:
            print(f"Database '{target_db}' already exists — nothing to do.")
        else:
            await conn.execute(f"CREATE DATABASE {target_db}")
            print(f"Created database '{target_db}' successfully.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        await conn.close()

    prefect_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{target_db}"
    print()
    print("Add this to your .env file:")
    print(f"PREFECT_DATABASE_URL={prefect_url}")


if __name__ == "__main__":
    app()
