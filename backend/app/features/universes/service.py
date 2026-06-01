"""Business logic for the universes feature."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.universes import repository as universes_repo
from app.features.universes.models import Universe
from app.features.universes.schemas import (
    TickerSummary,
    UniverseDetail,
    UniverseListResponse,
    UniverseSummary,
)


async def list_universes(db: AsyncSession) -> UniverseListResponse:
    universes = await universes_repo.list_universes(db)
    return UniverseListResponse(
        universes=[UniverseSummary.model_validate(u) for u in universes],
        total=len(universes),
    )


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
        is_system_managed=universe.is_system_managed,
        created_at=universe.created_at,
        tickers=[TickerSummary.model_validate(t) for t in tickers],
    )
