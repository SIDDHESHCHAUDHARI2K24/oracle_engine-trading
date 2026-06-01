"""Data access layer for the universes feature."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.universes.models import Ticker, Universe, UniverseMembership


async def list_universes(db: AsyncSession) -> list[Universe]:
    """Return all non-deleted universes, ordered by name."""
    result = await db.execute(
        select(Universe)
        .where(Universe.deleted_at.is_(None))
        .order_by(Universe.name)
    )
    return list(result.scalars().all())


async def get_universe_by_id(db: AsyncSession, universe_id: uuid.UUID) -> Universe | None:
    """Return a non-deleted universe by id, with active memberships eager-loaded."""
    result = await db.execute(
        select(Universe)
        .where(Universe.id == universe_id, Universe.deleted_at.is_(None))
        .options(selectinload(Universe.memberships).selectinload(UniverseMembership.ticker))
    )
    return result.scalar_one_or_none()


async def list_active_tickers_for_universe(
    db: AsyncSession, universe_id: uuid.UUID
) -> list[Ticker]:
    """Return active tickers currently in the given universe."""
    result = await db.execute(
        select(Ticker)
        .join(UniverseMembership, UniverseMembership.ticker_id == Ticker.id)
        .where(
            UniverseMembership.universe_id == universe_id,
            UniverseMembership.removed_at.is_(None),
            Ticker.active.is_(True),
        )
        .order_by(Ticker.symbol)
    )
    return list(result.scalars().all())
