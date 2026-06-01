"""Tests for basic database connectivity using asyncpg."""

import pytest

from sqlalchemy import text

from app.features.core.database import get_async_session


@pytest.mark.asyncio
async def test_database_select_1() -> None:
    """`SELECT 1` should succeed and return the value 1."""
    async for session in get_async_session():
        row = await session.execute(text("SELECT 1 AS value"))
        result = row.scalar()
        assert result == 1
