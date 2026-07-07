import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import torch
from sqlalchemy import func, select

from app.core.services.artifact_store import LocalArtifactStore
from app.features.feature_engineering.repository import bulk_upsert_feature_matrix
from app.features.feature_engineering.shared.feature_schema import input_feature_names
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.inference_service import (
    _calibrator_to_bytes,
    run_inference,
)
from app.features.ml_models.lstm.architecture import LSTMMathEngine
from app.features.ml_models.models import InferenceRun, Prediction, TrainingRun
from app.features.universes.models import Ticker, Universe, UniverseMembership

torch.manual_seed(42)
np.random.seed(42)

FEATURE_COLS = input_feature_names()
LOOKBACK = 252


def _make_artifact_store() -> LocalArtifactStore:
    tmp = tempfile.mkdtemp(prefix="artifacts_")
    return LocalArtifactStore(root=Path(tmp))


async def _create_universe(db_session, name: str = "test_inference") -> Universe:
    uni = Universe(name=name, display_name="Test Inference")
    db_session.add(uni)
    await db_session.flush()
    return uni


async def _create_ticker(db_session, symbol: str) -> Ticker:
    ticker = Ticker(symbol=symbol, name=f"Ticker {symbol}")
    db_session.add(ticker)
    await db_session.flush()
    return ticker


async def _add_membership(
    db_session, universe_id: uuid.UUID, ticker_id: uuid.UUID
) -> UniverseMembership:
    now = datetime.now(timezone.utc)
    mem = UniverseMembership(
        universe_id=universe_id, ticker_id=ticker_id, added_at=now
    )
    db_session.add(mem)
    await db_session.flush()
    return mem


async def _insert_features(
    db_session,
    ticker_id: uuid.UUID,
    n_days: int,
    base_date: date,
) -> int:
    rng = np.random.default_rng(77)
    records: list[dict] = []
    for i in range(n_days):
        rec: dict = {
            "ticker_id": ticker_id,
            "bar_date": base_date - timedelta(days=n_days - 1 - i),
        }
        for col in FEATURE_COLS:
            if col == "volume":
                rec[col] = int(rng.integers(1000, 10_000_000))
            else:
                rec[col] = float(rng.standard_normal())
        records.append(rec)
    return await bulk_upsert_feature_matrix(db_session, records)


async def _setup_lstm_artifact(
    db_session,
    artifact_store: LocalArtifactStore,
    universe_id: uuid.UUID,
    universe_slug: str,
    training_run_id: uuid.UUID,
) -> uuid.UUID:
    tr = TrainingRun(
        id=training_run_id,
        universe_id=universe_id,
        triggered_by="test",
        status="completed",
    )
    db_session.add(tr)
    await db_session.flush()

    lifecycle = ArtifactLifecycleService(artifact_store)
    model = LSTMMathEngine()
    data = model.serialize()
    artifact = await lifecycle.save_artifact(
        db_session, universe_id, universe_slug, "lstm", training_run_id, data
    )
    await lifecycle.activate(db_session, artifact.id)
    return artifact.id


async def _setup_calibrator_artifact(
    db_session,
    artifact_store: LocalArtifactStore,
    universe_id: uuid.UUID,
    universe_slug: str,
    training_run_id: uuid.UUID,
) -> uuid.UUID:
    from app.features.ml_models.conformal.calibrator import ConformalCalibrator

    lifecycle = ArtifactLifecycleService(artifact_store)
    cal = ConformalCalibrator(alpha=0.10)
    cal.quantiles = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0}
    data = _calibrator_to_bytes(cal)
    artifact = await lifecycle.save_artifact(
        db_session, universe_id, universe_slug, "conformal", training_run_id, data
    )
    await lifecycle.activate(db_session, artifact.id)
    return artifact.id


class TestRunInference:
    async def test_produces_predictions(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_predictions")
        t1 = await _create_ticker(db_session, "TICK1")
        t2 = await _create_ticker(db_session, "TICK2")
        for t in (t1, t2):
            await _add_membership(db_session, uni.id, t.id)
            await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        result = await run_inference(uni.id, inference_date, db_session, store)

        assert result.status == "completed"
        assert result.num_tickers_scored == 2

        preds = await db_session.execute(
            select(Prediction).where(
                Prediction.inference_date == inference_date,
                Prediction.universe_id == uni.id,
            )
        )
        preds = preds.scalars().all()
        assert len(preds) == 2

        for p in preds:
            assert p.inference_run_id == result.inference_run_id
            assert -2.0 < p.pred_t1 < 2.0
            assert p.pred_lo_t1 <= p.pred_hi_t1
            assert len(p.lstm_outputs) == 4

    async def test_rerun_same_date_is_idempotent(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_idempotent")
        t = await _create_ticker(db_session, "IDEM")
        await _add_membership(db_session, uni.id, t.id)
        await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        r1 = await run_inference(uni.id, inference_date, db_session, store)
        r2 = await run_inference(uni.id, inference_date, db_session, store)

        assert r1.num_tickers_scored == 1
        assert r2.num_tickers_scored == 1
        assert r2.num_predictions_written == 0

        count = await db_session.scalar(
            select(func.count()).select_from(Prediction).where(
                Prediction.universe_id == uni.id,
                Prediction.inference_date == inference_date,
            )
        )
        assert count == 1

    async def test_short_history_tickers_skipped(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_skipped")

        t_long = await _create_ticker(db_session, "LONG")
        t_short = await _create_ticker(db_session, "SHORT")
        await _add_membership(db_session, uni.id, t_long.id)
        await _add_membership(db_session, uni.id, t_short.id)
        await _insert_features(db_session, t_long.id, 260, inference_date)
        await _insert_features(db_session, t_short.id, 100, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        result = await run_inference(uni.id, inference_date, db_session, store)

        assert result.num_tickers_scored == 1

        preds = await db_session.execute(
            select(Prediction).where(
                Prediction.inference_date == inference_date,
                Prediction.universe_id == uni.id,
            )
        )
        preds = preds.scalars().all()
        assert len(preds) == 1

    async def test_artifact_ids_recorded(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_artifacts")
        t = await _create_ticker(db_session, "ARTS")
        await _add_membership(db_session, uni.id, t.id)
        await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        lstm_aid = await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        result = await run_inference(uni.id, inference_date, db_session, store)

        run = await db_session.get(InferenceRun, result.inference_run_id)
        assert run is not None
        stored_ids = [uuid.UUID(a) for a in run.artifact_ids]
        assert lstm_aid in stored_ids

    async def test_conviction_scores_in_range(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_conviction")
        t = await _create_ticker(db_session, "CONV")
        await _add_membership(db_session, uni.id, t.id)
        await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        await run_inference(uni.id, inference_date, db_session, store)

        preds = await db_session.execute(
            select(Prediction).where(
                Prediction.inference_date == inference_date,
                Prediction.universe_id == uni.id,
            )
        )
        pred = preds.scalars().all()[0]

        for label in ("t1", "t5", "t10", "t15"):
            score = getattr(pred, f"conviction_{label}")
            assert 0.0 <= score <= 100.0, f"conviction_{label}={score} out of [0,100]"

    async def test_empty_universe_no_active_artifacts(self, db_session):
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_empty")

        with pytest.raises(ValueError, match="No active artifacts"):
            await run_inference(
                uni.id, date(2024, 12, 31), db_session, store
            )

    async def test_tft_arrays_zero_when_skipped(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_tft_zero")
        t = await _create_ticker(db_session, "TFTZ")
        await _add_membership(db_session, uni.id, t.id)
        await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        await run_inference(uni.id, inference_date, db_session, store)

        preds = await db_session.execute(
            select(Prediction).where(
                Prediction.inference_date == inference_date,
                Prediction.universe_id == uni.id,
            )
        )
        pred = preds.scalars().all()[0]

        assert pred.tft_q10 == [0.0, 0.0, 0.0, 0.0]
        assert pred.tft_q50 == [0.0, 0.0, 0.0, 0.0]
        assert pred.tft_q90 == [0.0, 0.0, 0.0, 0.0]

    async def test_inference_run_status_completed(self, db_session):
        inference_date = date(2024, 12, 31)
        store = _make_artifact_store()
        uni = await _create_universe(db_session, "inf_test_status")
        t = await _create_ticker(db_session, "STAT")
        await _add_membership(db_session, uni.id, t.id)
        await _insert_features(db_session, t.id, 260, inference_date)

        tr_id = uuid.uuid4()
        await _setup_lstm_artifact(db_session, store, uni.id, uni.name, tr_id)

        result = await run_inference(uni.id, inference_date, db_session, store)

        run = await db_session.get(InferenceRun, result.inference_run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.completed_at is not None
        assert run.num_tickers_scored == 1
