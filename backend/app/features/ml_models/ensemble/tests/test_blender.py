"""Tests for RegimeBlender — uncertainty-aware LSTM/TFT ensemble blending.

Verifies the locked design formula: weight responds monotonically to
TFT quantile spread, clipped to [0.40, 0.80], symmetric across all
4 prediction horizons.
"""

import numpy as np
import pytest


class TestRegimeBlender:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.ensemble.blender import RegimeBlender

        self.RegimeBlender = RegimeBlender

    def _prime_buffer(self, blender, n: int = 50) -> None:
        """Feed alternating spreads around 0.05 to populate buffer with
        non-zero standard deviation (mean ≈ 0.05, std ≈ 0.01)."""
        for i in range(n):
            s = 0.04 if i % 2 == 0 else 0.06
            blender._spread_buffer.append(s)

    def test_high_tft_spread_shifts_weight_toward_lstm(self):
        """Wider TFT quantile spread → higher lstm_w → blend near LSTM pred."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender)
        result = blender.blend_horizon(1.0, 0.0, 0.0, 2.0)
        assert result == pytest.approx(0.80, rel=0.05)

    def test_low_tft_spread_shifts_weight_toward_tft(self):
        """Narrow TFT quantile spread → lower lstm_w → blend near TFT median."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender)
        result = blender.blend_horizon(1.0, 0.499, 0.0, 0.501)
        assert result == pytest.approx(0.40, rel=0.05)

    def test_weights_always_clipped_to_0_40_0_80(self):
        """LSTM weight must never escape [0.40, 0.80] regardless of spread."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender)

        r_high = blender.blend_horizon(1.0, 0.0, 0.0, 100.0)
        assert r_high <= 0.80
        assert r_high >= 0.60

        r_low = blender.blend_horizon(1.0, 0.4999, 0.0, 0.5001)
        assert r_low >= 0.40
        assert r_low <= 0.60

    def test_at_average_spread_blend_is_approx_60_40(self):
        """When z-score ≈ 0 the weight reverts to base_lstm_w = 0.60."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender, n=100)
        result = blender.blend_horizon(1.0, 0.475, 0.0, 0.525)
        assert result == pytest.approx(0.60, rel=0.05)

    def test_all_four_horizons_use_identical_rule(self):
        """blend_all applies the same blending formula to every horizon."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender, n=50)
        N, H = 3, 4
        lstm_preds = np.tile(np.array([1.0, 0.5, 2.0]).reshape(-1, 1), (1, H))
        tft_quantiles = {
            "q10": np.tile(np.array([0.4, 0.2, 1.8]).reshape(-1, 1), (1, H)),
            "q50": np.tile(np.array([0.5, 0.3, 1.9]).reshape(-1, 1), (1, H)),
            "q90": np.tile(np.array([0.6, 0.4, 2.0]).reshape(-1, 1), (1, H)),
        }
        result = blender.blend_all(lstm_preds, tft_quantiles)
        for i in range(N):
            assert np.allclose(result[i], result[i, 0])

    def test_blend_all_returns_correct_shape(self):
        """blend_all output must be [N, 4] matching input rows and horizons."""
        blender = self.RegimeBlender()
        self._prime_buffer(blender, n=50)
        N, H = 10, 4
        lstm_preds = np.random.default_rng(42).random((N, H))
        tft_quantiles = {
            "q10": np.random.default_rng(43).random((N, H)) - 0.05,
            "q50": np.random.default_rng(44).random((N, H)),
            "q90": np.random.default_rng(45).random((N, H)) + 0.05,
        }
        result = blender.blend_all(lstm_preds, tft_quantiles)
        assert result.shape == (N, H)

    def test_buffer_starts_empty_returns_neutral_z(self):
        """Before any history the z-score is 0 → weight stays at base."""
        blender = self.RegimeBlender()
        result = blender.blend_horizon(1.0, 0.0, 0.0, 2.0)
        assert result == pytest.approx(0.60, rel=0.05)
