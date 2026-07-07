import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.backtesting.models import BacktestRun
from app.features.backtesting.repository import get_pass_summary
from app.features.monitoring.service import AlertService


async def compute_backtest_drift(
    session: AsyncSession,
    universe_id: uuid.UUID,
    alert_service: AlertService | None = None,
) -> dict | None:
    stmt = (
        select(BacktestRun)
        .where(
            BacktestRun.universe_id == universe_id,
            BacktestRun.status == "completed",
        )
        .order_by(BacktestRun.completed_at.desc())
        .limit(2)
    )
    result = await session.execute(stmt)
    runs = list(result.scalars().all())

    if len(runs) < 2:
        return None

    current_run, previous_run = runs[0], runs[1]

    async def _pass_rate(run_id: uuid.UUID) -> tuple[float, int]:
        summary = await get_pass_summary(session, universe_id, run_id)
        if not summary:
            return 0.0, 0
        passed = sum(1 for s in summary if s["passes"] >= 2)
        return passed / len(summary), len(summary)

    current_rate, current_n = await _pass_rate(current_run.id)
    previous_rate, previous_n = await _pass_rate(previous_run.id)

    change_pct = (current_rate - previous_rate) * 100

    result_data = {
        "current_pass_rate": current_rate,
        "previous_pass_rate": previous_rate,
        "change_pct_points": round(change_pct, 4),
        "current_run_id": str(current_run.id),
        "previous_run_id": str(previous_run.id),
        "current_ticker_count": current_n,
        "previous_ticker_count": previous_n,
    }

    if change_pct < -5 and alert_service is not None:
        severity = "warning" if change_pct < -10 else "info"
        await alert_service.raise_alert(
            session,
            severity=severity,
            code="BACKTEST_DRIFT",
            message=f"Backtest pass rate dropped {abs(change_pct):.1f}pp ({previous_rate:.2%} -> {current_rate:.2%})",
            universe_id=universe_id,
            context=result_data,
        )

    return result_data
