import json
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

from app.features.ml_models.models import TrainingRun


async def _seed_universe(db_session, universe_id, name):
    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, display_name, created_at) "
            "VALUES (:id, :name, :dn, now())"
        ),
        {"id": universe_id, "name": name, "dn": f"Display {name}"},
    )


async def _seed_training_run(
    db_session, run_id, universe_id, validation_metrics, model_metadata=None
):
    run = TrainingRun(
        id=run_id,
        universe_id=universe_id,
        triggered_by="test",
        status="completed",
        validation_metrics=validation_metrics,
        model_metadata=model_metadata or {},
    )
    db_session.add(run)
    await db_session.flush()


async def _read_training_run_metadata(db_session, run_id):
    row = await db_session.execute(
        text("SELECT metadata FROM training_runs WHERE id = :rid"),
        {"rid": run_id},
    )
    result = row.scalar()
    if isinstance(result, str):
        result = json.loads(result)
    return result


@pytest.mark.asyncio
class TestLossCurveSignal:
    async def test_overfitting_detected(self, db_session):
        from app.features.monitoring.signals.loss_curve import LossCurveSignal

        universe_id = uuid.uuid4()
        run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-loss1")

        train_losses = [0.9, 0.8, 0.7, 0.6, 0.5]
        val_losses = [0.7, 0.71, 0.72, 0.73, 0.74]
        validation_metrics = {
            "train_losses": train_losses,
            "val_losses": val_losses,
        }
        await _seed_training_run(
            db_session, run_id, universe_id, validation_metrics
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = LossCurveSignal(alert_service=mock_alert)
        result = await signal.compute(db_session, universe_id)

        assert result is True

        mock_alert.raise_alert.assert_awaited_once()
        call_args = mock_alert.raise_alert.call_args
        assert call_args.kwargs["severity"] == "warning"
        assert call_args.kwargs["code"] == "OVERFITTING_DETECTED"
        assert call_args.kwargs["universe_id"] == universe_id

        metadata = await _read_training_run_metadata(db_session, run_id)
        assert "signal_loss_curve" in metadata
        assert metadata["signal_loss_curve"]["overfitting_detected"] is True

    async def test_no_overfitting_when_both_falling(self, db_session):
        from app.features.monitoring.signals.loss_curve import LossCurveSignal

        universe_id = uuid.uuid4()
        run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-loss2")

        train_losses = [0.9, 0.85, 0.8, 0.75, 0.7]
        val_losses = [0.8, 0.78, 0.76, 0.74, 0.72]
        validation_metrics = {
            "train_losses": train_losses,
            "val_losses": val_losses,
        }
        await _seed_training_run(
            db_session, run_id, universe_id, validation_metrics
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = LossCurveSignal(alert_service=mock_alert)
        result = await signal.compute(db_session, universe_id)

        assert result is False
        mock_alert.raise_alert.assert_not_awaited()

    async def test_no_overfitting_short_window(self, db_session):
        from app.features.monitoring.signals.loss_curve import LossCurveSignal

        universe_id = uuid.uuid4()
        run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-loss3")

        train_losses = [0.9, 0.8, 0.7]
        val_losses = [0.7, 0.75, 0.8]
        validation_metrics = {
            "train_losses": train_losses,
            "val_losses": val_losses,
        }
        await _seed_training_run(
            db_session, run_id, universe_id, validation_metrics
        )
        await db_session.flush()

        mock_alert = AsyncMock()
        signal = LossCurveSignal(alert_service=mock_alert)
        result = await signal.compute(db_session, universe_id)

        assert result is False
        mock_alert.raise_alert.assert_not_awaited()
