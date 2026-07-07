import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator

import numpy as np
import pytest
from sqlalchemy import func, select

from app.core.services.artifact_store import LocalArtifactStore
from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)
from app.features.ml_models import repository as ml_repo
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.inference_service import run_inference
from app.features.ml_models.models import ModelArtifact, Prediction
from app.features.ml_models.promotion import promote_challenger
from app.features.ml_models.service import train_universe
from app.features.universes.models import Ticker, Universe, UniverseMembership

pytestmark = pytest.mark.integration

FEATURE_NAMES = list(input_feature_names())
TARGET_NAMES = list(target_names())

_BASE_DATE = date(2025, 1, 2)
_TICKER_COUNT = 3
_ROWS_PER_TICKER = 400


def _make_feature_row(ticker_id: uuid.UUID, bar_date: date, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed + bar_date.toordinal())
    row = {
        "ticker_id": ticker_id,
        "bar_date": bar_date,
        "feature_schema_version": "v1.0",
    }
    for col in FEATURE_NAMES:
        row[col] = Decimal(str(round(float(rng.standard_normal()) * 10.0 + 100.0, 6)))
    for col in TARGET_NAMES:
        row[col] = Decimal(str(round(float(rng.standard_normal()) * 0.02, 8)))
    return row


async def _insert_feature_rows(session, ticker_ids: list[uuid.UUID]) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows: list[dict] = []
    for ti, ticker_id in enumerate(ticker_ids):
        for d in range(_ROWS_PER_TICKER):
            bar_date = _BASE_DATE + timedelta(days=d)
            row = _make_feature_row(ticker_id, bar_date, seed=ti * 1000 + d)
            rows.append(row)

    update_cols = {}
    for col in FeatureMatrix.__table__.columns:
        col_name = str(col.name)
        if col_name not in ("ticker_id", "bar_date", "feature_schema_version"):
            update_cols[col_name] = getattr(FeatureMatrix.__table__.c, col_name)

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        stmt = pg_insert(FeatureMatrix).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker_id", "bar_date", "feature_schema_version"],
            set_=update_cols,
        )
        await session.execute(stmt)
    await session.flush()


class TestE2EIntegration:
    @pytest.fixture
    def artifact_store(self) -> Generator[LocalArtifactStore, None, None]:
        with TemporaryDirectory() as tmpdir:
            yield LocalArtifactStore(root=Path(tmpdir) / "artifacts")

    @pytest.mark.asyncio
    async def test_full_train_infer_promote_cycle(self, db_session, artifact_store):
        # ── 1. Create universe + tickers with feature data ──
        universe = Universe(
            id=uuid.uuid4(),
            name="e2e-universe",
            display_name="E2E Test Universe",
            is_system_managed=False,
        )
        db_session.add(universe)
        await db_session.flush()

        ticker_ids: list[uuid.UUID] = []
        for sym in ["AAPL", "MSFT", "GOOGL"]:
            ticker = Ticker(
                id=uuid.uuid4(),
                symbol=f"E2E-{sym}",
                name=f"E2E {sym}",
                exchange="NYSE",
                asset_type="equity",
                active=True,
            )
            db_session.add(ticker)
            await db_session.flush()
            ticker_ids.append(ticker.id)

            membership = UniverseMembership(
                universe_id=universe.id,
                ticker_id=ticker.id,
                added_at=datetime(2024, 12, 1, tzinfo=timezone.utc),
            )
            db_session.add(membership)

        await db_session.flush()
        await _insert_feature_rows(db_session, ticker_ids)

        # ── 2. Train ──
        as_of_date = _BASE_DATE + timedelta(days=_ROWS_PER_TICKER - 1)
        result = await train_universe(
            universe_id=universe.id,
            as_of_date=as_of_date,
            db_session=db_session,
            artifact_store=artifact_store,
            hyperparams={
                "max_epochs": 3,
                "batch_size": 16,
                "patience": 10,
                "lr": 5e-3,
                "tft_max_epochs": 3,
            },
        )

        assert result.status == "completed", f"Training failed: {result.error}"
        assert result.training_run_id != uuid.UUID(int=0)
        assert len(result.artifact_ids) >= 2, (
            f"Expected >=2 artifacts, got {len(result.artifact_ids)}"
        )
        assert "overall_mse" in result.validation_metrics

        run = await ml_repo.get_training_run(db_session, result.training_run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.num_tickers == _TICKER_COUNT
        assert run.validation_metrics is not None
        assert run.hyperparams_snapshot is not None

        for aid in result.artifact_ids:
            artifact = await db_session.get(ModelArtifact, aid)
            assert artifact is not None
            assert artifact.training_run_id == result.training_run_id
            assert artifact.universe_id == universe.id

        lstm_artifact = None
        conformal_artifact = None
        for aid in result.artifact_ids:
            art = await db_session.get(ModelArtifact, aid)
            if art.model_role == "lstm":
                lstm_artifact = art
            elif art.model_role == "conformal":
                conformal_artifact = art
        assert lstm_artifact is not None, "LSTM artifact missing"
        assert conformal_artifact is not None, "Conformal artifact missing"

        # ── 3. Promote (auto-promote on first training) ──
        artifact_service = ArtifactLifecycleService(artifact_store)
        promoted, reason = await promote_challenger(
            session=db_session,
            artifact_service=artifact_service,
            challenger_artifact_ids=result.artifact_ids,
            challenger_metrics=result.validation_metrics,
            universe_id=universe.id,
        )

        assert promoted is True, f"Expected auto-promote, got: {reason}"
        assert "no champion" in reason.lower()

        for aid in result.artifact_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is True, f"Artifact {aid} not activated"

        # ── 4. Infer ──
        inference_date = as_of_date
        inf_result = await run_inference(
            universe.id, inference_date, db_session, artifact_store
        )

        assert inf_result.status == "completed"
        assert inf_result.num_tickers_scored == _TICKER_COUNT
        assert inf_result.num_predictions_written == _TICKER_COUNT

        preds = await db_session.execute(
            select(Prediction).where(
                Prediction.universe_id == universe.id,
                Prediction.inference_date == inference_date,
            )
        )
        preds = preds.scalars().all()
        assert len(preds) == _TICKER_COUNT

        for p in preds:
            assert p.inference_run_id == inf_result.inference_run_id
            assert p.pred_lo_t1 <= p.pred_hi_t1
            assert p.pred_lo_t5 <= p.pred_hi_t5
            assert p.pred_lo_t10 <= p.pred_hi_t10
            assert p.pred_lo_t15 <= p.pred_hi_t15
            assert len(p.lstm_outputs) == 4
            assert len(p.tft_q10) == 4
            assert len(p.tft_q50) == 4
            assert len(p.tft_q90) == 4

        # ── 5. Idempotent re-run inference ──
        inf_result2 = await run_inference(
            universe.id, inference_date, db_session, artifact_store
        )

        assert inf_result2.num_tickers_scored == _TICKER_COUNT
        assert inf_result2.num_predictions_written == 0, (
            "Expected idempotent re-run to write 0 new predictions"
        )

        count = await db_session.scalar(
            select(func.count())
            .select_from(Prediction)
            .where(
                Prediction.universe_id == universe.id,
                Prediction.inference_date == inference_date,
            )
        )
        assert count == _TICKER_COUNT

        # ── 6. Model-health endpoint data verification ──
        training_history = await ml_repo.get_training_history(
            db_session, universe.id, limit=10
        )
        assert len(training_history) >= 1
        assert any(r.id == result.training_run_id for r in training_history), (
            "Training run not found in history"
        )

        latest_run = await ml_repo.get_latest_training_run(db_session, universe.id)
        assert latest_run is not None
        assert latest_run.id == result.training_run_id

        artifacts = await ml_repo.get_artifacts_for_universe(db_session, universe.id)
        assert len(artifacts) >= 2, f"Expected >=2 artifacts, got {len(artifacts)}"
        assert any(a.is_active for a in artifacts), "No active artifacts"

        preds_for_date = await ml_repo.get_predictions_for_date(
            db_session, universe.id, inference_date
        )
        assert len(preds_for_date) == _TICKER_COUNT

        # ── 7. Conviction scores in [0, 100] ──
        for p in preds:
            for label in ("t1", "t5", "t10", "t15"):
                score = getattr(p, f"conviction_{label}")
                assert 0.0 <= score <= 100.0, (
                    f"conviction_{label}={score} out of [0, 100]"
                )
