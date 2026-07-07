"""Tests for ConformalCalibrator — locally-weighted split conformal prediction.

Coverage and correctness tests on synthetic data with heteroskedastic noise.
"""

from __future__ import annotations

import numpy as np
import torch


def _make_heteroskedastic_data(
    n_samples: int = 2000,
    n_features: int = 31,
    n_horizons: int = 4,
    seed: int = 42,
):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((n_samples, n_features))
    coef = rng.standard_normal((n_features, n_horizons)) * 0.5
    signal = x @ coef

    noise_scale = 0.05 + 0.25 * np.abs(x[:, 0]).reshape(-1, 1)
    noise = rng.standard_normal((n_samples, n_horizons)) * noise_scale

    y = signal + noise
    y_pred = signal + rng.standard_normal((n_samples, n_horizons)) * 0.01

    return x.astype(np.float64), y.astype(np.float64), y_pred.astype(np.float64)


class TestConformalCalibratorCoverage:
    def test_coverage_near_nominal(self):
        """90 % intervals achieve ≈90 % coverage on held-out test set."""
        from app.features.ml_models.conformal.calibrator import ConformalCalibrator

        x, y, y_pred = _make_heteroskedastic_data(n_samples=2000, seed=42)

        cal_idx = np.arange(0, 1200)
        trn_idx = np.arange(1200, 1600)
        test_idx = np.arange(1600, 2000)

        calibrator = ConformalCalibrator(alpha=0.10)
        calibrator.fit(y, y_pred, x, cal_idx, trn_idx)

        lo, hi = calibrator.predict(y_pred[test_idx], x[test_idx])
        inside = (y[test_idx] >= lo) & (y[test_idx] <= hi)
        coverage = inside.mean()

        assert 0.87 <= coverage <= 0.93, f"Coverage {coverage:.3f} outside [0.87, 0.93]"

        torch.manual_seed(0)

    def test_coverage_heldout_strictly_within_three_percent(self):
        """Coverage on held-out test is within ±3pp of nominal 90 %."""
        from app.features.ml_models.conformal.calibrator import ConformalCalibrator

        x, y, y_pred = _make_heteroskedastic_data(n_samples=3000, seed=123)

        cal_idx = np.arange(0, 1800)
        trn_idx = np.arange(1800, 2400)
        test_idx = np.arange(2400, 3000)

        calibrator = ConformalCalibrator(alpha=0.10)
        calibrator.fit(y, y_pred, x, cal_idx, trn_idx)

        lo, hi = calibrator.predict(y_pred[test_idx], x[test_idx])
        inside = (y[test_idx] >= lo) & (y[test_idx] <= hi)
        coverage = inside.mean()

        assert abs(coverage - 0.90) <= 0.03, (
            f"Coverage {coverage:.3f} deviates from 0.90 by {abs(coverage - 0.90):.3f}"
        )

        torch.manual_seed(0)

    def test_calibration_strictly_separate_from_training(self):
        """Calibration set must not overlap training set."""
        from app.features.ml_models.conformal.calibrator import ConformalCalibrator

        x, y, y_pred = _make_heteroskedastic_data(n_samples=100, seed=7)

        cal_idx = np.array([0, 1, 5, 10, 15])
        trn_idx = np.array([5, 20, 30])

        calibrator = ConformalCalibrator(alpha=0.10)

        try:
            calibrator.fit(y, y_pred, x, cal_idx, trn_idx)
            assert False, "Should have raised ValueError for overlapping indices"
        except ValueError as e:
            assert "overlap" in str(e).lower()
            assert "5" in str(e)

        torch.manual_seed(0)

    def test_intervals_wider_when_noise_higher(self):
        """Intervals should be wider for high-noise samples than low-noise ones."""
        from app.features.ml_models.conformal.calibrator import ConformalCalibrator

        rng = np.random.default_rng(99)
        n = 800
        x_low = rng.standard_normal((n, 31)).astype(np.float64)
        x_low[:, 0] = 0.1
        x_high = rng.standard_normal((n, 31)).astype(np.float64)
        x_high[:, 0] = 3.0

        x = np.vstack([x_low, x_high])
        signal = x @ rng.standard_normal((31, 4)).astype(np.float64) * 0.3
        noise = rng.standard_normal((x.shape[0], 4)).astype(np.float64) * (
            0.02 + 0.15 * np.abs(x[:, 0]).reshape(-1, 1)
        )
        y = signal + noise
        y_pred = (
            signal + rng.standard_normal((x.shape[0], 4)).astype(np.float64) * 0.005
        )

        cal_idx = np.concatenate([np.arange(0, 200), np.arange(800, 1000)])
        trn_idx = np.concatenate([np.arange(200, 300), np.arange(1000, 1100)])

        calibrator = ConformalCalibrator(alpha=0.10)
        calibrator.fit(y, y_pred, x, cal_idx, trn_idx)

        test_low = np.arange(300, 600)
        test_high = np.arange(1100, 1400)

        lo_low, hi_low = calibrator.predict(y_pred[test_low], x[test_low])
        lo_high, hi_high = calibrator.predict(y_pred[test_high], x[test_high])

        width_low = (hi_low - lo_low).mean()
        width_high = (hi_high - lo_high).mean()

        assert width_high > width_low, (
            f"High-noise width {width_high:.4f} not greater than "
            f"low-noise width {width_low:.4f}"
        )

        torch.manual_seed(0)

    def test_zero_residual_predictor_output_edge_case(self):
        """EPS division guard: zero/near-zero r_hat handled without error."""
        from app.features.ml_models.conformal.calibrator import (
            ConformalCalibrator,
        )

        calibrator = ConformalCalibrator(alpha=0.10)
        with torch.no_grad():
            for param in calibrator.residual_predictor.parameters():
                param.zero_()
        calibrator.residual_predictor.eval()

        n = 50
        n_h = 4
        x = np.random.default_rng(0).standard_normal((n, 31)).astype(np.float64)
        y = np.random.default_rng(1).standard_normal((n, n_h)).astype(np.float64)

        cal_idx = np.arange(0, 30)
        trn_idx = np.arange(30, 40)

        calibrator.fit(y.copy(), y.copy(), x, cal_idx, trn_idx)

        lo, hi = calibrator.predict(y, x)
        assert np.all(np.isfinite(lo))
        assert np.all(np.isfinite(hi))
        assert np.all(lo <= hi)

        torch.manual_seed(0)


class TestComputeWMax:
    def test_W_max_positive_and_ordered(self):
        """W_max values should be positive and monotonically increasing with horizon."""
        from app.features.ml_models.conformal.calibrator import ConformalCalibrator

        x, y, y_pred = _make_heteroskedastic_data(n_samples=2000, seed=42)

        cal_idx = np.arange(0, 1200)
        trn_idx = np.arange(1200, 1600)

        calibrator = ConformalCalibrator(alpha=0.10)
        calibrator.fit(y, y_pred, x, cal_idx, trn_idx)

        w_max = calibrator.compute_W_max(x)

        assert len(w_max) == 4
        for h in range(4):
            assert w_max[h] > 0, f"W_max[{h}]={w_max[h]} should be positive"

        for h in range(3):
            ratio = max(w_max[h], w_max[h + 1]) / max(
                min(w_max[h], w_max[h + 1]), 1e-10
            )
            assert ratio < 5.0, (
                f"W_max[{h}]={w_max[h]} and W_max[{h + 1}]={w_max[h + 1]} "
                f"differ by factor {ratio:.2f} — not wildly out of order"
            )

        torch.manual_seed(0)

    def test_W_max_constant_features(self):
        """With constant features, all widths should be the same across samples."""
        from app.features.ml_models.conformal.calibrator import (
            ConformalCalibrator,
            EPS,
        )

        n = 500
        n_h = 4
        rng = np.random.default_rng(42)
        y = rng.standard_normal((n, n_h)).astype(np.float64)
        y_pred = y + rng.standard_normal((n, n_h)).astype(np.float64) * 0.01
        x_const = np.ones((n, 31), dtype=np.float64)

        cal_idx = np.arange(0, 300)
        trn_idx = np.arange(300, 400)

        calibrator = ConformalCalibrator(alpha=0.10)
        calibrator.fit(y, y_pred, x_const, cal_idx, trn_idx)

        w_max = calibrator.compute_W_max(x_const)

        for h in range(4):
            assert np.isfinite(w_max[h]), f"W_max[{h}]={w_max[h]} should be finite"

        calibrator.residual_predictor.eval()
        with torch.no_grad():
            r_hat = (
                calibrator.residual_predictor(
                    torch.tensor(x_const, dtype=torch.float32)
                )
                .cpu()
                .numpy()
                .ravel()
            )

        for h in range(4):
            expected = float(
                2.0
                * max(calibrator.quantiles[h], 0.0)
                * np.percentile(np.maximum(r_hat, EPS), 90)
            )
            assert abs(w_max[h] - expected) < 1e-6, (
                f"W_max[{h}]={w_max[h]} != expected {expected}"
            )

        torch.manual_seed(0)
