import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.artifact_store import ArtifactStore
from app.features.ml_models.models import ModelArtifact


MODEL_ROLES = (
    "lstm",
    "tft_t1",
    "tft_t5",
    "tft_t10",
    "tft_t15",
    "conformal",
    "residual_predictor",
)


class ArtifactLifecycleService:
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store

    def _build_key(
        self,
        universe_slug: str,
        model_role: str,
        training_run_id: uuid.UUID,
    ) -> str:
        return f"{universe_slug}/{model_role}/{training_run_id}.pt"

    async def save_artifact(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        universe_slug: str,
        model_role: str,
        training_run_id: uuid.UUID,
        data: bytes,
    ) -> ModelArtifact:
        if model_role not in MODEL_ROLES:
            raise ValueError(
                f"Invalid model_role: {model_role}. Must be one of {MODEL_ROLES}"
            )

        key = self._build_key(universe_slug, model_role, training_run_id)
        self._store.put(key, data)

        artifact = ModelArtifact(
            universe_id=universe_id,
            training_run_id=training_run_id,
            model_role=model_role,
            artifact_path=key,
            size_bytes=len(data),
            is_active=False,
        )
        session.add(artifact)
        await session.flush()
        return artifact

    async def activate(
        self,
        session: AsyncSession,
        artifact_id: uuid.UUID,
    ) -> ModelArtifact:
        artifact = await session.get(ModelArtifact, artifact_id)
        if artifact is None:
            raise ValueError(f"Artifact {artifact_id} not found")

        current_champion = await session.execute(
            select(ModelArtifact)
            .where(
                ModelArtifact.universe_id == artifact.universe_id,
                ModelArtifact.model_role == artifact.model_role,
                ModelArtifact.is_active.is_(True),
            )
            .with_for_update()
        )
        current_champion = current_champion.scalar_one_or_none()  # type: ignore[assignment]

        if current_champion is not None:
            current_champion.is_active = False  # type: ignore[attr-defined]
            current_champion.archived_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]
            await session.flush()

        artifact.is_active = True
        artifact.archived_at = None
        await session.flush()
        return artifact

    async def activate_all(
        self,
        session: AsyncSession,
        artifact_ids: list[uuid.UUID],
    ) -> list[ModelArtifact]:
        results: list[ModelArtifact] = []
        for aid in artifact_ids:
            results.append(await self.activate(session, aid))
        return results

    async def load_active(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        model_role: str,
    ) -> bytes:
        result = await session.execute(
            select(ModelArtifact).where(
                ModelArtifact.universe_id == universe_id,
                ModelArtifact.model_role == model_role,
                ModelArtifact.is_active.is_(True),
            )
        )
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise ValueError(
                f"No active artifact for universe={universe_id} role={model_role}"
            )
        return self._store.get(artifact.artifact_path)

    async def archive_old(
        self,
        session: AsyncSession,
        cutoff: datetime,
    ) -> int:
        result = await session.execute(
            update(ModelArtifact)
            .where(
                ModelArtifact.is_active.is_(False),
                ModelArtifact.archived_at.is_(None),
                ModelArtifact.created_at < cutoff,
            )
            .values(archived_at=datetime.now(timezone.utc))
        )
        await session.flush()
        return result.rowcount  # type: ignore[attr-defined,union-attr]

    async def get_active_artifacts(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
    ) -> list[ModelArtifact]:
        result = await session.execute(
            select(ModelArtifact).where(
                ModelArtifact.universe_id == universe_id,
                ModelArtifact.is_active.is_(True),
            )
        )
        return list(result.scalars().all())
