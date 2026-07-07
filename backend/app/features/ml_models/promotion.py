import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.models import ModelArtifact, TrainingRun

logger = logging.getLogger(__name__)


async def _get_champion_metrics(
    session: AsyncSession,
    universe_id: uuid.UUID,
) -> dict | None:
    active_artifact = await session.execute(
        select(ModelArtifact.training_run_id)
        .where(
            ModelArtifact.universe_id == universe_id,
            ModelArtifact.is_active.is_(True),
        )
        .limit(1)
    )
    active_row = active_artifact.first()
    if active_row is None:
        return None

    training_run_id = active_row[0]
    run_metrics = await session.execute(
        select(TrainingRun.validation_metrics)
        .where(
            TrainingRun.id == training_run_id,
            TrainingRun.status == "completed",
            TrainingRun.validation_metrics.isnot(None),
        )
    )
    row = run_metrics.first()
    return row[0] if row else None


def _best_metric(metrics: dict) -> float:
    overall = metrics.get("overall_mse")
    if overall is not None:
        return float(overall)
    key = next(iter(metrics), None)
    if key is not None and isinstance(metrics[key], dict):
        mse = metrics[key].get("mse")
        if mse is not None:
            return float(mse)
    return float("inf")


async def promote_challenger(
    session: AsyncSession,
    artifact_service: ArtifactLifecycleService,
    challenger_artifact_ids: list[uuid.UUID],
    challenger_metrics: dict,
    universe_id: uuid.UUID,
    promotion_margin: float = 0.02,
) -> tuple[bool, str]:
    if not challenger_artifact_ids:
        return False, "no challenger artifacts provided"

    champion_metrics = await _get_champion_metrics(session, universe_id)

    if champion_metrics is None:
        await artifact_service.activate_all(session, challenger_artifact_ids)
        await session.flush()
        return True, "no champion exists — auto-promoted challenger"

    challenger_score = _best_metric(challenger_metrics)
    champion_score = _best_metric(champion_metrics)

    relative_improvement = (champion_score - challenger_score) / max(champion_score, 1e-12)

    if relative_improvement >= promotion_margin:
        await artifact_service.activate_all(session, challenger_artifact_ids)
        await session.flush()
        return True, (
            f"challenger promoted: champion_mse={champion_score:.6f}, "
            f"challenger_mse={challenger_score:.6f}, "
            f"improvement={relative_improvement:.4f} >= margin={promotion_margin}"
        )
    else:
        now = datetime.now(timezone.utc)
        for artifact_id in challenger_artifact_ids:
            artifact = await session.get(ModelArtifact, artifact_id)
            if artifact is not None and not artifact.is_active:
                artifact.archived_at = now
                artifact.model_metadata = {
                    **(artifact.model_metadata or {}),
                    "archive_reason": (
                        f"rejected: champion_mse={champion_score:.6f}, "
                        f"challenger_mse={challenger_score:.6f}, "
                        f"improvement={relative_improvement:.4f} < margin={promotion_margin}"
                    ),
                }
        await session.flush()
        return False, (
            f"challenger rejected: champion_mse={champion_score:.6f}, "
            f"challenger_mse={challenger_score:.6f}, "
            f"improvement={relative_improvement:.4f} < margin={promotion_margin}"
        )
