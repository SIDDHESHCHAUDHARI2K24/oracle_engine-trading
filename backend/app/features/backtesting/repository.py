"""Backtesting persistence layer.

Module-level async functions following the same pattern as
feature_engineering/repository.py.
"""

from datetime import date, datetime, timezone
import uuid

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.backtesting.models import BacktestRun, BacktestMetrics


async def create_backtest_run(
    session: AsyncSession,
    universe_id: uuid.UUID,
    triggered_by: str,
    period_start: date,
    period_end: date,
) -> BacktestRun:
    run = BacktestRun(
        universe_id=universe_id,
        triggered_by=triggered_by,
        backtest_period_start=period_start,
        backtest_period_end=period_end,
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def complete_backtest_run(
    session: AsyncSession,
    run_id: uuid.UUID,
    status: str,
    num_tickers: int,
    error: str | None = None,
) -> BacktestRun:
    run = await session.get(BacktestRun, run_id)
    if run is None:
        raise ValueError(f"BacktestRun {run_id} not found")
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    run.num_tickers = num_tickers
    if error:
        run.metadata_ = {**(run.metadata_ or {}), "error": error}
    await session.flush()
    return run


async def upsert_backtest_metrics(
    session: AsyncSession,
    records: list[dict],
) -> int:
    if not records:
        return 0

    metric_columns = {
        "backtest_run_id",
        "ticker_id",
        "strategy_name",
        "sharpe_ratio",
        "max_drawdown",
        "total_return",
        "win_rate",
        "profit_factor",
        "total_trades",
        "equity_curve",
    }
    clean = [{k: v for k, v in r.items() if k in metric_columns} for r in records]

    stmt = pg_insert(BacktestMetrics).values(clean)
    update_cols = {
        "sharpe_ratio": stmt.excluded.sharpe_ratio,
        "max_drawdown": stmt.excluded.max_drawdown,
        "total_return": stmt.excluded.total_return,
        "win_rate": stmt.excluded.win_rate,
        "profit_factor": stmt.excluded.profit_factor,
        "total_trades": stmt.excluded.total_trades,
        "equity_curve": stmt.excluded.equity_curve,
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["backtest_run_id", "ticker_id", "strategy_name"],
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.flush()
    return len(clean)


async def get_latest_backtest_run(
    session: AsyncSession,
    universe_id: uuid.UUID,
) -> BacktestRun | None:
    stmt = (
        select(BacktestRun)
        .where(BacktestRun.universe_id == universe_id)
        .order_by(BacktestRun.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_metrics_for_run(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> list[BacktestMetrics]:
    stmt = select(BacktestMetrics).where(BacktestMetrics.backtest_run_id == run_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_latest_metrics_for_ticker(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    universe_id: uuid.UUID | None = None,
) -> list[BacktestMetrics]:
    sub = (
        select(BacktestMetrics.backtest_run_id)
        .join(BacktestRun, BacktestRun.id == BacktestMetrics.backtest_run_id)
        .where(BacktestMetrics.ticker_id == ticker_id)
    )
    if universe_id is not None:
        sub = sub.where(BacktestRun.universe_id == universe_id)
    sub = sub.order_by(BacktestRun.created_at.desc()).limit(1).scalar_subquery()

    stmt = select(BacktestMetrics).where(BacktestMetrics.backtest_run_id == sub)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_pass_summary(
    session: AsyncSession,
    universe_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
) -> list[dict]:
    if run_id is None:
        latest = await get_latest_backtest_run(session, universe_id)
        if latest is None:
            return []
        run_id = latest.id

    stmt = text(
        """
        SELECT
            bm.ticker_id,
            t.symbol,
            COUNT(*) FILTER (WHERE bm.passed = TRUE) AS passes,
            jsonb_object_agg(bm.strategy_name, bm.passed) AS strategies
        FROM backtest_metrics bm
        JOIN tickers t ON t.id = bm.ticker_id
        WHERE bm.backtest_run_id = :run_id
        GROUP BY bm.ticker_id, t.symbol
        ORDER BY t.symbol
        """
    )
    result = await session.execute(stmt, {"run_id": run_id})
    return [
        {
            "ticker_id": str(row.ticker_id),
            "symbol": row.symbol,
            "passes": row.passes,
            "strategies": dict(row.strategies),
        }
        for row in result.fetchall()
    ]
