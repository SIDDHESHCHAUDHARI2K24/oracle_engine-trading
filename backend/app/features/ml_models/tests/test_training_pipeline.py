import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from sqlalchemy import text

from app.core.services.artifact_store import LocalArtifactStore
from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)
from app.features.ml_models import repository as ml_repo
from app.features.ml_models.artifact_service import ArtifactLifecycleService
from app.features.ml_models.models import ModelArtifact, TrainingRun
from app.features.ml_models.promotion import promote_challenger
from app.features.ml_models.service import train_universe, TrainingResult
from app.features.universes.models import Ticker, Universe, UniverseMembership

pytestmark = pytest.mark.anyio

FEATURE_NAMES = list(input_feature_names())
TARGET_NAMES = list(target_names())
N_FEATURES = 31
N_TARGETS = 4

_TEST_BASE_DATE = date(2020, 1, 2)
_TICKER_COUNT = 2
_ROWS_PER_TICKER = 300


def _make_feature_row(
    ticker_id: uuid.UUID,
    bar_date: date,
    seed: int = 0,
) -> dict:
    rng = np.random.default_rng(seed + bar_date.toordinal())
    row = {
        "ticker_id": ticker_id,
        "bar_date": bar_date,
        "feature_schema_version": "v1.0",
    }
    for i, col in enumerate(FEATURE_NAMES):
        row[col] = Decimal(str(round(float(rng.standard_normal()) * 10.0 + 100.0, 6)))
    for i, col in enumerate(TARGET_NAMES):
        row[col] = Decimal(str(round(float(rng.standard_normal()) * 0.02, 8)))
    return row


async def _insert_feature_rows(session, ticker_ids: list[uuid.UUID]):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows = []
    for ti, ticker_id in enumerate(ticker_ids):
        for d in range(_ROWS_PER_TICKER):
            bar_date = _TEST_BASE_DATE + timedelta(days=d)
            row = _make_feature_row(ticker_id, bar_date, seed=ti * 1000 + d)
            rows.append(row)

    stmt = pg_insert(FeatureMatrix).values(rows)
    update_cols = {}
    for col in FeatureMatrix.__table__.columns:
        col_name = str(col.name)
        if col_name not in ("ticker_id", "bar_date", "feature_schema_version"):
            update_cols[col_name] = stmt.excluded[col_name]

    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker_id", "bar_date", "feature_schema_version"],
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.flush()


async def _setup_universe(session):
    universe = Universe(
        id=uuid.uuid4(),
        name="test-universe",
        display_name="Test Universe",
        is_system_managed=False,
    )
    session.add(universe)
    await session.flush()

    ticker_ids = []
    for i in range(_TICKER_COUNT):
        ticker = Ticker(
            id=uuid.uuid4(),
            symbol=f"TEST{i}",
            name=f"Test Ticker {i}",
            exchange="NYSE",
            asset_type="equity",
            active=True,
        )
        session.add(ticker)
        await session.flush()
        ticker_ids.append(ticker.id)

        membership = UniverseMembership(
            universe_id=universe.id,
            ticker_id=ticker.id,
            added_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        session.add(membership)

    await session.flush()
    await _insert_feature_rows(session, ticker_ids)

    return universe, ticker_ids


class TestTrainingPipeline:
    @pytest.fixture
    def artifact_store(self):
        with TemporaryDirectory() as tmpdir:
            yield LocalArtifactStore(root=Path(tmpdir) / "artifacts")

    async def test_training_produces_artifacts_and_run(self, db_session, artifact_store):
        universe, ticker_ids = await _setup_universe(db_session)

        result = await train_universe(
            universe_id=universe.id,
            as_of_date=date(2020, 12, 31),
            db_session=db_session,
            artifact_store=artifact_store,
            hyperparams={
                "max_epochs": 3,
                "tft_max_epochs": 3,
                "batch_size": 16,
                "patience": 10,
                "lr": 5e-3,
            },
        )

        assert isinstance(result, TrainingResult)
        assert result.status == "completed", f"Training failed: {result.error}"
        assert result.training_run_id != uuid.UUID(int=0)
        assert len(result.artifact_ids) >= 2
        assert "overall_mse" in result.validation_metrics
        assert len(result.per_epoch_losses) >= 1

        run = await ml_repo.get_training_run(db_session, result.training_run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.num_tickers == _TICKER_COUNT
        assert run.validation_metrics is not None

        assert run.model_metadata is not None
        assert "feature_distribution" in run.model_metadata, (
            f"TrainingRun missing feature_distribution in model_metadata: "
            f"{run.model_metadata}"
        )
        feature_dist = run.model_metadata["feature_distribution"]
        assert isinstance(feature_dist, dict)
        assert len(feature_dist) >= 1
        first_feature = next(iter(feature_dist.values()))
        assert "hist" in first_feature
        assert "bin_edges" in first_feature
        assert "mean" in first_feature
        assert "std" in first_feature

        for aid in result.artifact_ids:
            artifact = await db_session.get(ModelArtifact, aid)
            assert artifact is not None
            assert artifact.training_run_id == result.training_run_id

        lstm_artifact = None
        conformal_artifact = None
        for aid in result.artifact_ids:
            art = await db_session.get(ModelArtifact, aid)
            if art.model_role == "lstm":
                lstm_artifact = art
            elif art.model_role == "conformal":
                conformal_artifact = art
        assert lstm_artifact is not None
        assert conformal_artifact is not None

        assert "w_max" in (conformal_artifact.model_metadata or {}), (
            f"Conformal artifact missing w_max in model_metadata: "
            f"{conformal_artifact.model_metadata}"
        )
        w_max = conformal_artifact.model_metadata["w_max"]
        assert isinstance(w_max, dict)
        horizon_keys = set(w_max.keys())
        has_int_keys = {0, 1, 2, 3}.issubset(horizon_keys)
        has_str_keys = {"0", "1", "2", "3"}.issubset(horizon_keys)
        assert has_int_keys or has_str_keys, f"w_max missing expected horizon keys: {horizon_keys}"
        for key in w_max:
            val = w_max[key]
            assert isinstance(val, (int, float)), f"w_max[{key}] not numeric: {val}"
            assert val > 0, f"w_max[{key}] not positive: {val}"

    async def test_run_status_transitions_recorded(self, db_session, artifact_store):
        universe, ticker_ids = await _setup_universe(db_session)

        result = await train_universe(
            universe_id=universe.id,
            as_of_date=date(2020, 12, 31),
            db_session=db_session,
            artifact_store=artifact_store,
            hyperparams={
                "max_epochs": 3,
                "tft_max_epochs": 3,
                "batch_size": 32,
                "lr": 5e-3,
            },
        )

        run = await ml_repo.get_training_run(db_session, result.training_run_id)
        assert run is not None
        assert run.status == "completed"
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.completed_at >= run.started_at

        history = await ml_repo.get_training_history(db_session, universe.id, limit=10)
        assert any(r.id == result.training_run_id for r in history)


class TestChampionChallenger:
    @pytest.fixture
    def artifact_store(self):
        with TemporaryDirectory() as tmpdir:
            yield LocalArtifactStore(root=Path(tmpdir) / "artifacts")

    @pytest.fixture
    def artifact_service(self, artifact_store):
        return ArtifactLifecycleService(artifact_store)

    async def _create_universe(self, session):
        universe = Universe(
            name=f"test-universe-{uuid.uuid4().hex[:8]}",
            display_name="Test Universe",
            is_system_managed=False,
        )
        session.add(universe)
        await session.flush()
        return universe

    async def _create_artifacts(
        self, session, artifact_service, universe_id, training_run_id, is_active=False
    ) -> list[uuid.UUID]:
        roles = ["lstm", "conformal", "residual_predictor"]
        ids = []
        for role in roles:
            art = await artifact_service.save_artifact(
                session,
                universe_id=universe_id,
                universe_slug="test-universe",
                model_role=role,
                training_run_id=training_run_id,
                data=b"mock-data",
            )
            ids.append(art.id)
        await session.flush()
        return ids

    async def _create_training_run(
        self,
        session,
        universe_id,
        validation_metrics: dict | None = None,
        status: str = "completed",
    ):
        run = TrainingRun(
            universe_id=universe_id,
            triggered_by="test",
            status=status,
            validation_metrics=validation_metrics,
        )
        session.add(run)
        await session.flush()
        return run

    async def test_first_training_auto_promotes(self, db_session, artifact_service):
        universe = await self._create_universe(db_session)
        universe_id = universe.id

        run = await self._create_training_run(
            db_session, universe_id, validation_metrics={"overall_mse": 0.01}
        )
        challenger_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, run.id
        )

        promoted, reason = await promote_challenger(
            session=db_session,
            artifact_service=artifact_service,
            challenger_artifact_ids=challenger_ids,
            challenger_metrics={"overall_mse": 0.01},
            universe_id=universe_id,
        )

        assert promoted is True
        assert "no champion" in reason.lower()
        for aid in challenger_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is True

    async def test_promotes_better_challenger(self, db_session, artifact_service):
        universe = await self._create_universe(db_session)
        universe_id = universe.id

        champion_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.10},
        )
        champion_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, champion_run.id
        )
        await artifact_service.activate_all(db_session, champion_ids)
        await db_session.flush()

        challenger_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.05},
        )
        challenger_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, challenger_run.id
        )

        promoted, reason = await promote_challenger(
            session=db_session,
            artifact_service=artifact_service,
            challenger_artifact_ids=challenger_ids,
            challenger_metrics={"overall_mse": 0.05},
            universe_id=universe_id,
        )

        assert promoted is True
        assert "promoted" in reason.lower()

        for aid in challenger_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is True, f"Challenger artifact {aid} not active"

        for aid in champion_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is False, f"Champion artifact {aid} still active"

    async def test_rejects_worse_challenger(self, db_session, artifact_service):
        universe = await self._create_universe(db_session)
        universe_id = universe.id

        champion_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.05},
        )
        champion_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, champion_run.id
        )
        await artifact_service.activate_all(db_session, champion_ids)
        await db_session.flush()

        challenger_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.10},
        )
        challenger_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, challenger_run.id
        )

        promoted, reason = await promote_challenger(
            session=db_session,
            artifact_service=artifact_service,
            challenger_artifact_ids=challenger_ids,
            challenger_metrics={"overall_mse": 0.10},
            universe_id=universe_id,
        )

        assert promoted is False
        assert "rejected" in reason.lower()

        for aid in challenger_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is False
            assert art.archived_at is not None

        for aid in champion_ids:
            art = await db_session.get(ModelArtifact, aid)
            assert art.is_active is True

    async def test_promotion_respects_margin(self, db_session, artifact_service):
        universe = await self._create_universe(db_session)
        universe_id = universe.id

        champion_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.10},
        )
        champion_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, champion_run.id
        )
        await artifact_service.activate_all(db_session, champion_ids)
        await db_session.flush()

        challenger_run = await self._create_training_run(
            db_session,
            universe_id,
            validation_metrics={"overall_mse": 0.099},
        )
        challenger_ids = await self._create_artifacts(
            db_session, artifact_service, universe_id, challenger_run.id
        )

        promoted, reason = await promote_challenger(
            session=db_session,
            artifact_service=artifact_service,
            challenger_artifact_ids=challenger_ids,
            challenger_metrics={"overall_mse": 0.099},
            universe_id=universe_id,
            promotion_margin=0.02,
        )

        assert promoted is False, (
            f"0.099 vs 0.10 is only 1% improvement, "
            f"should not pass 2% margin: {reason}"
        )
