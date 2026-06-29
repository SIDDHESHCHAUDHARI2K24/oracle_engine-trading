"""Tests for the EquityFeatureEngineer.

Follows TDD: these tests are written FIRST and expected to FAIL (RED)
before the implementation exists.
"""

import numpy as np
import pandas as pd
import pytest

from app.features.feature_engineering.technical.base import BaseFeatureEngineer
from app.features.feature_engineering.shared.feature_schema import technical_names


def make_ohlcv_fixture(n_rows: int = 300) -> pd.DataFrame:
    """Create deterministic OHLCV fixture for reproducible tests."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    base = 100.0
    close = base + rng.standard_normal(n_rows).cumsum() * 0.5
    close = np.maximum(close, 10.0)
    high = close + np.abs(rng.standard_normal(n_rows)) * 2.0
    low = close - np.abs(rng.standard_normal(n_rows)) * 2.0
    low = np.maximum(low, 1.0)
    open_price = low + rng.uniform(0, 1, n_rows) * (high - low)
    volume = rng.integers(100_000, 10_000_000, n_rows)
    return pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


class TestEquityFeatureEngineer:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.feature_engineering.technical.equity_engineer import (
            EquityFeatureEngineer,
        )
        self.EquityFeatureEngineer = EquityFeatureEngineer
        self.df = make_ohlcv_fixture(300)

    def test_engineer_is_instance_of_base(self):
        engineer = self.EquityFeatureEngineer()
        assert isinstance(engineer, BaseFeatureEngineer)

    def test_generate_features_returns_dataframe(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        assert isinstance(result, pd.DataFrame)

    def test_all_19_technical_columns_present(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        for col in technical_names():
            assert col in result.columns, f"Missing: {col}"

    def test_raw_ohlcv_columns_not_overwritten(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        for col in ["open", "high", "low", "close", "volume"]:
            pd.testing.assert_series_equal(
                result[col], self.df[col], check_names=False
            )

    def test_row_count_preserved(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        assert len(result) == len(self.df)

    def test_returns_1d_matches_manual(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        expected = self.df["close"].pct_change(1)
        pd.testing.assert_series_equal(
            result["returns_1d"].dropna(),
            expected.dropna(),
            check_names=False,
            rtol=1e-6,
        )

    def test_returns_5d_matches_manual(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        expected = self.df["close"].pct_change(5)
        pd.testing.assert_series_equal(
            result["returns_5d"].dropna(),
            expected.dropna(),
            check_names=False,
            rtol=1e-6,
        )

    def test_returns_10d_matches_manual(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        expected = self.df["close"].pct_change(10)
        pd.testing.assert_series_equal(
            result["returns_10d"].dropna(),
            expected.dropna(),
            check_names=False,
            rtol=1e-6,
        )

    def test_returns_20d_matches_manual(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        expected = self.df["close"].pct_change(20)
        pd.testing.assert_series_equal(
            result["returns_20d"].dropna(),
            expected.dropna(),
            check_names=False,
            rtol=1e-6,
        )

    def test_rsi_14_is_between_0_and_100(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        rsi = result["rsi_14"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_macd_triple_present(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        for col in ["macd", "macd_signal", "macd_hist"]:
            assert col in result.columns
            assert result[col].notna().any()

    def test_bb_bands_present_with_correct_width(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy()).dropna()
        computed_width = (result["bb_upper"] - result["bb_lower"]) / result["bb_middle"]
        pd.testing.assert_series_equal(
            computed_width, result["bb_width"], check_names=False, rtol=1e-6
        )

    def test_atr_14_positive(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        atr = result["atr_14"].dropna()
        assert (atr > 0).all()

    def test_volatility_20d_positive(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        vol = result["volatility_20d"].dropna()
        assert (vol > 0).all()

    def test_volume_z_score_mean_near_zero(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        z = result["volume_z_score"].dropna()
        assert abs(z.mean()) < 0.5

    def test_sma_50_present(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        assert result["sma_50"].notna().any()

    def test_sma_200_present(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        assert result["sma_200"].notna().any()

    def test_price_to_sma_ratios_present(self):
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        for col in ["price_to_sma50", "price_to_sma200"]:
            assert col in result.columns
            r = result[col].dropna()
            assert len(r) > 0

    def test_lookahead_no_forward_leakage(self):
        """Feature at time t must be identical when computed on
        history[:t] versus history[:t+10] — no future data leakage."""
        engineer = self.EquityFeatureEngineer()
        full_result = engineer.generate_features(self.df.copy())
        feature_cols = technical_names()
        t = 150
        partial_df = self.df.iloc[: t + 1].copy()
        partial_result = engineer.generate_features(partial_df)
        for col in feature_cols:
            if col in partial_result.columns:
                partial_val = partial_result[col].iloc[-1]
                full_val = full_result[col].iloc[t]
                if pd.isna(partial_val) and pd.isna(full_val):
                    continue
                assert partial_val == full_val or abs(partial_val - full_val) < 1e-10, (
                    f"Lookahead leakage in {col} at row {t}: "
                    f"partial={partial_val}, full={full_val}"
                )

    def test_no_features_returned_before_sufficient_data(self):
        """Early rows with insufficient history should be NaN for window-based features."""
        engineer = self.EquityFeatureEngineer()
        result = engineer.generate_features(self.df.copy())
        assert result["sma_200"].iloc[:199].isna().all()
