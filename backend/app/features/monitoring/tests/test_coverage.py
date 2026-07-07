import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from app.features.monitoring import repository as monitoring_repo


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


async def _seed_ticket(
    db_session,
    inf_run_id,
    ticker_id,
    universe_id,
    horizon,
    resolution_date,
    actual_return,
    conformal_lower=0.01,
    conformal_upper=0.05,
    status="TRADABLE",
):
    await db_session.execute(
        text(
            "INSERT INTO conviction_tickets "
            "(id, inference_run_id, ticker_id, universe_id, inference_date, "
            "horizon, direction, predicted_return, conviction_score, "
            "conformal_lower, conformal_upper, conformal_alpha, "
            "backtest_passes, backtest_pass_strategies, status, "
            "resolution_date, actual_return) "
            "VALUES (gen_random_uuid(), :irid, :tid, :uid, :idt, "
            ":hz, 'LONG', 0.03, 80.0, "
            ":clo, :chi, 0.10, "
            "3, '{mac,ma_cross}'::text[], :st, :rdt, :ar)"
        ),
        {
            "irid": inf_run_id,
            "tid": ticker_id,
            "uid": universe_id,
            "idt": resolution_date - timedelta(days=5),
            "hz": horizon,
            "clo": conformal_lower,
            "chi": conformal_upper,
            "st": status,
            "rdt": resolution_date,
            "ar": actual_return,
        },
    )


async def _seed_many_tickets(
    db_session,
    inf_run_id,
    universe_id,
    horizon,
    resolution_date,
    total,
    covered_count,
    conformal_lower=0.01,
    conformal_upper=0.05,
    symbol_prefix="TKR",
):
    for i in range(total):
        ticker_id = uuid.uuid4()
        await _seed_ticker(db_session, ticker_id, f"{symbol_prefix}{i}")
        if i < covered_count:
            actual_return = 0.03
        else:
            actual_return = 0.10
        await _seed_ticket(
            db_session,
            inf_run_id,
            ticker_id,
            universe_id,
            horizon,
            resolution_date,
            actual_return,
            conformal_lower=conformal_lower,
            conformal_upper=conformal_upper,
        )


@pytest.mark.asyncio
class TestCoverageSignal:
    async def test_coverage_from_resolved_tickets(self, db_session):
        from app.features.monitoring.signals.coverage import CoverageSignal

        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        today = date.today()

        await _seed_universe(db_session, universe_id, "test-cov1")
        await _seed_inference_run(db_session, inf_run_id, universe_id, today)
        await db_session.flush()

        await _seed_many_tickets(
            db_session,
            inf_run_id,
            universe_id,
            "T5",
            today,
            total=10,
            covered_count=8,
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = CoverageSignal(alert_service=mock_alert)
        await signal.compute(db_session, universe_id, today)

        covs = await monitoring_repo.get_recent_coverages(
            db_session, universe_id, "T5", 30, limit=5
        )
        assert len(covs) >= 1
        metric = covs[0]
        assert metric.horizon == "T5"
        assert metric.window_size == 30
        assert metric.realized_coverage == 0.80
        assert metric.num_tickets_resolved == 10

    async def test_coverage_sustained_breach_raises_alert(self, db_session):
        from app.features.monitoring.signals.coverage import CoverageSignal

        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        today = date.today()

        await _seed_universe(db_session, universe_id, "test-cov2")
        await _seed_inference_run(db_session, inf_run_id, universe_id, today)
        await db_session.flush()

        for offset in range(1, 5):
            await monitoring_repo.upsert_coverage_metric(
                db_session,
                universe_id=universe_id,
                horizon="T5",
                measurement_date=today - timedelta(days=offset),
                window_size=30,
                realized_coverage=0.70,
                num_tickets_resolved=10,
                is_alert=True,
            )

        await db_session.flush()

        await _seed_many_tickets(
            db_session,
            inf_run_id,
            universe_id,
            "T5",
            today,
            total=10,
            covered_count=6,
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = CoverageSignal(alert_service=mock_alert)
        await signal.compute(db_session, universe_id, today)

        mock_alert.raise_alert.assert_awaited_once()
        call_args = mock_alert.raise_alert.call_args
        assert call_args.kwargs["severity"] == "critical"
        assert call_args.kwargs["code"] == "COVERAGE_BREACH"
        assert call_args.kwargs["universe_id"] == universe_id

    async def test_coverage_short_sample_skipped(self, db_session):
        from app.features.monitoring.signals.coverage import CoverageSignal

        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        today = date.today()

        await _seed_universe(db_session, universe_id, "test-cov3")
        await _seed_inference_run(db_session, inf_run_id, universe_id, today)
        await db_session.flush()

        await _seed_many_tickets(
            db_session,
            inf_run_id,
            universe_id,
            "T5",
            today,
            total=3,
            covered_count=3,
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = CoverageSignal(alert_service=mock_alert)
        await signal.compute(db_session, universe_id, today)

        covs = await monitoring_repo.get_recent_coverages(
            db_session, universe_id, "T5", 30, limit=5
        )
        assert len(covs) >= 1
        metric = covs[0]
        assert metric.horizon == "T5"
        assert metric.window_size == 30
        assert metric.realized_coverage is None
        assert metric.num_tickets_resolved == 3

    async def test_coverage_30day_and_90day(self, db_session):
        from app.features.monitoring.signals.coverage import CoverageSignal

        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()
        today = date.today()

        await _seed_universe(db_session, universe_id, "test-cov4")
        await _seed_inference_run(db_session, inf_run_id, universe_id, today)
        await db_session.flush()

        await _seed_many_tickets(
            db_session,
            inf_run_id,
            universe_id,
            "T1",
            today - timedelta(days=20),
            total=10,
            covered_count=10,
        )
        await _seed_many_tickets(
            db_session,
            inf_run_id,
            universe_id,
            "T1",
            today - timedelta(days=60),
            total=10,
            covered_count=5,
            symbol_prefix="TK2",
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = CoverageSignal(alert_service=mock_alert)
        await signal.compute(db_session, universe_id, today)

        covs_30 = await monitoring_repo.get_recent_coverages(
            db_session, universe_id, "T1", 30, limit=10
        )
        covs_90 = await monitoring_repo.get_recent_coverages(
            db_session, universe_id, "T1", 90, limit=10
        )

        assert len(covs_30) >= 1
        metric_30 = covs_30[0]
        assert metric_30.window_size == 30
        assert metric_30.num_tickets_resolved == 10
        assert metric_30.realized_coverage == 1.0

        assert len(covs_90) >= 1
        metric_90 = covs_90[0]
        assert metric_90.window_size == 90
        assert metric_90.num_tickets_resolved == 20
        assert metric_90.realized_coverage == 0.75
