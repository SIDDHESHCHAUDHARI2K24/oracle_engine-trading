import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.core.database import get_async_session
from app.features.monitoring import repository as monitoring_repo
from app.features.monitoring.schemas import (
    AlertActionResponse,
    CoverageMetricResponse,
    FeatureDriftMetricResponse,
    ModelCardDetail,
    ModelHealthSummary,
    SystemAlertResponse,
)
from app.features.monitoring.service import AlertService

router = APIRouter()


def _get_alert_service() -> AlertService:
    return AlertService()


@router.get("/health", response_model=list[ModelHealthSummary])
async def list_model_health(
    session: AsyncSession = Depends(get_async_session),
):
    from app.features.universes.models import Universe
    from sqlalchemy import select

    result = await session.execute(
        select(Universe).where(Universe.deleted_at.is_(None))
    )
    universes = list(result.scalars().all())

    health_summaries: list[ModelHealthSummary] = []
    for universe in universes:
        open_alerts = await monitoring_repo.list_open_alerts(
            session, universe_id=universe.id
        )
        open_alert_count = len(open_alerts)
        alert_severity = None
        if open_alerts:
            severity_rank = {"critical": 0, "warning": 1, "info": 2}
            open_alerts_sorted = sorted(
                open_alerts, key=lambda a: severity_rank.get(a.severity, 3)
            )
            alert_severity = open_alerts_sorted[0].severity

        coverage_30d = None
        covers = await monitoring_repo.get_recent_coverages(
            session, universe.id, "T5", 30, limit=5
        )
        if covers:
            vals = [
                c.realized_coverage for c in covers if c.realized_coverage is not None
            ]
            if vals:
                coverage_30d = sum(vals) / len(vals)

        health_summaries.append(
            ModelHealthSummary(
                universe_id=universe.id,
                universe_name=universe.display_name or universe.name,
                last_retrain_at=universe.last_retrain_at,
                open_alert_count=open_alert_count,
                alert_severity=alert_severity,
                data_freshness_hours=None,
                conviction_correlation=None,
                coverage_30d=coverage_30d,
            )
        )

    return health_summaries


@router.get("/health/{universe_id}", response_model=ModelCardDetail)
async def get_model_card(
    universe_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    from app.features.universes.models import Universe
    from app.features.ml_models.models import TrainingRun, ModelArtifact
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    result = await session.execute(
        select(Universe).where(
            Universe.id == universe_id, Universe.deleted_at.is_(None)
        )
    )
    universe = result.scalar_one_or_none()
    if universe is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": f"Universe {universe_id} not found",
            },
        )

    runs_result = await session.execute(
        select(TrainingRun)
        .where(TrainingRun.universe_id == universe_id)
        .order_by(TrainingRun.started_at.desc())
        .limit(20)
    )
    runs = list(runs_result.scalars().all())

    artifacts_result = await session.execute(
        select(ModelArtifact)
        .where(
            ModelArtifact.universe_id == universe_id, ModelArtifact.is_active.is_(True)
        )
        .order_by(ModelArtifact.created_at.desc())
        .limit(20)
    )
    artifacts = list(artifacts_result.scalars().all())

    latest_run = runs[0] if runs else None

    open_alerts = await monitoring_repo.list_open_alerts(
        session, universe_id=universe_id
    )
    open_alert_count = len(open_alerts)
    alert_severity = None
    if open_alerts:
        severity_rank = {"critical": 0, "warning": 1, "info": 2}
        open_alerts_sorted = sorted(
            open_alerts, key=lambda a: severity_rank.get(a.severity, 3)
        )
        alert_severity = open_alerts_sorted[0].severity

    coverage_30d: dict[str, float | None] = {}
    coverage_90d: dict[str, float | None] = {}
    for horizon in ("T1", "T5", "T10", "T15"):
        for window_size, target, key in [
            (30, coverage_30d, "coverage_30d"),
            (90, coverage_90d, "coverage_90d"),
        ]:
            covers = await monitoring_repo.get_recent_coverages(
                session, universe_id, horizon, window_size, limit=90
            )
            if covers:
                vals = [
                    c.realized_coverage
                    for c in covers
                    if c.realized_coverage is not None
                ]
                if vals:
                    target[horizon] = sum(vals) / len(vals)
                else:
                    target[horizon] = None
            else:
                target[horizon] = None

    tickets_result = await session.execute(
        select(ConvictionTicket)
        .where(ConvictionTicket.universe_id == universe_id)
        .order_by(ConvictionTicket.created_at.desc())
        .limit(10)
    )
    recent_tickets = list(tickets_result.scalars().all())

    return ModelCardDetail(
        universe_id=universe.id,
        universe_name=universe.display_name or universe.name,
        last_retrain_at=universe.last_retrain_at,
        open_alert_count=open_alert_count,
        alert_severity=alert_severity,
        data_freshness_hours=None,
        training_history=[
            {
                "id": str(r.id),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "status": r.status,
                "validation_metrics": r.validation_metrics,
            }
            for r in runs
        ],
        active_artifacts=[
            {
                "id": str(a.id),
                "model_role": a.model_role,
                "artifact_path": a.artifact_path,
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artifacts
        ],
        validation_metrics=latest_run.validation_metrics if latest_run else None,
        coverage_30d=coverage_30d,
        coverage_90d=coverage_90d,
        recent_tickets=[
            {
                "id": str(t.id),
                "ticker_id": str(t.ticker_id),
                "horizon": t.horizon,
                "direction": t.direction,
                "conviction_score": t.conviction_score,
                "status": t.status,
                "outcome": t.outcome,
                "inference_date": t.inference_date.isoformat()
                if t.inference_date
                else None,
            }
            for t in recent_tickets
        ],
    )


@router.get("/coverage", response_model=list[CoverageMetricResponse])
async def get_coverage(
    universe_id: uuid.UUID,
    horizon: str = "T5",
    window_size: int = 30,
    limit: int = 90,
    session: AsyncSession = Depends(get_async_session),
):
    return await monitoring_repo.get_recent_coverages(
        session, universe_id, horizon, window_size, limit
    )


@router.get("/drift", response_model=list[FeatureDriftMetricResponse])
async def get_drift(
    universe_id: uuid.UUID,
    measurement_date: str | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    from datetime import date as dt_date

    parsed_date = None
    if measurement_date is not None:
        parsed_date = dt_date.fromisoformat(measurement_date)
    return await monitoring_repo.get_recent_drift_metrics(
        session, universe_id, parsed_date
    )


@router.get("/alerts", response_model=list[SystemAlertResponse])
async def list_alerts(
    severity: str | None = None,
    universe_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
):
    alert_service = _get_alert_service()
    return await alert_service.list_open_alerts(session, severity, universe_id)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertActionResponse)
async def acknowledge_alert_endpoint(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    alert_service = _get_alert_service()
    alert = await alert_service.acknowledge_alert(session, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ALERT_NOT_FOUND",
                "message": f"Alert {alert_id} not found",
            },
        )
    return AlertActionResponse(
        message="Alert acknowledged",
        alert=SystemAlertResponse.model_validate(alert),
    )


@router.post("/alerts/{alert_id}/resolve", response_model=AlertActionResponse)
async def resolve_alert_endpoint(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    alert_service = _get_alert_service()
    alert = await alert_service.resolve_alert(session, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ALERT_NOT_FOUND",
                "message": f"Alert {alert_id} not found",
            },
        )
    return AlertActionResponse(
        message="Alert resolved",
        alert=SystemAlertResponse.model_validate(alert),
    )
