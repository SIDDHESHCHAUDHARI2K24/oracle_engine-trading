import uuid
from datetime import date, timedelta

import numpy as np
from scipy.stats import entropy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.feature_engineering.models import FeatureMatrix
from app.features.feature_engineering.shared.feature_schema import input_feature_names
from app.features.ml_models.repository import get_latest_training_run
from app.features.monitoring import repository as monitoring_repo
from app.features.monitoring.service import AlertService
from app.features.universes.models import UniverseMembership

FEATURE_DRIFT_THRESHOLD = 0.3


class FeatureDriftSignal:
    @staticmethod
    def compute_kl_divergence(current_features, training_distribution, feature_name):
        baseline = training_distribution[feature_name]
        bin_edges = baseline["bin_edges"]
        baseline_hist = np.array(baseline["hist"], dtype=np.float64)

        current_hist, _ = np.histogram(current_features, bins=bin_edges)
        current_hist = current_hist.astype(np.float64)

        epsilon = 1e-10
        p = baseline_hist + epsilon
        q = current_hist + epsilon

        p = p / p.sum()
        q = q / q.sum()

        return float(entropy(p, q))

    @staticmethod
    async def compute_all_drift(
        session: AsyncSession,
        universe_id: uuid.UUID,
        measurement_date: date,
    ) -> None:
        training_run = await get_latest_training_run(session, universe_id)
        if training_run is None or not training_run.model_metadata:
            return

        training_distribution = training_run.model_metadata.get(
            "feature_distribution"
        )
        if training_distribution is None:
            return

        feature_names = input_feature_names()
        lookback_start = measurement_date - timedelta(days=252)

        ticker_subq = (
            select(UniverseMembership.ticker_id)
            .where(
                UniverseMembership.universe_id == universe_id,
                UniverseMembership.removed_at.is_(None),
            )
            .subquery()
        )

        stmt = (
            select(FeatureMatrix)
            .where(
                FeatureMatrix.ticker_id.in_(select(ticker_subq.c.ticker_id)),
                FeatureMatrix.bar_date >= lookback_start,
                FeatureMatrix.bar_date <= measurement_date,
            )
            .order_by(FeatureMatrix.bar_date)
        )

        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return

        feature_columns = {}
        for fname in feature_names:
            feature_columns[fname] = np.array(
                [
                    float(getattr(r, fname))
                    for r in rows
                    if getattr(r, fname) is not None
                ],
                dtype=np.float64,
            )

        any_breach = False
        alert_service = AlertService()

        for fname in feature_names:
            if fname not in training_distribution:
                continue

            current_data = feature_columns.get(fname)
            if current_data is None or len(current_data) < 10:
                kl = None
                breached = False
            else:
                kl = FeatureDriftSignal.compute_kl_divergence(
                    current_data, training_distribution, fname
                )
                breached = kl > FEATURE_DRIFT_THRESHOLD

            await monitoring_repo.upsert_drift_metric(
                session,
                universe_id=universe_id,
                feature_name=fname,
                measurement_date=measurement_date,
                kl_divergence=kl,
                threshold_breached=breached,
                training_run_id=training_run.id,
            )

            if breached:
                any_breach = True

        if any_breach:
            await alert_service.raise_alert(
                session,
                severity="warning",
                code="FEATURE_DRIFT",
                message=(
                    f"Feature drift detected for universe {universe_id} "
                    f"on {measurement_date}"
                ),
                universe_id=universe_id,
                context={
                    "measurement_date": str(measurement_date),
                    "training_run_id": str(training_run.id),
                },
            )
