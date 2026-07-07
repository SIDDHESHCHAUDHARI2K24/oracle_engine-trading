"""Prefect task wrappers for data ingestion feature services.

Thin wrappers — no business logic here. Each @task-decorated function
calls into the NumericalOrchestrator or gap detection service.
"""

import uuid

from prefect import task
from prefect.logging import get_run_logger

from app.features.data_ingestion.gap_detection import detect_gaps_batch
from app.features.data_ingestion.numerical.fred import FREDFetcher
from app.features.data_ingestion.numerical.yahoo import YahooFinanceFetcher
from app.features.data_ingestion.numerical.alpaca import AlpacaFetcher
from app.features.data_ingestion.numerical.stooq import StooqFetcher
from app.features.data_ingestion.service import NumericalOrchestrator


@task(retries=3, retry_delay_seconds=60)
async def ingest_universe(
    ticker_map: dict[str, uuid.UUID],
    start_date: str,
    end_date: str,
    mode: str = "incremental",
) -> dict:
    """Fetch and persist OHLCV + macro for a universe's tickers."""
    logger = get_run_logger()

    from app.features.core.database import async_session_factory

    async with async_session_factory() as session:
        fetchers = [
            YahooFinanceFetcher(),
            AlpacaFetcher(),
            StooqFetcher(),
        ]
        macro = FREDFetcher()

        orchestrator = NumericalOrchestrator(
            session=session,
            ohlcv_fetchers=fetchers,
            macro_fetcher=macro,
        )

        result = await orchestrator.run(
            ticker_map=ticker_map,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
        )
        logger.info("Ingest complete: %s", result)
        return result


@task(retries=2, retry_delay_seconds=30)
async def fill_gaps(
    ticker_added_map: dict[uuid.UUID, str],
) -> dict:
    """Detect and fill gaps for tickers with missing bar dates."""
    logger = get_run_logger()

    from app.features.core.database import async_session_factory

    async with async_session_factory() as session:
        gaps = await detect_gaps_batch(session, ticker_added_map)
        logger.info("Detected %d tickers with gaps", len(gaps))
        return gaps


@task(retries=1, retry_delay_seconds=30)
async def compute_features(
    ticker_map: dict | None = None,
) -> dict:
    """Compute features incrementally — trailing-window-seeded via trading calendar.

    Loads the last 252 trading days of OHLCV per ticker as the seed window
    (using the NYSE trading calendar, NOT naive row counts), runs the full
    pipeline, and persists only new rows.
    """
    logger = get_run_logger()

    import uuid as _uuid

    import pandas as pd

    from app.features.core.database import async_session_factory
    from app.features.data_ingestion.repository import (
        get_bars_in_range as _get_bars,
    )
    from app.features.data_ingestion.models import (
        MacroObservation,
    )
    from app.features.feature_engineering.service import (
        FeatureOrchestrator,
        get_active_tickers,
    )

    async with async_session_factory() as session:
        tickers = await get_active_tickers(session)
        ticker_ids = [_uuid.UUID(t["id"]) for t in tickers]
        logger.info(f"Computing features for {len(tickers)} tickers...")

        # ── Load macro DataFrame (read-only, shared across all tickers) ──
        from sqlalchemy import select
        from app.features.feature_engineering.shared.feature_schema import macro_names

        macro_stmt = select(
            MacroObservation.series_name,
            MacroObservation.observed_date,
            MacroObservation.value,
        ).where(
            MacroObservation.series_name.in_(macro_names()),
        ).order_by(MacroObservation.observed_date)
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

        # ── OHLCV loader (called inside orchestrator for each ticker) ──
        async def load_ohlcv_range(
            ticker_id, start_date, end_date
        ) -> pd.DataFrame:
            bars = await _get_bars(session, ticker_id, start_date, end_date)
            if not bars:
                return pd.DataFrame()
            records = []
            for bar in bars:
                records.append({
                    "bar_date": bar.bar_date,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": int(bar.volume),
                })
            df = pd.DataFrame(records)
            if not df.empty:
                df = df.set_index("bar_date").sort_index()
            return df

        orch = FeatureOrchestrator(n_jobs=-1)
        result = await orch.process_tickers_incremental(
            session=session,
            ticker_ids=ticker_ids,
            load_ohlcv_range=load_ohlcv_range,
            macro_df=macro_df,
            seed_trading_days=252,
        )
        logger.info(f"Feature computation result: {result}")
        return result
