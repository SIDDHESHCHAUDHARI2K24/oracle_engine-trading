import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest


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


async def _seed_ref_data(db_session, universe_id, ticker_id, inf_run_id, bt_run_id):
    from sqlalchemy import text

    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, display_name, created_at) "
            "VALUES (:id, :name, :dn, now())"
        ),
        {
            "id": universe_id,
            "name": f"test-{universe_id}",
            "dn": f"Display {universe_id}",
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO tickers (id, symbol, name, created_at, active) "
            "VALUES (:id, :sym, :name, now(), true)"
        ),
        {
            "id": ticker_id,
            "sym": f"T{str(ticker_id)[:18]}",
            "name": f"Ticker {ticker_id}",
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO inference_runs (id, universe_id, triggered_by, inference_date, status) "
            "VALUES (:id, :uid, :trig, :dt, 'completed')"
        ),
        {"id": inf_run_id, "uid": universe_id, "trig": "test", "dt": date.today()},
    )
    await db_session.execute(
        text(
            "INSERT INTO backtest_runs (id, universe_id, triggered_by, backtest_period_start, backtest_period_end, status, num_strategies, metadata) "
            "VALUES (:id, :uid, :trig, :start, :end, 'completed', 4, '{}'::jsonb)"
        ),
        {
            "id": bt_run_id,
            "uid": universe_id,
            "trig": "test",
            "start": date.today() - timedelta(days=365),
            "end": date.today(),
        },
    )
    await db_session.flush()


class TestPredictionsToDicts:
    def test_single_row_expands_to_four(self):
        from app.features.conviction_tickets.service import _predictions_to_dicts

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        pred = _make_prediction_row(ticker_id, universe_id, inf_run_id, date.today())

        dicts = _predictions_to_dicts([pred])
        assert len(dicts) == 4
        horizons = {d["horizon_idx"] for d in dicts}
        assert horizons == {0, 1, 2, 3}

    def test_correct_column_mapping(self):
        from app.features.conviction_tickets.service import _predictions_to_dicts

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        pred = _make_prediction_row(
            ticker_id,
            universe_id,
            inf_run_id,
            date.today(),
            pred_t1=0.025,
            pred_lo_t1=0.01,
            pred_hi_t1=0.04,
            conviction_t1=82.0,
        )

        dicts = _predictions_to_dicts([pred])
        t1 = [d for d in dicts if d["horizon_idx"] == 0][0]
        assert t1["pred"] == 0.025
        assert t1["pred_lo"] == 0.01
        assert t1["pred_hi"] == 0.04
        assert t1["conviction"] == 82.0
        assert t1["width"] == 0.03
        assert t1["ticker_id"] == str(ticker_id)
        assert t1["universe_id"] == str(universe_id)

    def test_width_computed_from_pred_lo_hi(self):
        from app.features.conviction_tickets.service import _predictions_to_dicts

        pred = _make_prediction_row(
            uuid.uuid4(),
            uuid.uuid4(),
            uuid.uuid4(),
            date.today(),
            pred_t5=0.03,
            pred_lo_t5=0.02,
            pred_hi_t5=0.07,
        )

        dicts = _predictions_to_dicts([pred])
        t5 = [d for d in dicts if d["horizon_idx"] == 1][0]
        assert t5["width"] == pytest.approx(0.05)
        assert t5["pred_lo"] == 0.02
        assert t5["pred_hi"] == 0.07


class TestBacktestPasses:
    def test_backtest_passes_from_summary(self):
        from app.features.conviction_tickets.service import _build_backtest_passes

        metrics = [
            {
                "ticker_id": "AAA",
                "passes": 3,
                "strategies": {"mac": True, "ma_cross": True, "bb": True, "rsi": False},
            },
            {
                "ticker_id": "BBB",
                "passes": 1,
                "strategies": {
                    "mac": False,
                    "ma_cross": True,
                    "bb": False,
                    "rsi": False,
                },
            },
        ]
        passes = _build_backtest_passes(metrics)
        assert passes == {"AAA": 3, "BBB": 1}

    def test_backtest_strategies_from_summary(self):
        from app.features.conviction_tickets.service import _build_backtest_strategies

        metrics = [
            {
                "ticker_id": "AAA",
                "passes": 3,
                "strategies": {"mac": True, "ma_cross": True, "bb": True, "rsi": False},
            },
            {
                "ticker_id": "BBB",
                "passes": 1,
                "strategies": {
                    "mac": False,
                    "ma_cross": True,
                    "bb": False,
                    "rsi": False,
                },
            },
        ]
        strategies = _build_backtest_strategies(metrics)
        assert sorted(strategies["AAA"]) == sorted(["mac", "ma_cross", "bb"])
        assert strategies["BBB"] == ["ma_cross"]


class TestTicketServiceEmitTickets:
    @pytest.mark.asyncio
    async def test_emit_tickets_runs(self, db_session):
        from app.features.conviction_tickets.service import TicketService

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        bt_run_id = uuid.uuid4()

        await _seed_ref_data(db_session, universe_id, ticker_id, inf_run_id, bt_run_id)

        prediction_row = _make_prediction_row(
            ticker_id,
            universe_id,
            inf_run_id,
            date.today(),
            pred_t1=0.025,
            pred_lo_t1=0.01,
            pred_hi_t1=0.04,
            conviction_t1=82.0,
            pred_t5=0.015,
            pred_lo_t5=0.01,
            pred_hi_t5=0.035,
            conviction_t5=68.0,
            pred_t10=-0.01,
            pred_lo_t10=-0.03,
            pred_hi_t10=0.0,
            conviction_t10=75.0,
            pred_t15=0.02,
            pred_lo_t15=0.0,
            pred_hi_t15=0.12,
            conviction_t15=70.0,
        )
        inference_run = _make_inference_run(inf_run_id, universe_id, date.today())

        bt_metrics = [
            {
                "ticker_id": str(ticker_id),
                "passes": 3,
                "strategies": {"mac": True, "ma_cross": True, "bb": True},
            },
        ]
        w_max = {0: 0.05, 1: 0.10, 2: 0.10, 3: 0.10}

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
        assert len([t for t in tickets if t.horizon == "T1"]) == 1
        assert len([t for t in tickets if t.horizon == "T5"]) == 1

    @pytest.mark.asyncio
    async def test_emit_tickets_no_passing(self, db_session):
        from app.features.conviction_tickets.service import TicketService

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        bt_run_id = uuid.uuid4()

        await _seed_ref_data(db_session, universe_id, ticker_id, inf_run_id, bt_run_id)

        prediction_row = _make_prediction_row(
            ticker_id,
            universe_id,
            inf_run_id,
            date.today(),
            pred_t1=-0.01,
            pred_lo_t1=-0.03,
            pred_hi_t1=0.0,
            conviction_t1=80.0,
            pred_t5=-0.02,
            pred_lo_t5=-0.04,
            pred_hi_t5=0.0,
            conviction_t5=70.0,
            pred_t10=-0.01,
            pred_lo_t10=-0.02,
            pred_hi_t10=0.0,
            conviction_t10=75.0,
            pred_t15=-0.005,
            pred_lo_t15=-0.01,
            pred_hi_t15=0.0,
            conviction_t15=65.0,
        )
        inference_run = _make_inference_run(inf_run_id, universe_id, date.today())

        bt_metrics = [
            {"ticker_id": str(ticker_id), "passes": 3, "strategies": {"mac": True}},
        ]
        w_max = {0: 0.05, 1: 0.10, 2: 0.10, 3: 0.12}

        service = TicketService()
        tickets, filter_run = await service.emit_tickets(
            session=db_session,
            inference_run=inference_run,
            predictions=[prediction_row],
            backtest_metrics=bt_metrics,
            w_max=w_max,
            backtest_run_id=bt_run_id,
        )

        assert len(tickets) == 0
        assert filter_run.num_tickets_emitted == 0
