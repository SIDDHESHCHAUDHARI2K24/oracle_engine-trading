#!/usr/bin/env python3
"""Cold-start backfill CLI — pulls 2 years of OHLCV + macro for all active tickers.

Resumable via ON CONFLICT upserts — re-running skips already-present data.
Batched (50 tickers/batch) with per-batch progress logging.

Usage:
    uv run python scripts/initial_backfill.py
    uv run python scripts/initial_backfill.py --universe sp500
    uv run python scripts/initial_backfill.py --batch-size 25
"""

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import typer

app = typer.Typer()

logger = logging.getLogger(__name__)


@app.command()
def backfill(
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name to scope to"),
    batch_size: int = typer.Option(50, "--batch-size", "-b", help="Tickers per batch"),
    years: int = typer.Option(2, "--years", "-y", help="Years of history to pull"),
):
    """Run the cold-start backfill for all (or one) universes."""
    asyncio.run(_run_backfill(universe, batch_size, years))


async def _run_backfill(universe: str | None, batch_size: int, years: int):
    import app.features.core.database as db
    from app.features.data_ingestion.numerical.alpaca import AlpacaFetcher
    from app.features.data_ingestion.numerical.fred import FREDFetcher
    from app.features.data_ingestion.numerical.stooq import StooqFetcher
    from app.features.data_ingestion.numerical.yahoo import YahooFinanceFetcher
    from app.features.data_ingestion.service import NumericalOrchestrator

    db._init_engine()

    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=years * 365)).isoformat()

    print(f"Starting cold-start backfill: {start_date} -> {end_date}")
    print(f"Batch size: {batch_size}, scope: {universe or 'all'}")

    async with db.async_session_factory() as session:
        from app.features.universes.repository import get_active_ticker_symbol_map

        ticker_map = await get_active_ticker_symbol_map(session, universe)

        if not ticker_map:
            print("No active tickers found. Seed universes first.")
            return

        symbols = list(ticker_map.keys())
        print(f"Found {len(symbols)} active tickers across all universes")

        batches = [
            dict(list(ticker_map.items())[i : i + batch_size])
            for i in range(0, len(ticker_map), batch_size)
        ]

        total_ohlcv = 0
        total_macro = 0
        total_failed: list[str] = []

        for batch_idx, batch_map in enumerate(batches):
            print(
                f"Batch {batch_idx + 1}/{len(batches)}: "
                f"{len(batch_map)} tickers..."
            )

            fetchers = [YahooFinanceFetcher(), AlpacaFetcher(), StooqFetcher()]
            macro = FREDFetcher()

            orchestrator = NumericalOrchestrator(
                session=session,
                ohlcv_fetchers=fetchers,
                macro_fetcher=macro,
            )

            result = await orchestrator.run(
                ticker_map=dict(batch_map),
                start_date=start_date,
                end_date=end_date,
                mode="cold_start",
            )

            total_ohlcv += result.get("ohlcv_rows", 0)
            total_macro += result.get("macro_rows", 0)
            total_failed.extend(result.get("failed_tickers", []))

            print(
                f"  -> {result['status']}: {result['ohlcv_rows']} bars, "
                f"{len(result.get('failed_tickers', []))} failed tickers"
            )

        print(f"\nBackfill complete: {total_ohlcv} OHLCV rows, {total_macro} macro rows")
        if total_failed:
            print(f"Failed tickers ({len(total_failed)}): {', '.join(total_failed[:20])}")
            if len(total_failed) > 20:
                print(f"  ... and {len(total_failed) - 20} more")

        print("Done.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    app()
