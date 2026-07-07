"""Weekly backtest Prefect flow.

Runs all 4 strategies over active members for each universe.
Scheduled: Sundays 4am ET (before the 6am weekly retrain).
"""

import uuid
from datetime import date, timedelta

from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(
    name="backtest-universe",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=7_200,
)
async def backtest_universe(universe_id: uuid.UUID, universe_name: str) -> dict:
    """Run backtest for a single universe across all 4 strategies.

    Isolated task — one universe failing does not abort the others.
    """
    logger = get_run_logger()
    as_of_date = date.today() - timedelta(days=1)
    period_start = as_of_date - timedelta(days=5 * 365)
    period_end = as_of_date

    from app.features.core.database import async_session_factory
    from app.features.backtesting.service import BacktestOrchestrator

    logger.info(
        "Backtest starting for universe %s (%s) period=%s → %s",
        universe_id,
        universe_name,
        period_start,
        period_end,
    )

    async with async_session_factory() as session:
        try:
            orchestrator = BacktestOrchestrator()
            result = await orchestrator.run_universe(
                session=session,
                universe_id=universe_id,
                period_start=period_start,
                period_end=period_end,
                triggered_by="weekly_scheduled",
            )

            logger.info(
                "Backtest completed for universe %s (%s): run_id=%s status=%s tickers=%d",
                universe_id,
                universe_name,
                result.id,
                result.status,
                result.num_tickers,
            )

            await session.flush()

            return {
                "universe_id": str(universe_id),
                "universe_name": universe_name,
                "run_id": str(result.id),
                "num_tickers": result.num_tickers,
                "status": result.status,
            }

        except Exception:
            logger.exception(
                "Backtest failed for universe %s (%s)",
                universe_id,
                universe_name,
            )
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="backtest_failure",
                message=f"Backtest failed for universe {universe_name} ({universe_id})",
                universe_id=universe_id,
            )
            return {
                "universe_id": str(universe_id),
                "universe_name": universe_name,
                "status": "failed",
            }


@flow(name="weekly_backtest", log_prints=True)
async def weekly_backtest_flow() -> dict:
    """Weekly backtest scheduled Sundays 4am ET.

    For each active universe: run all 4 backtest strategies over a
    5-year rolling window ending yesterday.  Per-universe isolation
    so one failure doesn't abort others.
    """
    logger = get_run_logger()

    from app.features.core.database import async_session_factory, _init_engine
    from app.features.universes.repository import list_universes

    _init_engine()

    async with async_session_factory() as session:
        universes = await list_universes(session, include_deleted=False)
        logger.info(
            "Weekly backtest starting for %d active universes",
            len(universes),
        )

    results = []
    for u in universes:
        result = await backtest_universe(u.id, u.name)
        results.append(result)

    succeeded = sum(1 for r in results if r.get("status") == "completed")
    completed_with_errors = sum(
        1 for r in results if r.get("status") == "completed_with_errors"
    )
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        "Weekly backtest complete: %d succeeded, %d with errors, %d failed out of %d universes",
        succeeded,
        completed_with_errors,
        failed,
        len(results),
    )

    return {
        "universes_processed": len(results),
        "succeeded": succeeded,
        "completed_with_errors": completed_with_errors,
        "failed": failed,
        "results": results,
    }
