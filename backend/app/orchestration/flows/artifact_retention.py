from datetime import datetime, timedelta, timezone

from prefect import flow
from prefect.logging import get_run_logger
from sqlalchemy import select

from app.features.ml_models.models import ModelArtifact


@flow(name="artifact_retention", log_prints=True)
async def artifact_retention_flow() -> dict:
    logger = get_run_logger()
    logger.info("Starting artifact retention reaper")

    from app.core.services.artifact_store import get_artifact_store
    from app.features.core.database import _init_engine, async_session_factory

    _init_engine()

    cutoff = datetime.now(timezone.utc) - timedelta(days=182)
    store = get_artifact_store()

    async with async_session_factory() as session:
        result = await session.execute(
            select(ModelArtifact).where(
                ModelArtifact.is_active.is_(False),
                ModelArtifact.created_at < cutoff,
                ModelArtifact.archived_at.is_(None),
            )
        )
        artifacts = list(result.scalars().all())

        deleted_count = 0
        for artifact in artifacts:
            try:
                store.delete(artifact.artifact_path)
                artifact.archived_at = datetime.now(timezone.utc)
                deleted_count += 1
            except Exception:
                logger.exception(
                    "Failed to delete artifact %s at %s",
                    artifact.id,
                    artifact.artifact_path,
                )

        await session.flush()

    logger.info(
        "Artifact retention complete: %d files deleted out of %d candidates",
        deleted_count,
        len(artifacts),
    )

    return {"candidates": len(artifacts), "deleted": deleted_count}
