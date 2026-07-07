import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from app.features.conviction_tickets.models import ConvictionTicket
from app.features.ml_models.models import InferenceRun
from app.features.monitoring.signals.correlation import compute_conviction_correlation
from app.features.universes.models import Ticker, Universe


class _FakeAlertService:
    def __init__(self):
        self.alerts = []

    async def raise_alert(self, session, severity, code, message, universe_id=None, context=None):
        self.alerts.append({
            "severity": severity,
            "code": code,
            "message": message,
            "universe_id": universe_id,
            "context": context,
        })


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


async def _make_inference_run(db_session, universe) -> InferenceRun:
    ir = InferenceRun(
        universe_id=universe.id,
        triggered_by="test",
        inference_date=date.today(),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="completed",
        artifact_ids=[],
        num_tickers_scored=1,
    )
    db_session.add(ir)
    await db_session.flush()
    return ir


@pytest.mark.asyncio
async def test_perfect_positive_correlation(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)

    today = date.today()
    for i in range(30):
        inference_run = await _make_inference_run(db_session, universe)
        conviction = 90.0 + (i * (10.0 / 29))
        actual_return = (i * (5.0 / 29)) / 100.0
        ticket = ConvictionTicket(
            inference_run_id=inference_run.id,
            ticker_id=ticker.id,
            universe_id=universe.id,
            inference_date=today - timedelta(days=30 - i),
            horizon="1d",
            direction="LONG",
            predicted_return=actual_return,
            conviction_score=conviction,
            conformal_lower=conviction - 5,
            conformal_upper=conviction + 5,
            conformal_alpha=0.10,
            backtest_passes=2,
            backtest_pass_strategies=["mean_reversion", "momentum_cross"],
            status="RESOLVED",
            resolution_date=today,
            actual_return=actual_return,
            outcome="WIN",
        )
        db_session.add(ticket)
    await db_session.flush()

    corr = await compute_conviction_correlation(db_session, universe.id)
    assert corr is not None
    assert corr > 0.95


@pytest.mark.asyncio
async def test_no_correlation_raises_warning(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)

    rng = np.random.default_rng(42)
    today = date.today()
    for i in range(30):
        inference_run = await _make_inference_run(db_session, universe)
        ticket = ConvictionTicket(
            inference_run_id=inference_run.id,
            ticker_id=ticker.id,
            universe_id=universe.id,
            inference_date=today - timedelta(days=30 - i),
            horizon="1d",
            direction="LONG",
            predicted_return=0.0,
            conviction_score=float(rng.uniform(50, 100)),
            conformal_lower=50.0,
            conformal_upper=100.0,
            conformal_alpha=0.10,
            backtest_passes=2,
            backtest_pass_strategies=["mean_reversion", "momentum_cross"],
            status="RESOLVED",
            resolution_date=today,
            actual_return=float(rng.uniform(-5, 5)),
            outcome="WIN",
        )
        db_session.add(ticket)
    await db_session.flush()

    alert_service = _FakeAlertService()

    corr = await compute_conviction_correlation(db_session, universe.id, alert_service)
    assert corr is not None
    assert corr < 0.2

    await compute_conviction_correlation(db_session, universe.id, alert_service)
    await compute_conviction_correlation(db_session, universe.id, alert_service)

    warnings = [a for a in alert_service.alerts if a["severity"] == "warning"]
    assert len(warnings) >= 1
    assert warnings[0]["code"] == "CONVICTION_UNPREDICTIVE"


@pytest.mark.asyncio
async def test_insufficient_sample_skipped(db_session):
    universe = await _make_universe(db_session)
    ticker = await _make_ticker(db_session)

    today = date.today()
    for i in range(5):
        inference_run = await _make_inference_run(db_session, universe)
        ticket = ConvictionTicket(
            inference_run_id=inference_run.id,
            ticker_id=ticker.id,
            universe_id=universe.id,
            inference_date=today - timedelta(days=5 - i),
            horizon="1d",
            direction="LONG",
            predicted_return=0.0,
            conviction_score=float(i * 10),
            conformal_lower=0.0,
            conformal_upper=100.0,
            conformal_alpha=0.10,
            backtest_passes=2,
            backtest_pass_strategies=["mean_reversion", "momentum_cross"],
            status="RESOLVED",
            resolution_date=today,
            actual_return=float(i * 0.5),
            outcome="WIN",
        )
        db_session.add(ticket)
    await db_session.flush()

    alert_service = _FakeAlertService()
    corr = await compute_conviction_correlation(db_session, universe.id, alert_service)
    assert corr is None
    assert len(alert_service.alerts) == 0
