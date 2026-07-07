import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.monitoring.models import (
    CoverageMetric,
    FeatureDriftMetric,
    SystemAlert,
)


async def upsert_coverage_metric(
    session: AsyncSession,
    universe_id: uuid.UUID,
    horizon: str,
    measurement_date: date,
    window_size: int,
    realized_coverage: float | None,
    num_tickets_resolved: int | None,
    is_alert: bool = False,
) -> CoverageMetric:
    stmt = (
        pg_insert(CoverageMetric)
        .values(
            universe_id=universe_id,
            horizon=horizon,
            measurement_date=measurement_date,
            window_size=window_size,
            realized_coverage=realized_coverage,
            num_tickets_resolved=num_tickets_resolved,
            is_alert=is_alert,
        )
        .on_conflict_do_update(
            index_elements=[
                "universe_id",
                "horizon",
                "measurement_date",
                "window_size",
            ],
            set_={
                "realized_coverage": realized_coverage,
                "num_tickets_resolved": num_tickets_resolved,
                "is_alert": is_alert,
                "computed_at": datetime.now(timezone.utc),
            },
        )
        .returning(CoverageMetric)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.scalar_one()


async def get_recent_coverages(
    session: AsyncSession,
    universe_id: uuid.UUID,
    horizon: str,
    window_size: int,
    limit: int = 90,
) -> list[CoverageMetric]:
    result = await session.execute(
        select(CoverageMetric)
        .where(
            CoverageMetric.universe_id == universe_id,
            CoverageMetric.horizon == horizon,
            CoverageMetric.window_size == window_size,
        )
        .order_by(CoverageMetric.measurement_date.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def upsert_drift_metric(
    session: AsyncSession,
    universe_id: uuid.UUID,
    feature_name: str,
    measurement_date: date,
    kl_divergence: float | None,
    threshold_breached: bool = False,
    training_run_id: uuid.UUID | None = None,
) -> FeatureDriftMetric:
    metric = FeatureDriftMetric(
        universe_id=universe_id,
        feature_name=feature_name,
        measurement_date=measurement_date,
        kl_divergence=kl_divergence,
        threshold_breached=threshold_breached,
        training_run_id=training_run_id,
    )
    session.add(metric)
    await session.flush()
    return metric


async def get_recent_drift_metrics(
    session: AsyncSession,
    universe_id: uuid.UUID,
    measurement_date: date | None = None,
    limit: int = 500,
) -> list[FeatureDriftMetric]:
    stmt = select(FeatureDriftMetric).where(
        FeatureDriftMetric.universe_id == universe_id
    )
    if measurement_date is not None:
        stmt = stmt.where(FeatureDriftMetric.measurement_date == measurement_date)
    stmt = stmt.order_by(FeatureDriftMetric.kl_divergence.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_alert(
    session: AsyncSession,
    severity: str,
    code: str,
    message: str,
    universe_id: uuid.UUID | None = None,
    context: dict | None = None,
) -> SystemAlert:
    alert = SystemAlert(
        severity=severity,
        code=code,
        message=message,
        universe_id=universe_id,
        context=context or {},
    )
    session.add(alert)
    await session.flush()
    return alert


async def find_open_alert(
    session: AsyncSession,
    code: str,
    universe_id: uuid.UUID | None = None,
) -> SystemAlert | None:
    stmt = select(SystemAlert).where(
        SystemAlert.code == code,
        SystemAlert.resolved_at.is_(None),
    )
    if universe_id is not None:
        stmt = stmt.where(SystemAlert.universe_id == universe_id)
    else:
        stmt = stmt.where(SystemAlert.universe_id.is_(None))
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def update_alert_context(
    session: AsyncSession,
    alert_id: uuid.UUID,
    context: dict,
) -> SystemAlert | None:
    alert = await session.get(SystemAlert, alert_id)
    if alert is None:
        return None
    alert.context = {**alert.context, **context}
    await session.flush()
    return alert


async def acknowledge_alert(
    session: AsyncSession,
    alert_id: uuid.UUID,
) -> SystemAlert | None:
    alert = await session.get(SystemAlert, alert_id)
    if alert is None:
        return None
    alert.acknowledged_at = datetime.now(timezone.utc)
    await session.flush()
    return alert


async def resolve_alert(
    session: AsyncSession,
    alert_id: uuid.UUID,
) -> SystemAlert | None:
    alert = await session.get(SystemAlert, alert_id)
    if alert is None:
        return None
    alert.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return alert


async def list_open_alerts(
    session: AsyncSession,
    severity: str | None = None,
    universe_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[SystemAlert]:
    stmt = select(SystemAlert).where(SystemAlert.resolved_at.is_(None))
    if severity is not None:
        stmt = stmt.where(SystemAlert.severity == severity)
    if universe_id is not None:
        stmt = stmt.where(SystemAlert.universe_id == universe_id)
    stmt = stmt.order_by(SystemAlert.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_open_alert_count(
    session: AsyncSession,
    universe_id: uuid.UUID | None = None,
) -> int:
    stmt = select(func.count(SystemAlert.id)).where(SystemAlert.resolved_at.is_(None))
    if universe_id is not None:
        stmt = stmt.where(SystemAlert.universe_id == universe_id)
    result = await session.execute(stmt)
    return result.scalar() or 0
