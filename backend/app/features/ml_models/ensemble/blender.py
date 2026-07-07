"""Uncertainty-aware RegimeBlender — blends LSTM point estimates with TFT
quantiles driven by TFT quantile spread.

Per locked deviation #3: wider TFT spread (more TFT uncertainty) leans
toward the LSTM. Weights clipped to [0.40, 0.80]. Symmetric across all
4 horizons.
"""

from collections import deque

import numpy as np


class RegimeBlender:
    """Blend LSTM point estimates with TFT median using uncertainty-aware
    weights driven by the TFT quantile spread.

    Design formula:
        tft_spread = q90 - q10
        spread_z = rolling z-score of recent spreads
        lstm_w = clip(base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
        blended = lstm_pred * lstm_w + tft_q50 * (1 - lstm_w)
    """

    def __init__(self, base_lstm_w: float = 0.60):
        self.base_lstm_w = base_lstm_w
        self._spread_buffer: deque[float] = deque(maxlen=200)

    def blend_horizon(self, lstm_pred, tft_q10, tft_q50, tft_q90):
        tft_spread = tft_q90 - tft_q10
        spread_z = self._normalize(tft_spread)
        lstm_w = np.clip(self.base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
        return lstm_pred * lstm_w + tft_q50 * (1 - lstm_w)

    def blend_all(self, lstm_preds, tft_quantiles):
        N, H = lstm_preds.shape
        blended = np.zeros((N, H))
        for h in range(H):
            for i in range(N):
                blended[i, h] = self.blend_horizon(
                    lstm_preds[i, h],
                    tft_quantiles["q10"][i, h],
                    tft_quantiles["q50"][i, h],
                    tft_quantiles["q90"][i, h],
                )
        return blended

    def _normalize(self, spread) -> float:
        spread_f = float(spread)
        if len(self._spread_buffer) < 2:
            self._spread_buffer.append(spread_f)
            return 0.0
        buf = np.array(self._spread_buffer, dtype=np.float64)
        mean = buf.mean()
        std = buf.std(ddof=0)
        if std < 1e-12:
            self._spread_buffer.append(spread_f)
            return 0.0
        z = (spread_f - mean) / std
        self._spread_buffer.append(spread_f)
        return z
