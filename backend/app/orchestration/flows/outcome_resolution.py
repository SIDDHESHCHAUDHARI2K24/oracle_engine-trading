from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(retries=1, timeout_seconds=600)
async def resolve_due_tickets() -> dict:
    logger = get_run_logger()

    from app.features.core.database import async_session_factory
    from app.features.conviction_tickets.resolution import resolve_tickets

    logger.info("Outcome resolution starting")

    async with async_session_factory() as session:
        try:
            result = await resolve_tickets(session)
            logger.info(
                "Outcome resolution complete: resolved=%d expired=%d deferred=%d errors=%d",
                result["resolved"],
                result["expired"],
                result["deferred"],
                result["errors"],
            )
            return result
        except Exception:
            logger.exception("Outcome resolution failed")
            raise


@flow(name="outcome_resolution")
async def outcome_resolution_flow() -> dict:
    logger = get_run_logger()

    from app.features.core.database import _init_engine

    _init_engine()

    logger.info("Outcome resolution flow starting")

    try:
        result = await resolve_due_tickets()
    except Exception:
        logger.exception("Outcome resolution flow failed")
        from app.features.core.database import async_session_factory

        async with async_session_factory() as session:
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="FLOW_FAILED",
                message="Outcome resolution flow failed",
            )
        raise

    logger.info(
        "Outcome resolution flow complete: %s",
        result,
    )

    return result
