"""Conviction scoring — z-score derived from TFT quantile spread.

Per DESIGN §6: sigma from 10-90 spread, z = y_pred / sigma, linear map to [0, 100].
"""

import numpy as np


SPREAD_DIVISOR = 2.563


def compute_conviction(
    y_pred: np.ndarray, tft_q10: np.ndarray, tft_q90: np.ndarray
) -> np.ndarray:
    sigma = (tft_q90 - tft_q10) / SPREAD_DIVISOR
    z = y_pred / (sigma + 1e-9)
    raw = z * 25 + 50
    return np.clip(raw, 0.0, 100.0)
