"""Equity feature engineer — computes all 19 technical indicators.

Primary implementation uses pure pandas/numpy (no external TA library
dependency).  All calculations are vectorized — no Python row loops.

TA-Lib may be used as a speed optimization if available in the runtime
environment, but the pure-pandas path is the primary and tested path.
"""

import logging

import numpy as np
import pandas as pd

from app.features.feature_engineering.technical.base import BaseFeatureEngineer

logger = logging.getLogger(__name__)

_TA_LIB_AVAILABLE = False
try:
    import talib  # noqa: F401

    _TA_LIB_AVAILABLE = True
    logger.info("TA-Lib available — using for technical indicators")
except ImportError:
    logger.info("TA-Lib not available — using pure-pandas fallback")


class EquityFeatureEngineer(BaseFeatureEngineer):
    """Compute the 19 equity technical features per the locked schema.

    Input DataFrame must have columns: open, high, low, close, volume.
    Features are **appended** — raw columns are never overwritten.
    """

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        df["returns_1d"] = close.pct_change(1)
        df["returns_5d"] = close.pct_change(5)
        df["returns_10d"] = close.pct_change(10)
        df["returns_20d"] = close.pct_change(20)

        df["rsi_14"] = self._compute_rsi(close, window=14)

        macd_line, macd_signal, macd_hist = self._compute_macd(close)
        df["macd"] = macd_line
        df["macd_signal"] = macd_signal
        df["macd_hist"] = macd_hist

        bb_upper, bb_middle, bb_lower = self._compute_bollinger(close)
        df["bb_upper"] = bb_upper
        df["bb_middle"] = bb_middle
        df["bb_lower"] = bb_lower
        df["bb_width"] = (bb_upper - bb_lower) / bb_middle

        df["atr_14"] = self._compute_atr(high, low, close, window=14)

        df["sma_50"] = close.rolling(window=50).mean()
        df["sma_200"] = close.rolling(window=200).mean()

        returns_1d_series = df["returns_1d"]
        df["volatility_20d"] = returns_1d_series.rolling(window=20).std() * np.sqrt(252)

        volume_mean_20 = volume.rolling(window=20).mean()
        volume_std_20 = volume.rolling(window=20).std()
        df["volume_z_score"] = (volume - volume_mean_20) / volume_std_20

        df["price_to_sma50"] = close / df["sma_50"]
        df["price_to_sma200"] = close / df["sma_200"]

        return df

    @staticmethod
    def _compute_rsi(close: pd.Series, window: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    @staticmethod
    def _compute_macd(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        macd_signal = macd_line.ewm(span=signal, adjust=False).mean()
        macd_hist = macd_line - macd_signal
        return macd_line, macd_signal, macd_hist

    @staticmethod
    def _compute_bollinger(
        close: pd.Series,
        window: int = 20,
        num_std: float = 2.0,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        middle = close.rolling(window=window).mean()
        std = close.rolling(window=window).std()
        upper = middle + num_std * std
        lower = middle - num_std * std
        return upper, middle, lower

    @staticmethod
    def _compute_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        window: int = 14,
    ) -> pd.Series:
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.ewm(alpha=1 / window, adjust=False).mean()
        return atr
