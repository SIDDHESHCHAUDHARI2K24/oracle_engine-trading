"""Tests for backtesting repository — TDD: red → green → refactor."""

from datetime import date
import uuid

import pytest
from app.features.backtesting.repository import (
    complete_backtest_run,
    create_backtest_run,
    get_latest_backtest_run,
    get_latest_metrics_for_ticker,
    get_metrics_for_run,
    get_pass_summary,
    upsert_backtest_metrics,
)
from app.features.universes.models import Ticker, Universe


async def _make_universe(db_session) -> Universe:
    short = uuid.uuid4().hex[:8]
    u = Universe(name=f"test_universe_{short}", display_name=f"Test Universe {short}")
    db_session.add(u)
    await db_session.flush()
    return u


async def _make_ticker(db_session, symbol: str = "AAPL") -> Ticker:
    t = Ticker(symbol=symbol, name=symbol, exchange="NASDAQ", asset_type="equity")
    db_session.add(t)
    await db_session.flush()
    return t


@pytest.mark.asyncio
async def test_create_and_complete_backtest_run(db_session):
    universe = await _make_universe(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )
    assert run.status == "running"
    assert run.universe_id == universe.id
    assert run.triggered_by == "test"

    completed = await complete_backtest_run(
        db_session, run.id, status="completed", num_tickers=10
    )
    assert completed.status == "completed"
    assert completed.num_tickers == 10
    assert completed.completed_at is not None


@pytest.mark.asyncio
async def test_upsert_metrics_idempotent(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )

    metrics = [
        {
            "backtest_run_id": run.id,
            "ticker_id": ticker.id,
            "strategy_name": "mean_reversion",
            "sharpe_ratio": 1.8,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "win_rate": 0.6,
            "profit_factor": 2.0,
            "total_trades": 15,
            "equity_curve": [{"date": "2024-01-02", "value": 100000.0}],
        }
    ]

    count1 = await upsert_backtest_metrics(db_session, metrics)
    assert count1 == 1

    # Re-upsert with different values — should still be 1 row
    metrics[0]["sharpe_ratio"] = 2.1
    count2 = await upsert_backtest_metrics(db_session, metrics)
    assert count2 == 1

    rows = await get_metrics_for_run(db_session, run.id)
    assert len(rows) == 1
    assert rows[0].sharpe_ratio == 2.1


@pytest.mark.asyncio
async def test_get_latest_backtest_run(db_session):
    universe = await _make_universe(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run1 = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )
    await complete_backtest_run(db_session, run1.id, "completed", 5)

    run2 = await create_backtest_run(
        db_session, universe.id, "test2", period_start, period_end
    )
    await complete_backtest_run(db_session, run2.id, "completed", 10)

    latest = await get_latest_backtest_run(db_session, universe.id)
    assert latest is not None
    assert latest.id == run2.id


@pytest.mark.asyncio
async def test_get_metrics_for_run(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )

    metrics = [
        {
            "backtest_run_id": run.id,
            "ticker_id": ticker.id,
            "strategy_name": name,
            "sharpe_ratio": 1.5 + i * 0.1,
            "max_drawdown": -0.1,
            "total_return": 0.2,
            "win_rate": 0.5,
            "profit_factor": 1.5,
            "total_trades": 12,
            "equity_curve": [],
        }
        for i, name in enumerate(["mean_reversion", "momentum_cross", "volatility_breakout", "stat_arb"])
    ]

    await upsert_backtest_metrics(db_session, metrics)
    result = await get_metrics_for_run(db_session, run.id)
    assert len(result) == 4
    assert {m.strategy_name for m in result} == {
        "mean_reversion", "momentum_cross", "volatility_breakout", "stat_arb"
    }


@pytest.mark.asyncio
async def test_get_pass_summary(db_session):
    universe = await _make_universe(db_session)
    ticker1 = await _make_ticker(db_session, "AAPL")
    ticker2 = await _make_ticker(db_session, "MSFT")
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )

    metrics = []
    for ticker in [ticker1, ticker2]:
        for i, name in enumerate(["mean_reversion", "momentum_cross", "volatility_breakout", "stat_arb"]):
            metrics.append({
                "backtest_run_id": run.id,
                "ticker_id": ticker.id,
                "strategy_name": name,
                "sharpe_ratio": 2.0 if i < 3 else 0.5,
                "max_drawdown": -0.2,
                "total_return": 0.3,
                "win_rate": 0.6,
                "profit_factor": 2.0,
                "total_trades": 15,
                "equity_curve": [],
            })

    await upsert_backtest_metrics(db_session, metrics)

    summary = await get_pass_summary(db_session, universe.id, run.id)
    assert len(summary) == 2

    aapl = next(s for s in summary if s["symbol"] == "AAPL")
    msft = next(s for s in summary if s["symbol"] == "MSFT")

    assert aapl["passes"] == 3
    assert not aapl["strategies"]["stat_arb"]
    assert aapl["strategies"]["mean_reversion"]

    assert msft["passes"] == 3


@pytest.mark.asyncio
async def test_get_latest_metrics_for_ticker(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )

    metrics = [
        {
            "backtest_run_id": run.id,
            "ticker_id": ticker.id,
            "strategy_name": "mean_reversion",
            "sharpe_ratio": 1.8,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "win_rate": 0.6,
            "profit_factor": 2.0,
            "total_trades": 15,
            "equity_curve": [],
        }
    ]
    await upsert_backtest_metrics(db_session, metrics)

    result = await get_latest_metrics_for_ticker(db_session, ticker.id, universe.id)
    assert len(result) == 1
    assert result[0].strategy_name == "mean_reversion"
    assert result[0].sharpe_ratio == 1.8


@pytest.mark.asyncio
async def test_upsert_excludes_computed_column(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)
    period_start = date(2024, 1, 1)
    period_end = date(2024, 12, 31)

    run = await create_backtest_run(
        db_session, universe.id, "test", period_start, period_end
    )

    metrics = [
        {
            "backtest_run_id": run.id,
            "ticker_id": ticker.id,
            "strategy_name": "mean_reversion",
            "sharpe_ratio": 1.8,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "win_rate": 0.6,
            "profit_factor": 2.0,
            "total_trades": 15,
            "equity_curve": [],
        }
    ]

    await upsert_backtest_metrics(db_session, metrics)

    rows = await get_metrics_for_run(db_session, run.id)
    assert len(rows) == 1
    assert rows[0].sharpe_ratio == 1.8
    assert rows[0].total_trades == 15
