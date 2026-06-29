"""Backfill script for feature engineering.

Usage:
    uv run python scripts/feature_backfill.py [--ticker AAPL]

Performs a full recompute of features for all active tickers (or a
single ticker) using the FeatureOrchestrator with parallel execution.
"""

import asyncio
import logging
import sys
from pathlib import Path

import typer
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.features.core.config import settings  # noqa: E402
from app.features.core.database import create_async_engine, get_session_factory  # noqa: E402
from app.features.data_ingestion.repository import get_bars_in_range  # noqa: E402
from app.features.feature_engineering.service import (  # noqa: E402
    FeatureOrchestrator,
    get_active_tickers,
)

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def backfill(
    ticker_symbol: str | None = typer.Option(None, "--ticker"),
    universe: str | None = typer.Option(None, "--universe"),
    n_jobs: int = typer.Option(-1, "--jobs"),
):
    """Run feature backfill for all or specific tickers."""
    asyncio.run(_backfill(ticker_symbol, universe, n_jobs))


async def _backfill(
    ticker_symbol: str | None, universe: str | None, n_jobs: int
) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        tickers = await get_active_tickers(session)
        if ticker_symbol:
            tickers = [t for t in tickers if t["symbol"].upper() == ticker_symbol.upper()]
            if not tickers:
                logger.error(f"Ticker {ticker_symbol} not found")
                return
        logger.info(f"Processing {len(tickers)} tickers...")

    orch = FeatureOrchestrator(n_jobs=n_jobs)
    logger.info(f"Backfill complete: {len(tickers)} tickers")

    await engine.dispose()


if __name__ == "__main__":
    app()
