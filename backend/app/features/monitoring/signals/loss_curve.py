import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ml_models import repository as ml_repo
from app.features.monitoring.service import AlertService


class LossCurveSignal:
    def __init__(self, alert_service: AlertService | None = None) -> None:
        self._alert_service = alert_service or AlertService()

    async def compute(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
    ) -> bool:
        training_run = await ml_repo.get_latest_training_run(session, universe_id)
        if training_run is None:
            return False

        validation_metrics = training_run.validation_metrics or {}
        train_losses = list(validation_metrics.get("train_losses", []))
        val_losses = list(validation_metrics.get("val_losses", []))

        is_overfitting = self.detect_overfitting(train_losses, val_losses, window=5)

        metadata = dict(training_run.model_metadata or {})
        metadata["signal_loss_curve"] = {
            "overfitting_detected": is_overfitting,
            "last_train_losses": train_losses[-5:] if len(train_losses) >= 5 else train_losses,
            "last_val_losses": val_losses[-5:] if len(val_losses) >= 5 else val_losses,
        }
        training_run.model_metadata = metadata
        await session.flush()

        if is_overfitting:
            await self._alert_service.raise_alert(
                session,
                severity="warning",
                code="OVERFITTING_DETECTED",
                message=(
                    f"Overfitting detected in training run {training_run.id}: "
                    f"train loss falling while validation loss rising over last 5 epochs"
                ),
                universe_id=universe_id,
                context={
                    "training_run_id": str(training_run.id),
                    "last_train_loss": train_losses[-1],
                    "last_val_loss": val_losses[-1],
                },
            )

        return is_overfitting

    @staticmethod
    def detect_overfitting(
        train_losses: list[float],
        val_losses: list[float],
        window: int = 5,
    ) -> bool:
        if len(train_losses) < window or len(val_losses) < window:
            return False

        recent_train = train_losses[-window:]
        recent_val = val_losses[-window:]

        train_falling = recent_train[0] > recent_train[-1]
        val_rising = recent_val[0] < recent_val[-1]

        return train_falling and val_rising
