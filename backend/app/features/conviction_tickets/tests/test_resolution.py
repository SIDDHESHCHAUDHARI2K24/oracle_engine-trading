import uuid
from datetime import date

import pytest
from sqlalchemy import text


async def _seed_universe(db_session, universe_id, name):
    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, display_name, created_at) "
            "VALUES (:id, :name, :dn, now())"
        ),
        {"id": universe_id, "name": name, "dn": f"Display {name}"},
    )


async def _seed_ticker(db_session, ticker_id, symbol):
    await db_session.execute(
        text(
            "INSERT INTO tickers (id, symbol, name, created_at, active) "
            "VALUES (:id, :sym, :name, now(), true)"
        ),
        {"id": ticker_id, "sym": symbol, "name": f"Ticker {symbol}"},
    )


async def _seed_inference_run(db_session, inf_run_id, universe_id, dt):
    await db_session.execute(
        text(
            "INSERT INTO inference_runs (id, universe_id, triggered_by, inference_date, status) "
            "VALUES (:id, :uid, :trig, :dt, 'completed')"
        ),
        {"id": inf_run_id, "uid": universe_id, "trig": "test", "dt": dt},
    )


async def _seed_ohlcv_bar(db_session, ticker_id, bar_date, close):
    await db_session.execute(
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


async def _seed_ticket(db_session, ticket_dict):
    await db_session.execute(
        text(
            "INSERT INTO conviction_tickets (inference_run_id, ticker_id, universe_id, "
            "inference_date, horizon, direction, predicted_return, conviction_score, "
            "conformal_lower, conformal_upper, conformal_alpha, backtest_passes, "
            "backtest_pass_strategies, status, resolution_date) "
            "VALUES (:inference_run_id, :ticker_id, :universe_id, :inference_date, "
            ":horizon, :direction, :predicted_return, :conviction_score, "
            ":conformal_lower, :conformal_upper, :conformal_alpha, :backtest_passes, "
            ":backtest_pass_strategies, :status, :resolution_date)"
        ),
        {
            "inference_run_id": ticket_dict["inference_run_id"],
            "ticker_id": ticket_dict["ticker_id"],
            "universe_id": ticket_dict["universe_id"],
            "inference_date": ticket_dict["inference_date"],
            "horizon": ticket_dict["horizon"],
            "direction": ticket_dict["direction"],
            "predicted_return": ticket_dict["predicted_return"],
            "conviction_score": ticket_dict["conviction_score"],
            "conformal_lower": ticket_dict["conformal_lower"],
            "conformal_upper": ticket_dict["conformal_upper"],
            "conformal_alpha": ticket_dict.get("conformal_alpha", 0.10),
            "backtest_passes": ticket_dict["backtest_passes"],
            "backtest_pass_strategies": ticket_dict["backtest_pass_strategies"],
            "status": ticket_dict["status"],
            "resolution_date": ticket_dict["resolution_date"],
        },
    )


@pytest.mark.asyncio
async def test_resolution_wins_when_price_goes_up(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-win")
    await _seed_ticker(db_session, ticker_id, "WIN")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ohlcv_bar(db_session, ticker_id, res_date, 110.0)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.02,
        "conviction_score": 80.0,
        "conformal_lower": 0.01,
        "conformal_upper": 0.04,
        "backtest_passes": 3,
        "backtest_pass_strategies": ["mac"],
        "status": "REVIEWED",
        "resolution_date": res_date,
    })
    await db_session.flush()

    result = await resolve_tickets(db_session, as_of_date=res_date)
    assert result["resolved"] == 1
    assert result["expired"] == 0
    assert result["deferred"] == 0

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    ticket = (await db_session.execute(stmt)).scalar_one()
    assert ticket.outcome == "win"
    assert ticket.actual_return == pytest.approx(0.10)
    assert ticket.status == "RESOLVED"


@pytest.mark.asyncio
async def test_resolution_losses_when_price_goes_down(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-loss")
    await _seed_ticker(db_session, ticker_id, "LOSS")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ohlcv_bar(db_session, ticker_id, res_date, 95.0)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.02,
        "conviction_score": 80.0,
        "conformal_lower": 0.01,
        "conformal_upper": 0.04,
        "backtest_passes": 3,
        "backtest_pass_strategies": ["mac"],
        "status": "ACTIONED",
        "resolution_date": res_date,
    })
    await db_session.flush()

    result = await resolve_tickets(db_session, as_of_date=res_date)
    assert result["resolved"] == 1
    assert result["expired"] == 0

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    ticket = (await db_session.execute(stmt)).scalar_one()
    assert ticket.outcome == "loss"
    assert ticket.actual_return == pytest.approx(-0.05)
    assert ticket.status == "RESOLVED"


@pytest.mark.asyncio
async def test_resolution_flat_for_tiny_move(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-flat")
    await _seed_ticker(db_session, ticker_id, "FLAT")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ohlcv_bar(db_session, ticker_id, res_date, 100.05)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.001,
        "conviction_score": 70.0,
        "conformal_lower": 0.001,
        "conformal_upper": 0.003,
        "backtest_passes": 2,
        "backtest_pass_strategies": ["mac"],
        "status": "REVIEWED",
        "resolution_date": res_date,
    })
    await db_session.flush()

    result = await resolve_tickets(db_session, as_of_date=res_date)
    assert result["resolved"] == 1

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    ticket = (await db_session.execute(stmt)).scalar_one()
    assert ticket.outcome == "flat"
    assert ticket.actual_return == pytest.approx(0.0005)
    assert ticket.status == "RESOLVED"


@pytest.mark.asyncio
async def test_resolution_idempotent(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-idem")
    await _seed_ticker(db_session, ticker_id, "IDEM")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ohlcv_bar(db_session, ticker_id, res_date, 110.0)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.02,
        "conviction_score": 80.0,
        "conformal_lower": 0.01,
        "conformal_upper": 0.04,
        "backtest_passes": 3,
        "backtest_pass_strategies": ["mac"],
        "status": "REVIEWED",
        "resolution_date": res_date,
    })
    await db_session.flush()

    r1 = await resolve_tickets(db_session, as_of_date=res_date)
    assert r1["resolved"] == 1

    r2 = await resolve_tickets(db_session, as_of_date=res_date)
    assert r2["resolved"] == 0
    assert r2["expired"] == 0
    assert r2["deferred"] == 0

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    ticket = (await db_session.execute(stmt)).scalar_one()
    assert ticket.outcome == "win"
    assert ticket.status == "RESOLVED"


@pytest.mark.asyncio
async def test_missing_resolution_bar_deferred(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-defer")
    await _seed_ticker(db_session, ticker_id, "DEFER")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.02,
        "conviction_score": 80.0,
        "conformal_lower": 0.01,
        "conformal_upper": 0.04,
        "backtest_passes": 3,
        "backtest_pass_strategies": ["mac"],
        "status": "REVIEWED",
        "resolution_date": res_date,
    })
    await db_session.flush()

    result = await resolve_tickets(db_session, as_of_date=res_date)
    assert result["deferred"] == 1
    assert result["resolved"] == 0
    assert result["expired"] == 0


@pytest.mark.asyncio
async def test_tradable_expires_not_resolved(db_session):
    from app.features.conviction_tickets.resolution import resolve_tickets
    from app.features.conviction_tickets.models import ConvictionTicket
    from sqlalchemy import select

    ticker_id = uuid.uuid4()
    universe_id = uuid.uuid4()
    inf_run_id = uuid.uuid4()

    inf_date = date(2025, 6, 2)
    res_date = date(2025, 6, 9)

    await _seed_universe(db_session, universe_id, "test-expire")
    await _seed_ticker(db_session, ticker_id, "EXPIRE")
    await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
    await _seed_ohlcv_bar(db_session, ticker_id, inf_date, 100.0)
    await _seed_ohlcv_bar(db_session, ticker_id, res_date, 105.0)
    await _seed_ticket(db_session, {
        "inference_run_id": inf_run_id,
        "ticker_id": ticker_id,
        "universe_id": universe_id,
        "inference_date": inf_date,
        "horizon": "T5",
        "direction": "LONG",
        "predicted_return": 0.02,
        "conviction_score": 80.0,
        "conformal_lower": 0.01,
        "conformal_upper": 0.04,
        "backtest_passes": 3,
        "backtest_pass_strategies": ["mac"],
        "status": "TRADABLE",
        "resolution_date": res_date,
    })
    await db_session.flush()

    result = await resolve_tickets(db_session, as_of_date=res_date)
    assert result["expired"] == 1
    assert result["resolved"] == 0
    assert result["deferred"] == 0

    stmt = select(ConvictionTicket).where(
        ConvictionTicket.inference_run_id == inf_run_id
    )
    ticket = (await db_session.execute(stmt)).scalar_one()
    assert ticket.status == "EXPIRED"
    assert ticket.outcome == "win"
    assert ticket.actual_return == pytest.approx(0.05)
