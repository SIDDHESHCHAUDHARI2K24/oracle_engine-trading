"""Tests for basic database connectivity using asyncpg."""

import pytest

from app.features.core.database import get_db


@pytest.mark.asyncio
async def test_database_select_1() -> None:
    """`SELECT 1` should succeed and return the value 1."""
    async with get_db() as conn:
        row = await conn.fetchrow("SELECT 1 AS value")
        assert row is not None
        assert row["value"] == 1

