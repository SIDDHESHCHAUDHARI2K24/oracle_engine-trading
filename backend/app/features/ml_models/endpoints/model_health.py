"""Model health API endpoints — model card, training history, artifacts, rollback, retrain, infer."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from prefect.client.orchestration import get_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.artifact_store import ArtifactStore, get_artifact_store
from app.features.auth.dependencies import get_current_user, requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.ml_models import repository as ml_repo
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.schemas import (
    ArtifactListResponse,
    ModelArtifactResponse,
    TrainingHistoryResponse,
    TrainingRunResponse,
    TriggerInferenceResponse,
    TriggerRetrainResponse,
)

model_health_router = APIRouter()

ADMIN = requires_role(["admin"])


def _training_run_to_response(run) -> TrainingRunResponse:
    return TrainingRunResponse(
        id=str(run.id),
        universe_id=str(run.universe_id),
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        status=run.status,
        train_window_start=run.train_window_start,
        train_window_end=run.train_window_end,
        calibration_window_start=run.calibration_window_start,
        calibration_window_end=run.calibration_window_end,
        validation_window_start=run.validation_window_start,
        validation_window_end=run.validation_window_end,
        num_tickers=run.num_tickers,
        num_training_samples=run.num_training_samples,
        hyperparams_snapshot=run.hyperparams_snapshot,
        validation_metrics=run.validation_metrics,
        error_summary=run.error_summary,
    )


def _artifact_to_response(a) -> ModelArtifactResponse:
    return ModelArtifactResponse(
        id=str(a.id),
        universe_id=str(a.universe_id),
        training_run_id=str(a.training_run_id),
        model_role=a.model_role,
        artifact_path=a.artifact_path,
        size_bytes=a.size_bytes,
        is_active=a.is_active,
        metadata=a.model_metadata,
        created_at=a.created_at,
        archived_at=a.archived_at,
    )


@model_health_router.get(
    "/{universe_id}",
    response_model=TrainingRunResponse,
)
async def get_model_card(
    universe_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    run = await ml_repo.get_latest_training_run(db, universe_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "TRAINING_RUN_NOT_FOUND",
                "message": f"No training runs found for universe {universe_id}",
            },
        )
    return _training_run_to_response(run)


@model_health_router.get(
    "/{universe_id}/training-history",
    response_model=TrainingHistoryResponse,
)
async def get_training_history(
    universe_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    runs = await ml_repo.get_training_history(db, universe_id)
    return TrainingHistoryResponse(
        universe_id=str(universe_id),
        runs=[_training_run_to_response(r) for r in runs],
    )


@model_health_router.get(
    "/{universe_id}/artifacts",
    response_model=ArtifactListResponse,
)
async def get_artifacts(
    universe_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    artifacts = await ml_repo.get_artifacts_for_universe(db, universe_id)
    return ArtifactListResponse(
        universe_id=str(universe_id),
        artifacts=[_artifact_to_response(a) for a in artifacts],
    )


@model_health_router.post(
    "/{universe_id}/artifacts/{artifact_id}/rollback",
    response_model=ModelArtifactResponse,
)
async def rollback_artifact(
    universe_id: uuid.UUID,
    artifact_id: uuid.UUID,
    _user: User = Depends(ADMIN),
    db: AsyncSession = Depends(get_async_session),
    store: ArtifactStore = Depends(get_artifact_store),
):
    lifecycle = ArtifactLifecycleService(store)
    try:
        artifact = await lifecycle.activate(db, artifact_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "ARTIFACT_NOT_FOUND",
                "message": str(exc),
            },
        )
    return _artifact_to_response(artifact)


@model_health_router.post(
    "/{universe_id}/retrain",
    response_model=TriggerRetrainResponse,
)
async def trigger_retrain(
    universe_id: uuid.UUID,
    _user: User = Depends(ADMIN),
):
    try:
        async with get_client() as client:
            deployment = await client.read_deployment_by_name("weekly-retrain")
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters={"universe_ids": [str(universe_id)]},
            )
            return TriggerRetrainResponse(
                message=f"Retrain triggered for universe {universe_id}",
                deployment_id=str(flow_run.id),
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "PREFECT_TRIGGER_FAILED",
                "message": f"Failed to trigger retrain: {exc}",
            },
        )


@model_health_router.post(
    "/{universe_id}/infer",
    response_model=TriggerInferenceResponse,
)
async def trigger_inference(
    universe_id: uuid.UUID,
    _user: User = Depends(ADMIN),
):
    try:
        async with get_client() as client:
            deployment = await client.read_deployment_by_name("daily-inference")
            flow_run = await client.create_flow_run_from_deployment(
                deployment_id=deployment.id,
                parameters={"universe_ids": [str(universe_id)]},
            )
            return TriggerInferenceResponse(
                message=f"Inference triggered for universe {universe_id}",
                deployment_id=str(flow_run.id),
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "PREFECT_TRIGGER_FAILED",
                "message": f"Failed to trigger inference: {exc}",
            },
        )
