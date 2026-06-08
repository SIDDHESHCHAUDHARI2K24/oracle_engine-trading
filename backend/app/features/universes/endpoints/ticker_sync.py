"""Admin-only endpoint to trigger a full Alpaca ticker sync."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes.repository import UpsertResult, validate_and_upsert_tickers
from app.features.universes.shared.alpaca_assets import get_alpaca_asset_map

logger = logging.getLogger(__name__)

ticker_sync_router = APIRouter(prefix="/api/v1/tickers", tags=["tickers"])


class TickerSyncResponse(BaseModel):
    inserted: int
    updated: int
    total: int


@ticker_sync_router.post("/sync", response_model=TickerSyncResponse)
async def sync_tickers(
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> TickerSyncResponse:
    """Sync all Alpaca US equities into the local tickers table. Admin only."""
    asset_map = get_alpaca_asset_map()
    all_symbols = list(asset_map.keys())

    result: UpsertResult = await validate_and_upsert_tickers(
        db=db, symbols=all_symbols, alpaca_map=asset_map
    )

    await db.commit()

    total = result.inserted + result.skipped
    logger.info(
        "Ticker sync complete: inserted=%d skipped=%d invalid=%d",
        result.inserted,
        result.skipped,
        len(result.invalid),
    )

    return TickerSyncResponse(
        inserted=result.inserted,
        updated=result.skipped,
        total=total,
    )
