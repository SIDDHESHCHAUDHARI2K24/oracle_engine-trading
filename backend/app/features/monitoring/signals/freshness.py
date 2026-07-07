import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.core.services.prefect_client import get_recent_runs
from app.features.data_ingestion.models import IngestRun
from app.features.monitoring.service import AlertService


async def compute_freshness(
    session: AsyncSession,
    universe_id: uuid.UUID | None = None,
    alert_service: AlertService | None = None,
    max_hours_stale: int = 36,
) -> dict | None:
    stmt = select(func.max(IngestRun.completed_at)).where(
        IngestRun.status == "succeeded"
    )
    result = await session.execute(stmt)
    last_completed = result.scalar_one_or_none()

    if last_completed is None:
        no_data_result = {
            "last_successful_ingest": None,
            "hours_since": None,
            "stale": True,
        }
        if alert_service is not None:
            await alert_service.raise_alert(
                session,
                severity="critical",
                code="INGEST_STALE",
                message="No successful ingest run found",
                universe_id=universe_id,
                context=no_data_result,
            )
        return no_data_result

    now = datetime.now(timezone.utc)
    hours_since = (now - last_completed).total_seconds() / 3600
    stale = hours_since > max_hours_stale

    result_data: dict[str, object] = {
        "last_successful_ingest": last_completed.isoformat(),
        "hours_since": round(hours_since, 2),
        "stale": stale,
    }

    if stale and alert_service is not None:
        await alert_service.raise_alert(
            session,
            severity="critical",
            code="INGEST_STALE",
            message=f"Ingest is stale: last successful run was {hours_since:.1f}h ago (threshold: {max_hours_stale}h)",
            universe_id=universe_id,
            context=result_data,
        )

    return result_data


async def compute_pipeline_success(
    session: AsyncSession | None = None,
    alert_service: AlertService | None = None,
    lookback_hours: int = 168,
    success_threshold: float = 0.95,
) -> dict | None:
    runs = await get_recent_runs(limit=100)

    if not runs:
        empty_result = {
            "total_runs": 0,
            "success_rate": None,
            "trigger_alert": False,
        }
        return empty_result

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=lookback_hours)

    recent_runs = []
    for run in runs:
        start_time_str = run.get("start_time")
        if start_time_str is not None:
            start_time = datetime.fromisoformat(start_time_str)
            if start_time >= cutoff:
                recent_runs.append(run)

    if not recent_runs:
        empty_recent = {
            "total_runs": 0,
            "success_rate": None,
            "trigger_alert": False,
        }
        return empty_recent

    succeeded = sum(1 for r in recent_runs if r.get("state", "").upper() == "COMPLETED")
    total = len(recent_runs)
    success_rate = succeeded / total

    trigger = success_rate < success_threshold

    result_data: dict[str, object] = {
        "total_runs": total,
        "succeeded_runs": succeeded,
        "success_rate": round(success_rate, 4),
        "threshold": success_threshold,
        "trigger_alert": trigger,
    }

    if trigger and alert_service is not None and session is not None:
        await alert_service.raise_alert(
            session,
            severity="warning",
            code="PIPELINE_SUCCESS_LOW",
            message=f"Pipeline success rate {success_rate:.1%} below {success_threshold:.0%} threshold ({succeeded}/{total} runs in last {lookback_hours}h)",
            context=result_data,
        )

    return result_data
