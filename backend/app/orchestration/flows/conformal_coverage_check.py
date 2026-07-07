import uuid
from datetime import date

from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(
    name="coverage-check-universe",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=1_800,
)
async def coverage_check_universe(universe_id: uuid.UUID) -> dict:
    logger = get_run_logger()
    today = date.today()

    from app.features.core.database import async_session_factory
    from app.features.monitoring.signals.coverage import CoverageSignal

    async with async_session_factory() as session:
        try:
            signal = CoverageSignal()
            await signal.compute(session, universe_id, today)
            await session.flush()
            logger.info("Coverage check complete for universe %s", universe_id)
            return {"universe_id": str(universe_id), "status": "completed"}
        except Exception:
            logger.exception("Coverage check failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message=f"Coverage check failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {"universe_id": str(universe_id), "status": "failed"}


@flow(name="conformal_coverage_check", log_prints=True)
async def conformal_coverage_check_flow() -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory, _init_engine
    from app.features.universes.repository import list_universes

    _init_engine()

    async with async_session_factory() as session:
        universes = await list_universes(session, include_deleted=False)
        logger.info(
            "Conformal coverage check starting for %d active universes",
            len(universes),
        )

    results = []
    for u in universes:
        result = await coverage_check_universe(u.id)
        results.append(result)

    succeeded = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        "Conformal coverage check complete: %d succeeded, %d failed out of %d universes",
        succeeded,
        failed,
        len(results),
    )

    return {
        "universes_processed": len(universes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
