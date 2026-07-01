"""Data access layer for the universes feature."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.universes.models import Ticker, Universe, UniverseMembership


@dataclass
class UpsertResult:
    inserted: int
    skipped: int
    invalid: list[str]


async def list_universes(
    db: AsyncSession, include_deleted: bool = False
) -> list[Universe]:
    """Return universes ordered by name, optionally including soft-deleted."""
    stmt = select(Universe)
    if not include_deleted:
        stmt = stmt.where(Universe.deleted_at.is_(None))
    stmt = stmt.order_by(Universe.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_universes_with_counts(
    db: AsyncSession, include_deleted: bool = False
) -> list[tuple[Universe, int]]:
    """Return universes paired with their active-ticker counts."""
    count_sq = (
        select(func.count())
        .select_from(UniverseMembership)
        .where(
            UniverseMembership.universe_id == Universe.id,
            UniverseMembership.removed_at.is_(None),
        )
        .scalar_subquery()
    )
    stmt = select(Universe, count_sq.label("ticker_count"))
    if not include_deleted:
        stmt = stmt.where(Universe.deleted_at.is_(None))
    stmt = stmt.order_by(Universe.name)
    result = await db.execute(stmt)
    return [(row[0], int(row[1])) for row in result.all()]


async def get_universe_by_id(
    db: AsyncSession, universe_id: uuid.UUID, include_deleted: bool = False
) -> Universe | None:
    """Return a universe by id, with active memberships eager-loaded."""
    stmt = select(Universe).where(Universe.id == universe_id)
    if not include_deleted:
        stmt = stmt.where(Universe.deleted_at.is_(None))
    stmt = stmt.options(
        selectinload(Universe.memberships).selectinload(UniverseMembership.ticker)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_universe_by_name(db: AsyncSession, name: str) -> Universe | None:
    """Return a non-deleted universe by name."""
    result = await db.execute(
        select(Universe).where(Universe.name == name, Universe.deleted_at.is_(None))
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


async def validate_and_upsert_tickers(
    db: AsyncSession, symbols: list[str], alpaca_map: dict
) -> UpsertResult:
    """Validate symbols against an Alpaca asset map and upsert valid ones.

    Returns an UpsertResult with inserted, skipped, and invalid symbol lists.
    The caller is responsible for providing the asset map (enables testability).
    """
    from app.features.universes.shared.alpaca_assets import normalize_symbol

    inserted: list[str] = []
    skipped: list[str] = []
    invalid: list[str] = []

    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        asset = alpaca_map.get(normalized)
        if asset is None:
            invalid.append(symbol)
            continue

        result = await db.execute(select(Ticker).where(Ticker.symbol == normalized))
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.active = True
            skipped.append(normalized)
        else:
            ticker = Ticker(
                symbol=normalized,
                name=asset.symbol,
                exchange=asset.exchange,
                asset_type=asset.asset_type,
            )
            db.add(ticker)
            inserted.append(normalized)

    await db.flush()
    return UpsertResult(inserted=len(inserted), skipped=len(skipped), invalid=invalid)


async def get_or_create_ticker(db: AsyncSession, symbol: str) -> Ticker | None:
    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol))
    return result.scalar_one_or_none()


async def add_memberships(
    db: AsyncSession,
    universe_id: uuid.UUID,
    ticker_ids: list[uuid.UUID],
) -> list[UniverseMembership]:
    now = datetime.now(timezone.utc)
    memberships = []
    for tid in ticker_ids:
        m = UniverseMembership(
            universe_id=universe_id,
            ticker_id=tid,
            added_at=now,
        )
        db.add(m)
        memberships.append(m)
    await db.flush()
    return memberships


async def remove_membership(
    db: AsyncSession, universe_id: uuid.UUID, ticker_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe_id,
            UniverseMembership.ticker_id == ticker_id,
            UniverseMembership.removed_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        return False
    membership.removed_at = datetime.now(timezone.utc)
    await db.flush()
    return True


async def get_members_at_date(
    db: AsyncSession, universe_id: uuid.UUID, at_date: datetime
) -> list[Ticker]:
    result = await db.execute(
        select(Ticker)
        .join(UniverseMembership, UniverseMembership.ticker_id == Ticker.id)
        .where(
            UniverseMembership.universe_id == universe_id,
            UniverseMembership.added_at <= at_date,
            (UniverseMembership.removed_at.is_(None))
            | (UniverseMembership.removed_at > at_date),
            Ticker.active.is_(True),
        )
        .order_by(Ticker.symbol)
    )
    return list(result.scalars().all())


async def get_active_memberships(
    db: AsyncSession, universe_id: uuid.UUID
) -> list[UniverseMembership]:
    result = await db.execute(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe_id,
            UniverseMembership.removed_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def get_active_ticker_symbol_map(
    db: AsyncSession, universe_name: str | None = None
) -> dict[str, uuid.UUID]:
    """Return all active tickers as {symbol: ticker_id}, optionally scoped.

    Used by the data ingestion backfill and daily flow to determine
    which tickers to fetch data for.
    """
    stmt = (
        select(Ticker.symbol, Ticker.id)
        .select_from(Ticker)
        .join(UniverseMembership, UniverseMembership.ticker_id == Ticker.id)
        .where(
            UniverseMembership.removed_at.is_(None),
            Ticker.active.is_(True),
        )
        .distinct()
    )

    if universe_name:
        stmt = stmt.join(Universe, Universe.id == UniverseMembership.universe_id)
        stmt = stmt.where(
            Universe.name == universe_name,
            Universe.deleted_at.is_(None),
        )

    result = await db.execute(stmt)
    return {row[0]: row[1] for row in result.fetchall()}
