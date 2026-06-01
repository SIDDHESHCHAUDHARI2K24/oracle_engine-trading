"""Tests for basic database connectivity using the per-test session."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_database_select_1(db_session: AsyncSession) -> None:
    """SELECT 1 should succeed and return the value 1."""
    result = await db_session.execute(text("SELECT 1 AS value"))
    assert result.scalar() == 1
