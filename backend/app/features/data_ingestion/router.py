"""Data ingestion API endpoints.

Exposes trigger (on-demand refresh), status (latest run summary),
and bar query (OHLCV read-back for inspection).
"""

import logging
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.core.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data_ingestion", tags=["data_ingestion"])


@router.post("/trigger")
async def trigger_ingestion(
    universe_id: uuid.UUID | None = None,
    mode: str = "incremental",
    db: AsyncSession = Depends(get_async_session),
):
    """Trigger an on-demand data ingestion run.

    For small scopes (single universe), runs synchronously.
    For full scopes, fires a Prefect deployment and returns the run ID.
    """
    from app.features.data_ingestion.numerical.alpaca import AlpacaFetcher
    from app.features.data_ingestion.numerical.fred import FREDFetcher
    from app.features.data_ingestion.numerical.stooq import StooqFetcher
    from app.features.data_ingestion.numerical.yahoo import YahooFinanceFetcher
    from app.features.data_ingestion.service import NumericalOrchestrator
    from app.features.universes.repository import get_active_ticker_symbol_map

    ticker_map = await get_active_ticker_symbol_map(db, None)
    if not ticker_map:
        return {"message": "No active tickers found", "run_id": None}

    start = (date.today() - timedelta(days=5)).isoformat()
    end = date.today().isoformat()

    fetchers = [YahooFinanceFetcher(), AlpacaFetcher(), StooqFetcher()]
    macro = FREDFetcher()

    orchestrator = NumericalOrchestrator(
        session=db,
        ohlcv_fetchers=fetchers,
        macro_fetcher=macro,
    )

    result = await orchestrator.run(
        ticker_map=ticker_map,
        start_date=start,
        end_date=end,
        mode=mode,
    )

    return {
        "message": f"Ingestion {result['status']}",
        "run_id": result.get("run_id"),
        "summary": result,
    }


@router.get("/status")
async def ingestion_status(db: AsyncSession = Depends(get_async_session)):
    """Return latest IngestRun summary for the monitoring panel."""
    from app.features.data_ingestion.repository import get_latest_ingest_run

    run = await get_latest_ingest_run(db)
    return {
        "latest_run": run,
    }


@router.get("/bars")
async def query_bars(
    ticker_id: uuid.UUID = Query(..., description="Ticker UUID"),
    start: str = Query(..., description="Start date ISO"),
    end: str = Query(..., description="End date ISO"),
    db: AsyncSession = Depends(get_async_session),
):
    """Return OHLCV bars for a ticker within a date range."""
    from app.features.data_ingestion.repository import get_bars_in_range

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    bars = await get_bars_in_range(db, ticker_id, start_date, end_date)

    return {
        "ticker_id": str(ticker_id),
        "bars": [
            {
                "bar_date": b.bar_date.isoformat(),
                "open": float(b.open),
                "high": float(b.high),
                "low": float(b.low),
                "close": float(b.close),
                "adjusted_close": float(b.adjusted_close) if b.adjusted_close else None,
                "volume": b.volume,
                "source": b.source,
            }
            for b in bars
        ],
    }
