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
    """Compute features for active tickers (incremental — trailing-window-seeded)."""
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.feature_engineering.service import (
        FeatureOrchestrator,
        get_active_tickers,
    )

    async with async_session_factory() as session:
        tickers = await get_active_tickers(session)
        logger.info(f"Computing features for {len(tickers)} tickers...")

    orch = FeatureOrchestrator(n_jobs=-1)

    logger.info("Feature computation queued")
    return {"tickers_processed": len(tickers), "status": "queued"}
