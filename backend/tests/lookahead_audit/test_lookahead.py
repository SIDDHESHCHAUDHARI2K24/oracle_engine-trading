"""Lookahead Audit Suite — Release-Blocking Quality Gate.

Proves no future leakage anywhere in the Pipeline A feature path.
A single failing cell here means lookahead bias — treat as a release blocker.

Strategy: compute the full pipeline on history[:t] and history[:t+K],
then assert EVERY feature row at dates <= t is bit-identical between runs.
This catches leaks at any intermediate timestamp, not just the splice point.
"""

import numpy as np
import pandas as pd
import pytest

from app.features.feature_engineering.alignment.macro_merger import MacroMerger
from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    macro_names,
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
    macro_dates = pd.date_range(equity_index[0], equity_index[-1], freq="MS")
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


def _assert_all_past_rows_invariant(
    partial_result: pd.DataFrame,
    full_result: pd.DataFrame,
    slice_at: int,
    context: str,
    burn_in: int = 252,
) -> None:
    """Assert every non-NaN past row from burn_in..slice_at-1 is identical."""
    feature_cols = [
        c
        for c in input_feature_names()
        if c in partial_result.columns and c in full_result.columns
    ]
    check_start = max(burn_in, 0)
    check_end = min(slice_at, len(partial_result), len(full_result))
    if check_end <= check_start:
        return

    failing: list[str] = []
    for col in feature_cols:
        for idx in range(check_start, check_end):
            p_val = partial_result[col].iloc[idx]
            f_val = full_result[col].iloc[idx]
            if pd.isna(p_val) and pd.isna(f_val):
                continue
            if pd.isna(p_val) or pd.isna(f_val):
                failing.append(
                    f"{context}: {col} row {idx} NaN mismatch "
                    f"partial={p_val}, full={f_val}"
                )
                continue
            if abs(float(p_val) - float(f_val)) >= 1e-8:
                failing.append(
                    f"{context}: {col} row {idx} diverges "
                    f"partial={p_val:.10f}, full={f_val:.10f}"
                )

    if failing:
        raise AssertionError(
            f"LOOKAHEAD LEAKAGE in {context} — {len(failing)} rows affected:\n"
            + "\n".join(failing[:10])
            + ("\n..." if len(failing) > 10 else "")
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

    def test_full_pipeline_all_rows_no_future_leakage(self):
        """ALL past rows must be invariant — not just the splice point."""
        df = make_ohlcv(500, seed=42)
        macro = make_macro_df(df.index)

        t = 380
        partial = df.iloc[:t].copy()
        full_result, _ = self.run_pipeline(df, macro)
        partial_result, _ = self.run_pipeline(partial, macro)

        _assert_all_past_rows_invariant(
            partial_result, full_result, t, "full_pipeline"
        )

    def test_scaler_only_all_rows_no_future_leakage(self):
        """All rows in scaler output must be invariant."""
        df = make_ohlcv(600, seed=77)
        macro = make_macro_df(df.index)

        t = 450
        partial = df.iloc[:t].copy()

        full_scaled, _ = self.scaler.fit_transform("AUDIT", df)
        partial_scaled, _ = self.scaler.fit_transform("AUDIT-PARTIAL", partial)

        _assert_all_past_rows_invariant(
            partial_scaled, full_scaled, t, "scaler_only"
        )

    def test_engineer_only_all_rows_no_future_leakage(self):
        """All technical indicator rows must be invariant."""
        df = make_ohlcv(400, seed=123)
        engineer = EquityFeatureEngineer()

        t = 300
        partial = df.iloc[:t].copy()
        full_eng = engineer.generate_features(df.copy())
        partial_eng = engineer.generate_features(partial)

        feature_cols = [
            c
            for c in input_feature_names()
            if c in partial_eng.columns and c in full_eng.columns
        ]
        burn_in = 200
        check_end = min(t, len(partial_eng), len(full_eng))
        for row_i in range(burn_in, check_end):
            for col in feature_cols:
                p_val = partial_eng[col].iloc[row_i]
                f_val = full_eng[col].iloc[row_i]
                if pd.isna(p_val) and pd.isna(f_val):
                    continue
                if pd.isna(p_val) or pd.isna(f_val):
                    raise AssertionError(
                        f"ENGINEER LOOKAHEAD: {col} row {row_i} NaN mismatch"
                    )
                assert abs(float(p_val) - float(f_val)) < 1e-8, (
                    f"ENGINEER LOOKAHEAD: {col} row {row_i} diverges "
                    f"partial={p_val:.10f}, full={f_val:.10f}"
                )

    @pytest.mark.slow
    def test_end_to_end_all_rows_invariance(self):
        """E2E: Every past row must be identical with or without future data."""
        df = make_ohlcv(700, seed=999)
        macro = make_macro_df(df.index)

        t = 500
        partial = df.iloc[:t].copy()
        full_result, _ = self.run_pipeline(df, macro)
        partial_result, _ = self.run_pipeline(partial, macro)

        _assert_all_past_rows_invariant(
            partial_result, full_result, t, "e2e"
        )


class TestMacroMergerLookahead:
    """Standalone test: MacroMerger must not forward-peek future macro values."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        self.merger = MacroMerger()

    def test_macro_merger_no_forward_peek(self):
        """Macro value at date t must be identical with or without future data."""
        dates = pd.date_range("2024-01-01", periods=200, freq="B")
        equity = pd.DataFrame(
            {"close": 100.0, "volume": 1_000_000},
            index=dates,
        )

        rng = np.random.default_rng(55)
        full_macro_dates = pd.date_range("2023-06-01", "2025-06-30", freq="MS")
        full_macro = pd.DataFrame(
            {
                col: rng.standard_normal(len(full_macro_dates))
                for col in macro_names()
            },
            index=full_macro_dates,
        )

        t = 120
        cutoff_date = dates[t - 1]
        partial_macro_count = len(
            full_macro[full_macro.index <= cutoff_date]
        )
        partial_macro = full_macro.iloc[: partial_macro_count + 1].copy()

        full_merged = self.merger.merge(equity.copy(), full_macro.copy())
        partial_merged = self.merger.merge(
            equity.iloc[:t].copy(), partial_macro.copy()
        )

        for col in macro_names():
            if col not in partial_merged.columns or col not in full_merged.columns:
                continue
            p_val = partial_merged[col].iloc[-5]
            f_val = full_merged[col].iloc[t - 5]
            if pd.isna(p_val) and pd.isna(f_val):
                continue
            assert float(p_val) == pytest.approx(float(f_val), rel=1e-8), (
                f"MACRO MERGER LOOKAHEAD in {col}: "
                f"partial={p_val}, full={f_val}"
            )
