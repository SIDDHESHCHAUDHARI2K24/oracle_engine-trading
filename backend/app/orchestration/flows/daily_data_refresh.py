"""Daily data refresh Prefect flow.

Scheduled weekdays ~4:30pm ET — fetches new bars for all active
tickers post-market-close, refreshes macro, and fills gaps.
"""

from datetime import date, timedelta

from prefect import flow
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService
from app.orchestration.tasks.data_tasks import compute_features, fill_gaps, ingest_universe


@flow(name="daily_data_refresh", log_prints=True)
async def daily_data_refresh_flow(
    ticker_map: dict | None = None,
    target_date: str | None = None,
) -> dict:
    """Fetch incremental OHLCV + macro and fill detected gaps.

    Args:
        ticker_map: Optional dict of symbol → ticker_id. If None,
            resolved from all active universes by the caller.
        target_date: ISO date to fetch for. Defaults to today.
    """
    logger = get_run_logger()

    if target_date is None:
        target_date = date.today().isoformat()

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    if ticker_map is None:
        ticker_map = {}

    try:
        result = await ingest_universe(
            ticker_map=ticker_map,
            start_date=yesterday,
            end_date=target_date,
            mode="incremental",
        )

        if result.get("failed_tickers"):
            await fill_gaps({})

        feature_result = await compute_features(ticker_map)
        result["features"] = feature_result

        return result
    except Exception:
        logger.exception("Daily data refresh flow failed")
        from app.features.core.database import async_session_factory, _init_engine

        _init_engine()
        async with async_session_factory() as session:
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message="Daily data refresh flow failed",
            )
        raise
