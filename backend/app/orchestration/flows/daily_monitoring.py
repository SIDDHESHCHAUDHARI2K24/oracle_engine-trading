import uuid
from datetime import date

from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(
    name="monitoring-freshness",
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=600,
)
async def freshness_signal_task(universe_id: uuid.UUID | None = None) -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.freshness import compute_freshness

    async with async_session_factory() as session:
        try:
            alert_service = AlertService()
            result = await compute_freshness(
                session, universe_id=universe_id, alert_service=alert_service
            )
            await session.flush()
            logger.info("Freshness check complete")
            return {"status": "completed", "data": result}
        except Exception:
            logger.exception("Freshness check failed")
            await alert_service.raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message="Freshness monitoring task failed",
            )
            return {"status": "failed"}


@task(
    name="monitoring-pipeline-success",
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=600,
)
async def pipeline_success_signal_task() -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.freshness import compute_pipeline_success

    async with async_session_factory() as session:
        try:
            alert_service = AlertService()
            result = await compute_pipeline_success(
                session=session, alert_service=alert_service
            )
            await session.flush()
            logger.info("Pipeline success check complete")
            return {"status": "completed", "data": result}
        except Exception:
            logger.exception("Pipeline success check failed")
            await alert_service.raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message="Pipeline success monitoring task failed",
            )
            return {"status": "failed"}


@task(
    name="monitoring-correlation",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=1_800,
)
async def correlation_signal_task(universe_id: uuid.UUID) -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.correlation import (
        compute_conviction_correlation,
    )

    async with async_session_factory() as session:
        try:
            alert_service = AlertService()
            corr = await compute_conviction_correlation(
                session, universe_id, alert_service=alert_service
            )
            await session.flush()
            logger.info(
                "Correlation check complete for universe %s: corr=%s", universe_id, corr
            )
            return {
                "universe_id": str(universe_id),
                "status": "completed",
                "correlation": corr,
            }
        except Exception:
            logger.exception("Correlation check failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message=f"Correlation monitoring task failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {"universe_id": str(universe_id), "status": "failed"}


@task(
    name="monitoring-drift",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=3_600,
)
async def drift_signal_task(universe_id: uuid.UUID) -> dict:
    logger = get_run_logger()
    measure_date = date.today()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.drift import FeatureDriftSignal

    async with async_session_factory() as session:
        try:
            await FeatureDriftSignal.compute_all_drift(
                session, universe_id, measure_date
            )
            await session.flush()
            logger.info("Drift check complete for universe %s", universe_id)
            return {"universe_id": str(universe_id), "status": "completed"}
        except Exception:
            logger.exception("Drift check failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message=f"Drift monitoring task failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {"universe_id": str(universe_id), "status": "failed"}


@task(
    name="monitoring-backtest-drift",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=1_800,
)
async def backtest_drift_signal_task(universe_id: uuid.UUID) -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.backtest_drift import compute_backtest_drift

    async with async_session_factory() as session:
        try:
            alert_service = AlertService()
            result = await compute_backtest_drift(
                session, universe_id, alert_service=alert_service
            )
            await session.flush()
            logger.info("Backtest drift check complete for universe %s", universe_id)
            return {
                "universe_id": str(universe_id),
                "status": "completed",
                "data": result,
            }
        except Exception:
            logger.exception("Backtest drift check failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message=f"Backtest drift monitoring task failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {"universe_id": str(universe_id), "status": "failed"}


@flow(name="daily_monitoring", log_prints=True)
async def daily_monitoring_flow() -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory, _init_engine
    from app.features.universes.repository import list_universes

    _init_engine()

    today = date.today()
    is_heavy_day = today.weekday() in (0, 3)

    logger.info(
        "Daily monitoring starting: heavy=%s (Mon/Thu) weekday=%d",
        is_heavy_day,
        today.weekday(),
    )

    async with async_session_factory() as session:
        universes = await list_universes(session, include_deleted=False)
        logger.info("Daily monitoring for %d active universes", len(universes))

    results = []

    fresh_result = await freshness_signal_task()
    results.append(fresh_result)

    pipe_result = await pipeline_success_signal_task()
    results.append(pipe_result)

    if is_heavy_day:
        for u in universes:
            corr_result = await correlation_signal_task(u.id)
            results.append(corr_result)

            drift_result = await drift_signal_task(u.id)
            results.append(drift_result)

            bt_drift_result = await backtest_drift_signal_task(u.id)
            results.append(bt_drift_result)

    succeeded = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        "Daily monitoring complete: %d succeeded, %d failed out of %d results",
        succeeded,
        failed,
        len(results),
    )

    return {
        "heavy_day": is_heavy_day,
        "universes_processed": len(universes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
