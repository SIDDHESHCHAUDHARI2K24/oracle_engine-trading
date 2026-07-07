import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, text

from app.features.conviction_tickets.models import ConvictionTicket


def _make_prediction_row(
    ticker_id,
    universe_id,
    inference_run_id,
    inference_date,
    pred_t1=0.02,
    pred_lo_t1=0.01,
    pred_hi_t1=0.04,
    conviction_t1=80.0,
    pred_t5=0.03,
    pred_lo_t5=0.01,
    pred_hi_t5=0.06,
    conviction_t5=75.0,
    pred_t10=0.01,
    pred_lo_t10=0.00,
    pred_hi_t10=0.03,
    conviction_t10=70.0,
    pred_t15=0.015,
    pred_lo_t15=0.005,
    pred_hi_t15=0.035,
    conviction_t15=68.0,
):
    p = MagicMock()
    p.ticker_id = ticker_id
    p.universe_id = universe_id
    p.inference_run_id = inference_run_id
    p.inference_date = inference_date
    p.pred_t1 = pred_t1
    p.pred_lo_t1 = pred_lo_t1
    p.pred_hi_t1 = pred_hi_t1
    p.conviction_t1 = conviction_t1
    p.pred_t5 = pred_t5
    p.pred_lo_t5 = pred_lo_t5
    p.pred_hi_t5 = pred_hi_t5
    p.conviction_t5 = conviction_t5
    p.pred_t10 = pred_t10
    p.pred_lo_t10 = pred_lo_t10
    p.pred_hi_t10 = pred_hi_t10
    p.conviction_t10 = conviction_t10
    p.pred_t15 = pred_t15
    p.pred_lo_t15 = pred_lo_t15
    p.pred_hi_t15 = pred_hi_t15
    p.conviction_t15 = conviction_t15
    return p


def _make_inference_run(inference_run_id, universe_id, inference_date):
    run = MagicMock()
    run.id = inference_run_id
    run.universe_id = universe_id
    run.inference_date = inference_date
    return run


async def _create_universe(session, name="test_universe"):
    uid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO universes (id, name, display_name, created_at) "
            "VALUES (:id, :name, :dn, now())"
        ),
        {"id": uid, "name": name, "dn": f"Display {name}"},
    )
    return uid


async def _create_ticker(session, symbol="TEST"):
    tid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO tickers (id, symbol, name, created_at, active, exchange, asset_type) "
            "VALUES (:id, :sym, :name, now(), true, 'NYSE', 'equity')"
        ),
        {"id": tid, "sym": symbol, "name": f"Ticker {symbol}"},
    )
    return tid


async def _add_membership(session, universe_id, ticker_id):
    await session.execute(
        text(
            "INSERT INTO universe_memberships (universe_id, ticker_id, added_at) "
            "VALUES (:uid, :tid, now())"
        ),
        {"uid": universe_id, "tid": ticker_id},
    )


async def _seed_ohlcv_bar(session, ticker_id, bar_date, close):
    await session.execute(
        text(
            "INSERT INTO ohlcv_bars (ticker_id, bar_date, open, high, low, close, "
            "adjusted_close, volume, source, created_at) "
            "VALUES (:tid, :bd, :o, :h, :l, :c, :ac, :v, 'test', now())"
        ),
        {
            "tid": ticker_id,
            "bd": bar_date,
            "o": close,
            "h": close,
            "l": close,
            "c": close,
            "ac": close,
            "v": 100000,
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_filter_emit_resolve_cycle(db_session):
    from app.features.conviction_tickets.repository import update_ticket_status
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.service import TicketService

    inference_date = date(2025, 6, 13)

    # 1. SEED UNIVERSE + TICKER + MEMBERSHIP
    universe_id = await _create_universe(db_session, "test_integration")
    ticker_id = await _create_ticker(db_session, "INTEG")
    await _add_membership(db_session, universe_id, ticker_id)
    await db_session.flush()

    # 2. SEED BACKTEST RUN + METRICS (3 of 4 strategies pass)
    bt_run_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO backtest_runs (id, universe_id, triggered_by, "
            "backtest_period_start, backtest_period_end, status, num_strategies, metadata) "
            "VALUES (:id, :uid, 'test', :start, :end, 'completed', 4, '{}'::jsonb)"
        ),
        {
            "id": bt_run_id,
            "uid": universe_id,
            "start": inference_date - timedelta(days=365),
            "end": inference_date,
        },
    )

    strategies_config = [
        ("mean_reversion", True),
        ("momentum_cross", True),
        ("volatility_breakout", True),
        ("stat_arb", False),
    ]
    for strategy_name, passes in strategies_config:
        sharpe = 2.0 if passes else 0.5
        trades = 15 if passes else 3
        drawdown = -0.15 if passes else -0.50
        await db_session.execute(
            text(
                "INSERT INTO backtest_metrics (backtest_run_id, ticker_id, strategy_name, "
                "sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor, total_trades, equity_curve) "
                "VALUES (:bt_rid, :tid, :strat, :sharpe, :dd, 0.25, 0.6, 2.0, :trades, '[]'::jsonb)"
            ),
            {
                "bt_rid": bt_run_id,
                "tid": ticker_id,
                "strat": strategy_name,
                "sharpe": sharpe,
                "dd": drawdown,
                "trades": trades,
            },
        )
    await db_session.flush()

    # 3. SEED INFERENCE RUN
    inf_run_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO inference_runs (id, universe_id, triggered_by, inference_date, status) "
            "VALUES (:id, :uid, :trig, :dt, 'completed')"
        ),
        {"id": inf_run_id, "uid": universe_id, "trig": "test", "dt": inference_date},
    )
    await db_session.flush()

    prediction_row = _make_prediction_row(
        ticker_id,
        universe_id,
        inf_run_id,
        inference_date,
        pred_t1=0.02,
        pred_lo_t1=0.01,
        pred_hi_t1=0.04,
        conviction_t1=80.0,
        pred_t5=0.02,
        pred_lo_t5=0.01,
        pred_hi_t5=0.06,
        conviction_t5=60.0,
        pred_t10=-0.01,
        pred_lo_t10=-0.03,
        pred_hi_t10=0.01,
        conviction_t10=75.0,
        pred_t15=0.015,
        pred_lo_t15=0.005,
        pred_hi_t15=0.035,
        conviction_t15=68.0,
    )
    inference_run = _make_inference_run(inf_run_id, universe_id, inference_date)

    bt_metrics = [
        {
            "ticker_id": str(ticker_id),
            "passes": 3,
            "strategies": {
                "mean_reversion": True,
                "momentum_cross": True,
                "volatility_breakout": True,
                "stat_arb": False,
            },
        }
    ]
    w_max = {0: 0.05, 1: 0.10, 2: 0.10, 3: 0.10}

    # 4. RUN FILTER + EMISSION
    service = TicketService()
    tickets, filter_run = await service.emit_tickets(
        session=db_session,
        inference_run=inference_run,
        predictions=[prediction_row],
        backtest_metrics=bt_metrics,
        w_max=w_max,
        backtest_run_id=bt_run_id,
    )

    assert filter_run is not None
    assert filter_run.num_predictions_evaluated == 4
    assert filter_run.num_tickets_emitted == 2

    t1_ticket = [t for t in tickets if t.horizon == "T1"][0]
    t15_ticket = [t for t in tickets if t.horizon == "T15"][0]

    assert t1_ticket.status == "TRADABLE"
    assert t1_ticket.conviction_score == 80.0
    assert t1_ticket.backtest_passes == 3
    assert t1_ticket.conformal_lower == 0.01
    assert t1_ticket.conformal_upper == 0.04
    assert t1_ticket.direction == "LONG"
    assert t1_ticket.inference_date == inference_date
    assert t1_ticket.horizon == "T1"

    assert t15_ticket.status == "TRADABLE"
    assert t15_ticket.conviction_score == 68.0
    assert t15_ticket.horizon == "T15"

    # Verify filter gate: T5 filtered out by conviction (60 <= 67)
    assert len([t for t in tickets if t.horizon == "T5"]) == 0

    # Verify filter gate: T10 filtered out by direction (negative predicted return)
    assert len([t for t in tickets if t.horizon == "T10"]) == 0

    # 5. TEST LIFECYCLE
    updated = await update_ticket_status(
        db_session, t1_ticket.id, "REVIEWED", user_notes="reviewed ok"
    )
    assert updated.status == "REVIEWED"
    assert updated.user_notes == "reviewed ok"

    updated = await update_ticket_status(
        db_session, t1_ticket.id, "ACTIONED", user_notes="acting now"
    )
    assert updated.status == "ACTIONED"
    assert updated.user_notes == "acting now"

    # 6. SEED OHLCV BARS
    resolution_dates = {t.horizon: t.resolution_date for t in tickets}
    await _seed_ohlcv_bar(db_session, ticker_id, inference_date, 100.0)
    for horizon_label, res_date in resolution_dates.items():
        await _seed_ohlcv_bar(db_session, ticker_id, res_date, 110.0)
    await db_session.flush()

    # 7. RUN RESOLUTION
    max_res_date = max(t.resolution_date for t in tickets)
    result = await resolve_tickets(db_session, as_of_date=max_res_date)

    assert result["resolved"] == 1
    stmt = select(ConvictionTicket).where(ConvictionTicket.id == t1_ticket.id)
    t1 = (await db_session.execute(stmt)).scalar_one()
    assert t1.actual_return == pytest.approx(0.10)
    assert t1.outcome == "win"
    assert t1.status == "RESOLVED"

    stmt = select(ConvictionTicket).where(ConvictionTicket.id == t15_ticket.id)
    t15 = (await db_session.execute(stmt)).scalar_one()
    assert t15.outcome == "win"
    assert t15.status == "EXPIRED"

    # 8. TEST IDEMPOTENCY
    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    tickets_after_first = list((await db_session.execute(stmt)).scalars().all())
    first_count = len(tickets_after_first)

    tickets2, fr2 = await service.emit_tickets(
        session=db_session,
        inference_run=inference_run,
        predictions=[prediction_row],
        backtest_metrics=bt_metrics,
        w_max=w_max,
        backtest_run_id=bt_run_id,
    )

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    tickets_after_second = list((await db_session.execute(stmt)).scalars().all())
    assert len(tickets_after_second) == first_count

    result2 = await resolve_tickets(db_session, as_of_date=max_res_date)
    assert result2["resolved"] == 0
    assert result2["expired"] == 0
    assert result2["deferred"] == 0

    stmt = select(ConvictionTicket).where(ConvictionTicket.id == t1_ticket.id)
    t1_final = (await db_session.execute(stmt)).scalar_one()
    assert t1_final.status == "RESOLVED"
    assert t1_final.outcome == "win"
    assert t1_final.actual_return == pytest.approx(0.10)
