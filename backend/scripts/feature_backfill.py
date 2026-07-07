"""Backfill script for feature engineering.

Usage:
    uv run python scripts/feature_backfill.py [--ticker AAPL]

Performs a full recompute of features for all active tickers (or a
single ticker) using the FeatureOrchestrator with parallel execution.
"""

import asyncio
import logging
import sys
import uuid as _uuid
from datetime import date as _date
from pathlib import Path

import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from app.features.core.database import async_session_factory  # noqa: E402
from app.features.data_ingestion.repository import (  # noqa: E402
    get_bars_in_range,
)
from app.features.data_ingestion.models import (  # noqa: E402
    MacroObservation,
)
from app.features.feature_engineering.service import (  # noqa: E402
    FeatureOrchestrator,
    get_active_tickers,
)
from app.features.feature_engineering.shared.feature_schema import (  # noqa: E402
    macro_names,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def backfill(
    ticker_symbol: str | None = typer.Option(None, "--ticker"),
    universe: str | None = typer.Option(None, "--universe"),
    n_jobs: int = typer.Option(-1, "--jobs"),
    mode: str = typer.Option("full", "--mode"),
):
    """Run feature backfill for all or specific tickers."""
    asyncio.run(_backfill(ticker_symbol, universe, n_jobs, mode))


async def _backfill(
    ticker_symbol: str | None,
    universe: str | None,
    n_jobs: int,
    mode: str,
) -> None:
    async with async_session_factory() as session:
        tickers = await get_active_tickers(session)
        if ticker_symbol:
            tickers = [
                t for t in tickers if t["symbol"].upper() == ticker_symbol.upper()
            ]
            if not tickers:
                logger.error(f"Ticker {ticker_symbol} not found")
                return

        ticker_ids = [_uuid.UUID(t["id"]) for t in tickers]
        logger.info(f"Backfilling features for {len(tickers)} tickers (mode={mode})...")

        # ── Load macro DataFrame ──
        macro_stmt = (
            select(
                MacroObservation.series_name,
                MacroObservation.observed_date,
                MacroObservation.value,
            )
            .where(MacroObservation.series_name.in_(macro_names()))
            .order_by(MacroObservation.observed_date)
        )
        macro_result = await session.execute(macro_stmt)
        macro_rows = macro_result.fetchall()

        macro_df = pd.DataFrame()
        if macro_rows:
            macro_dict: dict[str, dict] = {}
            for series_name, obs_date, value in macro_rows:
                if series_name not in macro_dict:
                    macro_dict[series_name] = {}
                macro_dict[series_name][obs_date] = float(value)
            macro_df = pd.DataFrame(macro_dict).sort_index()
            macro_df = macro_df.ffill()

        # ── OHLCV loader ──
        async def load_ohlcv(ticker_id, start_date, end_date):
            bars = await get_bars_in_range(session, ticker_id, start_date, end_date)
            if not bars:
                return pd.DataFrame()
            records = []
            for bar in bars:
                records.append(
                    {
                        "bar_date": bar.bar_date,
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                    }
                )
            df = pd.DataFrame(records)
            if not df.empty:
                df = df.set_index("bar_date").sort_index()
            return df

        orch = FeatureOrchestrator(n_jobs=n_jobs)

        if mode == "incremental":
            result = await orch.process_tickers_incremental(
                session=session,
                ticker_ids=ticker_ids,
                load_ohlcv_range=load_ohlcv,
                macro_df=macro_df,
                seed_trading_days=252,
            )
        else:
            result = await orch.process_tickers(
                session=session,
                ticker_ids=ticker_ids,
                load_ohlcv=lambda tid: asyncio.run(
                    load_ohlcv(tid, _date(2010, 1, 1), _date.today())
                ),
                macro_df=macro_df,
            )

        await session.commit()
        logger.info(f"Backfill complete: {result}")


if __name__ == "__main__":
    app()
