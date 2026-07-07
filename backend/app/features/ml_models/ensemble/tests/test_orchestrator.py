"""Tests for EnsembleOrchestrator — blender + calibrator + scorer integration.

Uses deterministic mock objects so orchestration logic (field wiring,
shape propagation, conviction bounds) can be verified without real models.
"""

import numpy as np
import pytest

from unittest.mock import Mock


N_SAMPLES = 10
N_HORIZONS = 4
N_FEATURES = 31
HORIZON_LABELS = ["t1", "t5", "t10", "t15"]


class MockBlender:
    def blend_horizon(self, lstm_pred, tft_q10, tft_q50, tft_q90):
        return 0.6 * lstm_pred + 0.4 * tft_q50


class MockCalibrator:
    def predict(self, blended, features):
        return blended - 0.02, blended + 0.02


class MockScorer:
    def compute_conviction(self, y_pred, tft_q10, tft_q90):
        sigma = (tft_q90 - tft_q10) / 2.563
        z = y_pred / (sigma + 1e-9)
        raw = z * 25 + 50
        return np.clip(raw, 0.0, 100.0)


class TestEnsembleOrchestrator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.ensemble.orchestrator import EnsembleOrchestrator

        self.EnsembleOrchestrator = EnsembleOrchestrator

        rng = np.random.default_rng(42)
        self.lstm = rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.02
        self.tft = {
            "q10": (rng.standard_normal((N_SAMPLES, N_HORIZONS)) * 0.015 - 0.01).astype(np.float64),
            "q50": (rng.standard_normal((N_SAMPLES, N_HORIZONS)) * 0.01 + 0.005).astype(np.float64),
            "q90": (rng.standard_normal((N_SAMPLES, N_HORIZONS)) * 0.015 + 0.02).astype(np.float64),
        }
        self.features = rng.standard_normal((N_SAMPLES, N_FEATURES)).astype(np.float64)

        self.orchestrator = self.EnsembleOrchestrator(
            blender=MockBlender(),
            calibrator=MockCalibrator(),
            scorer=MockScorer(),
        )

    def test_predict_returns_all_20_fields(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        assert len(result) == 20, f"Expected 20 fields, got {len(result)}"

        for label in HORIZON_LABELS:
            assert f"pred_{label}" in result
            assert f"pred_lo_{label}" in result
            assert f"pred_hi_{label}" in result
            assert f"conviction_{label}" in result

        assert "lstm_outputs" in result
        assert "tft_q10" in result
        assert "tft_q50" in result
        assert "tft_q90" in result

    def test_conviction_scores_in_zero_one_hundred(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        for label in HORIZON_LABELS:
            scores = result[f"conviction_{label}"]
            assert np.all(scores >= 0.0), f"conviction_{label} below 0"
            assert np.all(scores <= 100.0), f"conviction_{label} above 100"

    def test_conviction_scores_are_finite(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        for label in HORIZON_LABELS:
            assert np.all(np.isfinite(result[f"conviction_{label}"]))

    def test_raw_component_arrays_match_inputs(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        assert result["lstm_outputs"].shape == (N_SAMPLES, N_HORIZONS)
        assert result["tft_q10"].shape == (N_SAMPLES, N_HORIZONS)
        assert result["tft_q50"].shape == (N_SAMPLES, N_HORIZONS)
        assert result["tft_q90"].shape == (N_SAMPLES, N_HORIZONS)

        np.testing.assert_array_equal(result["lstm_outputs"], self.lstm)
        np.testing.assert_array_equal(result["tft_q10"], self.tft["q10"])
        np.testing.assert_array_equal(result["tft_q50"], self.tft["q50"])
        np.testing.assert_array_equal(result["tft_q90"], self.tft["q90"])

    def test_pred_outputs_have_correct_shape(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        for label in HORIZON_LABELS:
            assert result[f"pred_{label}"].shape == (N_SAMPLES,)
            assert result[f"pred_lo_{label}"].shape == (N_SAMPLES,)
            assert result[f"pred_hi_{label}"].shape == (N_SAMPLES,)
            assert result[f"conviction_{label}"].shape == (N_SAMPLES,)

    def test_pred_lo_less_equal_pred_hi(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        for label in HORIZON_LABELS:
            lo = result[f"pred_lo_{label}"]
            hi = result[f"pred_hi_{label}"]
            assert np.all(lo <= hi), f"pred_lo_{label} > pred_hi_{label}"

    def test_blender_calibrator_scorer_work_together(self):
        result = self.orchestrator.predict(self.lstm.copy(), self.tft.copy(), self.features.copy())

        for label in HORIZON_LABELS:
            pred = result[f"pred_{label}"]
            lo = result[f"pred_lo_{label}"]
            hi = result[f"pred_hi_{label}"]
            conv = result[f"conviction_{label}"]

            assert pred.shape == lo.shape == hi.shape == conv.shape
            assert np.all(np.isfinite(pred))
            assert np.all(np.isfinite(lo))
            assert np.all(np.isfinite(hi))
            assert np.all(np.isfinite(conv))

    def test_predict_does_not_mutate_inputs(self):
        lstm_copy = self.lstm.copy()
        tft_copy = {k: v.copy() for k, v in self.tft.items()}
        features_copy = self.features.copy()

        self.orchestrator.predict(lstm_copy, tft_copy, features_copy)

        np.testing.assert_array_equal(lstm_copy, self.lstm)
        for k in self.tft:
            np.testing.assert_array_equal(tft_copy[k], self.tft[k])
        np.testing.assert_array_equal(features_copy, self.features)

    def test_conviction_extreme_spreads_remain_bounded(self):
        rng = np.random.default_rng(77)

        narrow_lstm = np.zeros((N_SAMPLES, N_HORIZONS), dtype=np.float64)
        narrow_tft = {
            "q10": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.01,
            "q50": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.01,
            "q90": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.01 + 0.0001,
        }

        result = self.orchestrator.predict(narrow_lstm, narrow_tft, self.features.copy())
        for label in HORIZON_LABELS:
            scores = result[f"conviction_{label}"]
            assert np.all(scores >= 0.0) and np.all(scores <= 100.0)

        wide_lstm = np.ones((N_SAMPLES, N_HORIZONS), dtype=np.float64) * 0.05
        wide_tft = {
            "q10": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.001 - 0.05,
            "q50": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.001,
            "q90": rng.standard_normal((N_SAMPLES, N_HORIZONS)).astype(np.float64) * 0.001 + 0.05,
        }

        result = self.orchestrator.predict(wide_lstm, wide_tft, self.features.copy())
        for label in HORIZON_LABELS:
            scores = result[f"conviction_{label}"]
            assert np.all(scores >= 0.0) and np.all(scores <= 100.0)


class TestComputeConvictionFormula:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.ml_models.ensemble.scoring import compute_conviction

        self.compute_conviction = compute_conviction

    def test_positive_prediction_yields_high_conviction(self):
        y_pred = np.array([[0.02, 0.0, 0.0, 0.0]], dtype=np.float64)
        q10 = np.array([[-0.005, 0.0, 0.0, 0.0]], dtype=np.float64)
        q90 = np.array([[0.025, 0.0, 0.0, 0.0]], dtype=np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        expected = 25 * (0.02 / ((0.03) / 2.563)) + 50
        assert scores[0, 0] == pytest.approx(expected, rel=0.001)
        assert scores[0, 0] > 50.0

    def test_negative_prediction_yields_low_conviction(self):
        y_pred = np.array([[-0.015, 0.0, 0.0, 0.0]], dtype=np.float64)
        q10 = np.array([[-0.03, 0.0, 0.0, 0.0]], dtype=np.float64)
        q90 = np.array([[0.006, 0.0, 0.0, 0.0]], dtype=np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        expected = 25 * (-0.015 / ((0.036) / 2.563)) + 50
        assert scores[0, 0] == pytest.approx(expected, rel=0.001)
        assert scores[0, 0] < 50.0

    def test_docstring_example_1(self):
        y_pred = np.array([[0.02, 0.0, 0.0, 0.0]], dtype=np.float64)
        spread = 0.015 * 2.563
        q10 = np.array([[-spread / 2, 0.0, 0.0, 0.0]], dtype=np.float64)
        q90 = np.array([[spread / 2, 0.0, 0.0, 0.0]], dtype=np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        assert scores[0, 0] == pytest.approx(83.3, rel=0.01)

    def test_docstring_example_2(self):
        y_pred = np.array([[-0.015, 0.0, 0.0, 0.0]], dtype=np.float64)
        spread = 0.018 * 2.563
        q10 = np.array([[-spread / 2, 0.0, 0.0, 0.0]], dtype=np.float64)
        q90 = np.array([[spread / 2, 0.0, 0.0, 0.0]], dtype=np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        assert scores[0, 0] == pytest.approx(29.1, rel=0.01)

    def test_zero_sigma_gives_clipped_output(self):
        y_pred = np.array([[0.01, -0.01, 0.0, 0.0]], dtype=np.float64)
        q10 = np.array([[0.0, 0.0, 0.0, 0.0]], dtype=np.float64)
        q90 = np.array([[0.0, 0.0, 0.0, 0.0]], dtype=np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        assert scores[0, 0] == pytest.approx(100.0)
        assert scores[0, 1] == pytest.approx(0.0)

    def test_output_shape_matches_input(self):
        rng = np.random.default_rng(123)
        N = 5
        y_pred = rng.standard_normal((N, 4)).astype(np.float64) * 0.02
        q10 = (rng.standard_normal((N, 4)) * 0.01 - 0.02).astype(np.float64)
        q90 = (rng.standard_normal((N, 4)) * 0.01 + 0.02).astype(np.float64)

        scores = self.compute_conviction(y_pred, q10, q90)

        assert scores.shape == (N, 4)
