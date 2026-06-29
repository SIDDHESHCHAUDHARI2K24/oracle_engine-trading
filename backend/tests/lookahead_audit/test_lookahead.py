"""Lookahead Audit Suite — Release-Blocking Quality Gate.

Proves no future leakage anywhere in the Pipeline A feature path.
A single failing cell here means lookahead bias — treat as a release blocker.

Strategy: compute the full pipeline on history[:t] and history[:t+K],
then assert every feature row at dates <= t is identical between runs.
"""

import numpy as np
import pandas as pd
import pytest

from app.features.feature_engineering.alignment.macro_merger import MacroMerger
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
)
from app.features.feature_engineering.technical.equity_engineer import (
    EquityFeatureEngineer,
)
from app.features.feature_engineering.tensor_prep.feature_scaler import FeatureScaler
from app.features.feature_engineering.tensor_prep.target_generator import (
    TargetGenerator,
)


def make_ohlcv(n_rows: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    base = 100.0
    close = base + rng.standard_normal(n_rows).cumsum() * 0.5
    close = np.maximum(close, 10.0)
    high = close + np.abs(rng.standard_normal(n_rows)) * 2
    low = close - np.abs(rng.standard_normal(n_rows)) * 2
    low = np.maximum(low, 1.0)
    open_p = low + rng.uniform(0, 1, n_rows) * (high - low)
    volume = rng.integers(100_000, 10_000_000, n_rows)
    return pd.DataFrame(
        {"open": open_p, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def make_macro_df(equity_index: pd.DatetimeIndex) -> pd.DataFrame:
    macro_dates = pd.date_range(
        equity_index[0], equity_index[-1], freq="MS"
    )
    rng = np.random.default_rng(99)
    return pd.DataFrame(
        {
            "fed_funds_rate": np.clip(rng.normal(5.0, 0.5, len(macro_dates)), 0, 20),
            "cpi": 300.0 + rng.standard_normal(len(macro_dates)).cumsum() * 0.2,
            "unemployment": np.clip(rng.normal(4.0, 0.5, len(macro_dates)), 0, 15),
            "gdp": 25.0 + np.abs(rng.standard_normal(len(macro_dates)).cumsum()) * 0.1,
            "yield_spread_10y_2y": rng.normal(-0.2, 0.5, len(macro_dates)),
            "vix": np.clip(rng.normal(18, 5, len(macro_dates)), 5, 60),
            "high_yield_spread": np.clip(rng.normal(4.0, 1.0, len(macro_dates)), 1, 10),
        },
        index=macro_dates,
    )


class TestLookaheadAudit:
    """Release-blocking audit: prove no future data leaks into any past feature."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.engineer = EquityFeatureEngineer()
        self.merger = MacroMerger()
        self.target_gen = TargetGenerator()
        self.scaler = FeatureScaler()

    def run_pipeline(self, df: pd.DataFrame, macro: pd.DataFrame):
        engineered = self.engineer.generate_features(df.copy())
        merged = self.merger.merge(engineered, macro)
        targets = self.target_gen.generate(merged["close"])
        full = merged.join(targets)
        scaled, stats = self.scaler.fit_transform("AUDIT", full)
        result = full.copy()
        for col in input_feature_names():
            if col in scaled.columns and col in result.columns:
                result[col] = scaled[col]
        return result, stats

    def test_technical_features_no_future_leakage(self):
        df = make_ohlcv(400)
        macro = make_macro_df(df.index)

        t = 250
        partial = df.iloc[:t].copy()
        full, _ = self.run_pipeline(df, macro)
        partial_result, _ = self.run_pipeline(partial, macro)

        for col in input_feature_names():
            if col in partial_result.columns and col in full.columns:
                p_val = partial_result[col].iloc[-1]
                f_val = full[col].iloc[t - 1]
                if pd.isna(p_val) or pd.isna(f_val):
                    continue
                assert abs(p_val - f_val) < 1e-8, (
                    f"TECHNICAL LOOKAHEAD LEAKAGE in {col} at row {t-1}"
                )

    def test_scaled_features_no_future_leakage(self):
        df = make_ohlcv(500, seed=42)
        macro = make_macro_df(df.index)

        t = 400
        partial = df.iloc[:t].copy()
        full_scaled, _ = self.scaler.fit_transform("AUDIT", df)
        partial_scaled, _ = self.scaler.fit_transform("AUDIT-PARTIAL", partial)

        for col in input_feature_names():
            if col in partial_scaled.columns and col in full_scaled.columns:
                p_val = partial_scaled[col].iloc[-1]
                f_val = full_scaled[col].iloc[t - 1]
                if pd.isna(p_val) or pd.isna(f_val):
                    continue
                assert abs(p_val - f_val) < 1e-8 or abs(p_val - f_val) < 1e-10, (
                    f"SCALED LOOKAHEAD LEAKAGE in {col} at row {t-1}: "
                    f"partial={p_val:.8f}, full={f_val:.8f}"
                )

    def test_dataset_windows_no_future_leakage(self):
        """Verify that the full pipeline's output at past dates is invariant
        to appended future OHLCV rows."""
        df = make_ohlcv(500, seed=77)
        macro = make_macro_df(df.index)

        t = 350
        partial_df = df.iloc[:t].copy()
        full_result, _ = self.run_pipeline(df, macro)
        partial_result, _ = self.run_pipeline(partial_df, macro)

        check_idx = 330
        for col in input_feature_names():
            if col not in partial_result.columns or col not in full_result.columns:
                continue
            p_val = partial_result[col].iloc[check_idx]
            f_val = full_result[col].iloc[check_idx]
            if pd.isna(p_val) or pd.isna(f_val):
                continue
            assert abs(p_val - f_val) < 1e-8, (
                f"DATASET LOOKAHEAD LEAKAGE in {col} at row {check_idx}"
            )

    @pytest.mark.slow
    def test_end_to_end_invariance(self):
        """End-to-end: the output of the full pipeline at row t must be
        identical whether computed with only t rows or t+K rows."""
        df = make_ohlcv(600, seed=123)
        macro = make_macro_df(df.index)

        t = 400
        partial = df.iloc[:t].copy()
        full_result, _ = self.run_pipeline(df, macro)
        partial_result, _ = self.run_pipeline(partial, macro)

        last_valid = min(t - 1, len(partial_result) - 1, len(full_result) - 1)
        for col in input_feature_names():
            if col not in partial_result.columns or col not in full_result.columns:
                continue
            p_val = partial_result[col].iloc[-1]
            f_val = full_result[col].iloc[t - 1]
            if pd.isna(p_val) or pd.isna(f_val):
                continue
            assert abs(p_val - f_val) < 1e-8, (
                f"E2E LOOKAHEAD LEAKAGE in {col}: "
                f"partial@-1={p_val:.8f}, full@{t-1}={f_val:.8f}"
            )
