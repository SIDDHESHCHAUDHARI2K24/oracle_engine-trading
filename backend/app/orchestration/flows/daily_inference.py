"""Daily inference Prefect flow.

Scheduled weekdays ~5:30pm ET — runs inference for every active universe,
writing predictions for the current trading day.

Depends on S2 data refresh + S3 feature compute completing first
(enforced via Prefect's `wait_for` — schedule offset is the
simplest coordination mechanism for v1).
"""

import uuid
from datetime import date

from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(
    name="infer-universe",
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=7_200,
)
async def infer_universe(universe_id: uuid.UUID) -> dict:
    """Run inference for a single universe and persist predictions.

    Isolated task — one universe failing does not abort the others.
    """
    logger = get_run_logger()
    today = date.today()

    from app.features.core.database import async_session_factory
    from app.core.services.artifact_store import get_artifact_store
    from app.features.ml_models.inference_service import run_inference

    logger.info("Inference starting for universe %s...", universe_id)

    async with async_session_factory() as session:
        try:
            store = get_artifact_store()
            result = await run_inference(
                universe_id=universe_id,
                inference_date=today,
                db_session=session,
                artifact_store=store,
            )

            logger.info(
                "Inference complete for universe %s: scored=%d written=%d",
                universe_id,
                result.num_tickers_scored,
                result.num_predictions_written,
            )

            await session.flush()

            return {
                "universe_id": str(universe_id),
                "inference_run_id": str(result.inference_run_id),
                "num_tickers_scored": result.num_tickers_scored,
                "num_predictions_written": result.num_predictions_written,
                "status": result.status,
            }

        except Exception:
            logger.exception("Inference failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="inference_failure",
                message=f"Inference failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {
                "universe_id": str(universe_id),
                "status": "failed",
            }


@task(
    name="filter-emit-tickets",
    retries=1,
    retry_delay_seconds=60,
    timeout_seconds=1_800,
)
async def filter_and_emit_tickets(
    universe_id: uuid.UUID,
    inference_run_id: uuid.UUID,
    inference_date: date,
) -> dict:
    """Filter predictions through the conviction gate and emit tickets.

    Runs after inference completes for a universe.
    """
    logger = get_run_logger()
    logger.info(
        "Filter & emit starting for universe=%s run=%s",
        universe_id, inference_run_id,
    )

    from app.features.core.database import async_session_factory
    from app.features.ml_models.repository import (
        get_predictions_for_date,
        get_inference_run,
    )
    from app.features.backtesting.repository import (
        get_pass_summary,
        get_latest_backtest_run,
    )
    from app.features.conviction_tickets.service import TicketService

    async with async_session_factory() as session:
        try:
            inference_run = await get_inference_run(session, inference_run_id)
            if inference_run is None:
                logger.warning("InferenceRun %s not found", inference_run_id)
                return {"universe_id": str(universe_id), "status": "skipped"}

            predictions = await get_predictions_for_date(
                session, universe_id, inference_date
            )

            if not predictions:
                logger.info(
                    "No predictions for universe=%s date=%s — skipping filter",
                    universe_id, inference_date,
                )
                return {
                    "universe_id": str(universe_id),
                    "status": "skipped",
                    "predictions_evaluated": 0,
                    "tickets_emitted": 0,
                }

            bt_summary = await get_pass_summary(session, universe_id)
            latest_bt_run = await get_latest_backtest_run(session, universe_id)
            backtest_run_id = latest_bt_run.id if latest_bt_run else None

            w_max = {0: 0.05, 1: 0.08, 2: 0.10, 3: 0.12}

            service = TicketService()
            tickets, filter_run = await service.emit_tickets(
                session=session,
                inference_run=inference_run,
                predictions=predictions,
                backtest_metrics=bt_summary,
                w_max=w_max,
                backtest_run_id=backtest_run_id,
            )

            await session.flush()

            logger.info(
                "Filter complete for universe=%s: evaluated=%d emitted=%d",
                universe_id,
                filter_run.num_predictions_evaluated,
                filter_run.num_tickets_emitted,
            )

            return {
                "universe_id": str(universe_id),
                "inference_run_id": str(inference_run_id),
                "predictions_evaluated": filter_run.num_predictions_evaluated,
                "tickets_emitted": filter_run.num_tickets_emitted,
                "status": "completed",
            }

        except Exception:
            logger.exception(
                "Filter & emit failed for universe=%s run=%s",
                universe_id, inference_run_id,
            )
            return {
                "universe_id": str(universe_id),
                "inference_run_id": str(inference_run_id),
                "status": "failed",
            }



@flow(name="daily_inference", log_prints=True)
async def daily_inference_flow() -> dict:
    """Daily inference scheduled weekdays ~5:30pm ET.

    Depends on S2 data refresh + S3 feature compute completing first.
    For each active universe: load active artifacts → run inference →
    persist predictions → filter & emit conviction tickets.
    Per-universe isolation so one failure doesn't abort others.
    """
    logger = get_run_logger()

    from app.features.core.database import async_session_factory, _init_engine
    from app.features.universes.repository import list_universes

    _init_engine()

    async with async_session_factory() as session:
        universes = await list_universes(session, include_deleted=False)
        universe_ids = [u.id for u in universes]
        logger.info(
            "Daily inference starting for %d active universes",
            len(universe_ids),
        )

    results = []
    for uid in universe_ids:
        inf_result = await infer_universe(uid)
        results.append(inf_result)

        if inf_result.get("status") == "completed" and "inference_run_id" in inf_result:
            infer_run_id = uuid.UUID(inf_result["inference_run_id"])
            filter_result = await filter_and_emit_tickets(
                uid, infer_run_id, date.today()
            )
            results.append(filter_result)

    succeeded = sum(
        1 for r in results if r.get("status") == "completed"
    )
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        "Daily inference complete: %d succeeded, %d failed out of %d results",
        succeeded,
        failed,
        len(results),
    )

    return {
        "universes_processed": len(universe_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
