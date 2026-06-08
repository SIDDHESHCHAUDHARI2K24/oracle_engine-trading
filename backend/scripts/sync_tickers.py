"""Sync all tradable US equities from Alpaca into the local tickers table.

Fetches the full Alpaca asset list, then upserts in chunks of 1000.
Idempotent — safe to run repeatedly.

Usage:
    uv run python scripts/sync_tickers.py
"""

import asyncio
import logging
import os
import sys

import typer
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.features.universes.models import Ticker
from app.features.universes.shared.alpaca_assets import (
    AssetInfo,
    get_alpaca_asset_map,
    normalize_symbol,
)

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mbi_user:mbi_password@localhost:5433/mbi"
)

logger = logging.getLogger(__name__)

cli = typer.Typer()


async def _upsert_chunk(db: AsyncSession, symbols: list[str], asset_map: dict[str, AssetInfo]) -> tuple[int, int]:
    inserted = 0
    updated = 0

    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        asset = asset_map.get(normalized)
        if asset is None:
            continue

        result = await db.execute(
            select(Ticker).where(Ticker.symbol == normalized)
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            existing.name = asset.symbol
            existing.exchange = asset.exchange
            existing.asset_type = asset.asset_type
            existing.active = True
            updated += 1
        else:
            ticker = Ticker(
                symbol=normalized,
                name=asset.symbol,
                exchange=asset.exchange,
                asset_type=asset.asset_type,
            )
            db.add(ticker)
            inserted += 1

    await db.flush()
    return inserted, updated


async def _sync_all() -> None:
    engine = create_async_engine(
        DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
    )
    sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("Fetching Alpaca asset map...")
    asset_map = get_alpaca_asset_map()
    all_symbols = list(asset_map.keys())
    logger.info("Fetched %d assets from Alpaca", len(all_symbols))

    chunk_size = 1000
    total_inserted = 0
    total_updated = 0

    async with sessionmaker() as session:
        for i in range(0, len(all_symbols), chunk_size):
            chunk = all_symbols[i : i + chunk_size]
            ins, upd = await _upsert_chunk(session, chunk, asset_map)
            total_inserted += ins
            total_updated += upd
            logger.info(
                "Chunk %d/%d — inserted=%d updated=%d",
                i // chunk_size + 1,
                (len(all_symbols) + chunk_size - 1) // chunk_size,
                ins,
                upd,
            )

        await session.commit()
        logger.info("Sync complete: inserted=%d updated=%d", total_inserted, total_updated)

    await engine.dispose()


@cli.command()
def sync():
    """Fetch all US equities from Alpaca and upsert into the tickers table."""
    asyncio.run(_sync_all())


if __name__ == "__main__":
    cli()
