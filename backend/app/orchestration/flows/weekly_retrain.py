"""Weekly retrain Prefect flow.

Scheduled Sundays ~6am ET — retrains models for every active universe,
promotes challenger artifacts if they outperform the champion.
"""

import uuid
from datetime import date

from prefect import flow, task
from prefect.logging import get_run_logger

from app.features.monitoring.service import AlertService


@task(
    name="retrain-universe",
    retries=1,
    retry_delay_seconds=120,
    timeout_seconds=14_400,
)
async def retrain_universe(universe_id: uuid.UUID) -> dict:
    """Train a single universe and attempt champion/challenger promotion.

    Isolated task — one universe failing does not abort the others.
    """
    logger = get_run_logger()
    today = date.today()

    from app.features.core.database import async_session_factory
    from app.core.services.artifact_store import get_artifact_store
    from app.features.ml_models.service import train_universe
    from app.features.ml_models.promotion import promote_challenger

    logger.info("Retraining universe %s starting...", universe_id)

    async with async_session_factory() as session:
        try:
            store = get_artifact_store()
            result = await train_universe(
                universe_id=universe_id,
                as_of_date=today,
                db_session=session,
                artifact_store=store,
            )

            logger.info(
                "Training completed for universe %s: status=%s run=%s",
                universe_id,
                result.status,
                result.training_run_id,
            )

            if result.status == "completed" and result.artifact_ids:
                from app.features.ml_models.artifact_service import (
                    ArtifactLifecycleService,
                )

                lifecycle = ArtifactLifecycleService(store)
                promoted, reason = await promote_challenger(
                    session=session,
                    artifact_service=lifecycle,
                    challenger_artifact_ids=result.artifact_ids,
                    challenger_metrics=result.validation_metrics,
                    universe_id=universe_id,
                )
                logger.info(
                    "Promotion for universe %s: promoted=%s reason=%s",
                    universe_id,
                    promoted,
                    reason,
                )

            await session.flush()

            return {
                "universe_id": str(universe_id),
                "training_run_id": str(result.training_run_id),
                "validation_metrics": result.validation_metrics,
                "status": result.status,
            }

        except Exception:
            logger.exception("Retrain failed for universe %s", universe_id)
            await AlertService().raise_alert(
                session,
                severity="critical",
                code="retrain_failure",
                message=f"Retrain failed for universe {universe_id}",
                universe_id=universe_id,
            )
            return {
                "universe_id": str(universe_id),
                "status": "failed",
            }


@flow(name="weekly_retrain", log_prints=True)
async def weekly_retrain_flow() -> dict:
    """Weekly retrain scheduled Sundays ~6am ET.

    For each active universe: retrain → promote if better.
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
            "Weekly retrain starting for %d active universes",
            len(universe_ids),
        )

    results = []
    for uid in universe_ids:
        result = await retrain_universe(uid)
        results.append(result)

    succeeded = sum(1 for r in results if r.get("status") == "completed")
    failed = sum(1 for r in results if r.get("status") == "failed")

    logger.info(
        "Weekly retrain complete: %d succeeded, %d failed out of %d universes",
        succeeded,
        failed,
        len(results),
    )

    return {
        "universes_processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
