import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.features.monitoring.signals.drift import (
    FeatureDriftSignal,
)


def make_training_distribution(feature_name, data, bins=50):
    hist, bin_edges = np.histogram(data, bins=bins)
    return {
        feature_name: {
            "hist": hist.tolist(),
            "bin_edges": bin_edges.tolist(),
            "mean": float(np.mean(data)),
            "std": float(np.std(data)),
        }
    }


class TestComputeKlDivergence:
    def test_identical_distribution_zero_kl(self):
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, 10000)
        training_dist = make_training_distribution("feature_a", data)

        kl = FeatureDriftSignal.compute_kl_divergence(
            current_features=data,
            training_distribution=training_dist,
            feature_name="feature_a",
        )
        assert kl < 0.1

    def test_shifted_distribution_positive_kl(self):
        rng = np.random.default_rng(42)
        baseline = rng.normal(0, 1, 10000)
        training_dist = make_training_distribution("feature_a", baseline)

        shifted = rng.normal(2, 1, 10000)
        kl = FeatureDriftSignal.compute_kl_divergence(
            current_features=shifted,
            training_distribution=training_dist,
            feature_name="feature_a",
        )
        assert kl > 0.3

    def test_empty_bin_not_infinity(self):
        rng = np.random.default_rng(42)
        baseline = rng.normal(0, 1, 10000)
        training_dist = make_training_distribution("feature_a", baseline)

        sparse_data = rng.normal(0, 0.1, 5000)
        kl = FeatureDriftSignal.compute_kl_divergence(
            current_features=sparse_data,
            training_distribution=training_dist,
            feature_name="feature_a",
        )
        assert not np.isinf(kl)
        assert not np.isnan(kl)
        assert kl >= 0


class TestComputeAllDrift:
    @pytest.mark.asyncio
    async def test_missing_training_distribution_skipped(self):
        mock_session = AsyncMock()
        mock_training_run = MagicMock()
        mock_training_run.model_metadata = {}
        mock_training_run.id = uuid.uuid4()

        with patch(
            "app.features.monitoring.signals.drift.get_latest_training_run",
            return_value=mock_training_run,
        ):
            await FeatureDriftSignal.compute_all_drift(
                session=mock_session,
                universe_id=uuid.uuid4(),
                measurement_date=date(2025, 6, 1),
            )

        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_breach_raises_warning(self):
        universe_id = uuid.uuid4()
        training_run_id = uuid.uuid4()
        measurement_date = date(2025, 6, 1)

        rng = np.random.default_rng(42)
        baseline = rng.normal(0, 1, 10000)
        training_dist = make_training_distribution("open", baseline)

        mock_training_run = MagicMock()
        mock_training_run.model_metadata = {"feature_distribution": training_dist}
        mock_training_run.id = training_run_id

        shifted = rng.normal(5, 1, 500)
        feature_names = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "returns_1d",
            "returns_5d",
            "returns_10d",
            "returns_20d",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_hist",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "bb_width",
            "atr_14",
            "volatility_20d",
            "volume_z_score",
            "sma_50",
            "sma_200",
            "price_to_sma50",
            "price_to_sma200",
            "fed_funds_rate",
            "cpi",
            "unemployment",
            "gdp",
            "yield_spread_10y_2y",
            "vix",
            "high_yield_spread",
        ]

        feature_rows = []
        for i in range(20):
            row = MagicMock()
            for fname in feature_names:
                setattr(row, fname, None)
            setattr(row, "open", float(shifted[i]))
            feature_rows.append(row)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = feature_rows

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with (
            patch(
                "app.features.monitoring.signals.drift.get_latest_training_run",
                return_value=mock_training_run,
            ),
            patch(
                "app.features.monitoring.signals.drift.AlertService",
            ) as mock_alert_cls,
        ):
            mock_alert_instance = mock_alert_cls.return_value
            mock_alert_instance.raise_alert = AsyncMock()

            await FeatureDriftSignal.compute_all_drift(
                session=mock_session,
                universe_id=universe_id,
                measurement_date=measurement_date,
            )

            mock_alert_instance.raise_alert.assert_called_once()
            call_kwargs = mock_alert_instance.raise_alert.call_args.kwargs
            assert call_kwargs["severity"] == "warning"
            assert call_kwargs["code"] == "FEATURE_DRIFT"
            assert call_kwargs["universe_id"] == universe_id
