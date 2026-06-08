"""Business logic for the universes feature."""

import base64
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.universes import repository as universes_repo
from app.features.universes.models import Ticker, Universe
from app.features.universes.schemas import (
    AddResult,
    TickerSummary,
    UniverseDetail,
    UniverseListResponse,
    UniverseSummary,
)
from app.features.universes.shared.alpaca_assets import (
    get_alpaca_asset_map,
    normalize_symbol,
)


class SystemManagedUniverseError(ValueError):
    """Raised when attempting to mutate a system-managed universe."""


def _generate_public_id() -> str:
    raw = secrets.token_hex(6)
    encoded = base64.b32encode(bytes.fromhex(raw)).decode().rstrip("=").lower()
    return f"uni_{encoded[:10]}"


async def list_universes(
    db: AsyncSession, include_deleted: bool = False
) -> UniverseListResponse:
    rows = await universes_repo.list_universes_with_counts(
        db, include_deleted=include_deleted
    )
    summaries = [
        UniverseSummary(
            id=universe.id,
            name=universe.name,
            display_name=universe.display_name,
            description=universe.description,
            public_id=universe.public_id,
            last_retrain_at=universe.last_retrain_at,
            is_system_managed=universe.is_system_managed,
            created_at=universe.created_at,
            ticker_count=count,
        )
        for universe, count in rows
    ]
    return UniverseListResponse(universes=summaries, total=len(summaries))


async def get_universe_detail(
    db: AsyncSession, universe_id: uuid.UUID
) -> UniverseDetail | None:
    universe: Universe | None = await universes_repo.get_universe_by_id(db, universe_id)
    if universe is None:
        return None
    tickers = await universes_repo.list_active_tickers_for_universe(db, universe_id)
    return UniverseDetail(
        id=universe.id,
        name=universe.name,
        display_name=universe.display_name,
        description=universe.description,
        public_id=universe.public_id,
        last_retrain_at=universe.last_retrain_at,
        is_system_managed=universe.is_system_managed,
        created_at=universe.created_at,
        tickers=[TickerSummary.model_validate(t) for t in tickers],
    )


async def create_universe(
    db: AsyncSession,
    name: str,
    display_name: str,
    description: str | None = None,
) -> Universe:
    existing = await universes_repo.get_universe_by_name(db, name)
    if existing is not None:
        raise ValueError(f"Universe with name '{name}' already exists")
    universe = Universe(
        name=name,
        display_name=display_name,
        description=description,
        public_id=_generate_public_id(),
    )
    db.add(universe)
    await db.flush()
    return universe


async def update_universe(
    db: AsyncSession, universe_id: uuid.UUID, **kwargs
) -> Universe:
    universe = await universes_repo.get_universe_by_id(db, universe_id)
    if universe is None:
        raise ValueError("Universe not found")
    if universe.is_system_managed:
        raise SystemManagedUniverseError("Cannot modify a system-managed universe")
    for key, value in kwargs.items():
        if value is not None and hasattr(universe, key):
            setattr(universe, key, value)
    await db.flush()
    return universe


async def soft_delete_universe(db: AsyncSession, universe_id: uuid.UUID) -> None:
    universe = await universes_repo.get_universe_by_id(db, universe_id)
    if universe is None:
        raise ValueError("Universe not found")
    if universe.is_system_managed:
        raise SystemManagedUniverseError("Cannot delete a system-managed universe")
    universe.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def restore_universe(db: AsyncSession, universe_id: uuid.UUID) -> None:
    universe = await universes_repo.get_universe_by_id(
        db, universe_id, include_deleted=True
    )
    if universe is None:
        raise ValueError("Universe not found")
    universe.deleted_at = None
    await db.flush()


def _assert_universe_active(universe: Universe | None) -> Universe:
    if universe is None:
        raise ValueError("Universe not found")
    if universe.deleted_at is not None:
        raise ValueError("Cannot modify a deleted universe")
    return universe


async def add_members(
    db: AsyncSession, universe_id: uuid.UUID, symbols: list[str]
) -> AddResult:
    _assert_universe_active(await universes_repo.get_universe_by_id(db, universe_id))

    alpaca_map = get_alpaca_asset_map()

    added: list[str] = []
    already_present: list[str] = []
    invalid: list[str] = []

    current_memberships = await universes_repo.get_active_memberships(db, universe_id)
    current_ticker_ids = {m.ticker_id for m in current_memberships}

    for raw in symbols:
        normalized = normalize_symbol(raw)
        asset = alpaca_map.get(normalized)
        if asset is None:
            invalid.append(raw)
            continue

        ticker = await universes_repo.get_or_create_ticker(db, normalized)
        if ticker is None:
            ticker = Ticker(
                symbol=normalized,
                name=asset.symbol,
                exchange=asset.exchange,
                asset_type=asset.asset_type,
            )
            db.add(ticker)
            await db.flush()
        else:
            ticker.active = True

        if ticker.id in current_ticker_ids:
            already_present.append(normalized)
        else:
            added.append(normalized)

    new_ticker_ids: list[uuid.UUID] = []
    for symbol in added:
        ticker = await universes_repo.get_or_create_ticker(db, symbol)
        if ticker:
            new_ticker_ids.append(ticker.id)

    if new_ticker_ids:
        await universes_repo.add_memberships(db, universe_id, new_ticker_ids)

    return AddResult(
        added=added,
        already_present=already_present,
        invalid=invalid,
    )


async def remove_member(
    db: AsyncSession, universe_id: uuid.UUID, ticker_id: uuid.UUID
) -> None:
    _assert_universe_active(await universes_repo.get_universe_by_id(db, universe_id))
    removed = await universes_repo.remove_membership(db, universe_id, ticker_id)
    if not removed:
        raise ValueError("Ticker is not an active member of this universe")


async def get_members(
    db: AsyncSession,
    universe_id: uuid.UUID,
    at_date: datetime | None = None,
) -> list[Ticker]:
    universe = await universes_repo.get_universe_by_id(db, universe_id)
    if universe is None:
        raise ValueError("Universe not found")
    if at_date:
        return await universes_repo.get_members_at_date(db, universe_id, at_date)
    return await universes_repo.list_active_tickers_for_universe(db, universe_id)
