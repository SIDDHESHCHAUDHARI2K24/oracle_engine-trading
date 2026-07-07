"""Locally-weighted split conformal prediction for multi-horizon forecasts.

Architecture pinned from spec: ResidualPredictor [31→16→8→1] + Softplus,
calibration via (1-alpha) quantile of normalized absolute residuals.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import torch
from torch import nn


class ResidualPredictor(nn.Module):
    """Small MLP predicting expected absolute residual from 31-dim features."""

    def __init__(self) -> None:
        super().__init__()
        self.model = nn.Sequential(
            nn.Linear(31, 16),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(8, 1),
            nn.Softplus(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)


EPS = 1e-8


def _train_residual_predictor(
    model: ResidualPredictor,
    features: np.ndarray,
    residuals: np.ndarray,
    n_epochs: int = 200,
    lr: float = 1e-3,
    patience: int = 20,
) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    x_tensor = torch.tensor(features, dtype=torch.float32)
    y_tensor = torch.tensor(residuals, dtype=torch.float32).reshape(-1, 1)

    best_loss = float("inf")
    best_state: dict | None = None
    wait = 0

    model.train()
    for _ in range(n_epochs):
        optimizer.zero_grad()
        pred = model(x_tensor)
        loss = loss_fn(pred, y_tensor)
        loss.backward()
        optimizer.step()

        current = loss.item()
        if current < best_loss - 1e-6:
            best_loss = current
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            wait = 0
        else:
            wait += 1
            if wait >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)


class ConformalCalibrator:
    """Locally-weighted split conformal predictor.

    Calibrates per-horizon quantiles so that prediction intervals satisfy
    P(Y ∈ [lo, hi]) ≥ 1 - alpha on held-out calibration data.
    """

    def __init__(self, alpha: float = 0.10) -> None:
        if not 0 < alpha < 1:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        self.alpha = alpha
        self.residual_predictor = ResidualPredictor()
        self.quantiles: dict[int, float] = {}

    def fit(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        features: np.ndarray,
        calibration_indices: np.ndarray,
        training_indices: np.ndarray,
    ) -> None:
        """Calibrate on a held-out calibration split.

        Args:
            y_true: shape (n_samples, n_horizons)
            y_pred: shape (n_samples, n_horizons)
            features: shape (n_samples, 31)
            calibration_indices: 1-d integer array of calibration row indices
            training_indices: 1-d integer array of training row indices
        """
        cal_set = set(int(i) for i in calibration_indices)
        trn_set = set(int(i) for i in training_indices)
        overlap = cal_set & trn_set
        if overlap:
            raise ValueError(
                f"Calibration indices overlap with training indices: {overlap}"
            )

        residuals = np.abs(y_true[calibration_indices] - y_pred[calibration_indices])

        _train_residual_predictor(
            self.residual_predictor,
            features[calibration_indices],
            residuals.mean(axis=1),
        )

        self.residual_predictor.eval()
        with torch.no_grad():
            r_hat = (
                self.residual_predictor(
                    torch.tensor(features[calibration_indices], dtype=torch.float32)
                )
                .cpu()
                .numpy()
                .ravel()
            )

        r_hat = np.maximum(r_hat, EPS)

        n_horizons = y_true.shape[1]
        self.quantiles = {}
        for h in range(n_horizons):
            s = residuals[:, h] / r_hat
            q = np.quantile(s, 1 - self.alpha)  # type: ignore[call-overload]
            self.quantiles[h] = float(q)

    def predict(
        self,
        y_pred: np.ndarray,
        features: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Produce prediction intervals.

        Args:
            y_pred: shape (n_samples, n_horizons)
            features: shape (n_samples, 31)

        Returns:
            (lo, hi) each shape (n_samples, n_horizons)
        """
        if not self.quantiles:
            raise RuntimeError("Calibrator has not been fit — call fit() first.")

        self.residual_predictor.eval()
        with torch.no_grad():
            r_hat = (
                self.residual_predictor(torch.tensor(features, dtype=torch.float32))
                .cpu()
                .numpy()
                .ravel()
            )

        r_hat = np.maximum(r_hat, EPS)
        n_samples, n_horizons = y_pred.shape
        lo = np.empty_like(y_pred)
        hi = np.empty_like(y_pred)

        for h in range(n_horizons):
            q = self.quantiles.get(h, 0.0)
            lo[:, h] = y_pred[:, h] - q * r_hat
            hi[:, h] = y_pred[:, h] + q * r_hat

        return lo, hi

    def compute_W_max(self, features: np.ndarray) -> dict[int, float]:
        """Compute the per-horizon 90th-percentile conformal interval width.

        Args:
            features: shape (n_samples, 31) — calibration set features

        Returns:
            dict mapping horizon index (0=t1, 1=t5, 2=t10, 3=t15) to
            90th-percentile width.
        """
        if not self.quantiles:
            raise RuntimeError("Calibrator has not been fit — call fit() first.")

        self.residual_predictor.eval()
        with torch.no_grad():
            r_hat = (
                self.residual_predictor(torch.tensor(features, dtype=torch.float32))
                .cpu()
                .numpy()
                .ravel()
            )
        r_hat = np.maximum(r_hat, EPS)

        w_max: dict[int, float] = {}
        for h, q_h in self.quantiles.items():
            widths = 2.0 * q_h * r_hat
            w_max[h] = float(np.percentile(widths, 90))
        return w_max
