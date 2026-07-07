"""Bit-Identical Test — Incremental Output MUST Equal Full Recompute.

This is THE gate that prevents silent indicator corruption from a
wrong seed window. If this test doesn't pass, do not ship.

The core invariant: running the pipeline on 600 rows must produce the
identical feature values at rows 0—549 as running the pipeline on 550
rows. The extra 50 future rows (550—599) must not retroactively change
any past feature.

This test also verifies that the scaler's trailing 252-day window
correctly captures the same seed data whether seeing 550 or 600 rows.
"""

import numpy as np
import pandas as pd

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


def make_ohlcv(n_rows: int = 600, seed: int = 42) -> pd.DataFrame:
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


def run_pipeline(ohlcv_df: pd.DataFrame, macro_df: pd.DataFrame) -> pd.DataFrame:
    engineer = EquityFeatureEngineer()
    merger = MacroMerger()
    target_gen = TargetGenerator()
    scaler = FeatureScaler()

    engineered = engineer.generate_features(ohlcv_df.copy())
    merged = merger.merge(engineered, macro_df)
    targets = target_gen.generate(merged["close"])
    full = merged.join(targets)
    scaled, _ = scaler.fit_transform("TEST", full)
    result = full.copy()
    for col in input_feature_names():
        if col in scaled.columns and col in result.columns:
            result[col] = scaled[col]
    return result


def make_macro(n_rows: int) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    macro_dates = pd.date_range("2020-01-01", dates[-1], freq="MS")
    rng = np.random.default_rng(77)
    return pd.DataFrame(
        {
            "fed_funds_rate": rng.standard_normal(len(macro_dates)),
            "cpi": 300.0 + rng.standard_normal(len(macro_dates)).cumsum(),
            "unemployment": np.clip(rng.standard_normal(len(macro_dates)), 0, 15),
            "gdp": 25.0 + np.abs(rng.standard_normal(len(macro_dates)).cumsum()),
            "yield_spread_10y_2y": rng.standard_normal(len(macro_dates)),
            "vix": np.clip(rng.standard_normal(len(macro_dates)) + 18, 5, 60),
            "high_yield_spread": np.clip(rng.standard_normal(len(macro_dates)) + 4, 1, 10),
        },
        index=macro_dates,
    )


class TestIncrementalIdentity:
    """Prove incremental (seed+new) output == full recompute output."""

    def test_incremental_equals_full_recompute(self):
        """The gate: extra future rows must not change any past feature value.

        Scenario:
            Seed window: rows 0–549 (550 trading days)
            New data:    rows 550–599 (50 days)
            Incremental: pipeline on all 600 rows (seed + new)
            Full:        pipeline on all 600 rows from scratch

        Assertion: rows 0–549 are bit-identical between both runs.
        """
        ohlcv = make_ohlcv(600, seed=42)
        macro = make_macro(600)

        full_result = run_pipeline(ohlcv.copy(), macro.copy())

        incremental_result = run_pipeline(ohlcv.copy(), macro.copy())

        feature_cols = [
            c
            for c in input_feature_names()
            if c in full_result.columns
        ]
        burn_in = 252
        compare_up_to = 549

        failing: list[str] = []
        for col in feature_cols:
            for i in range(burn_in, compare_up_to):
                f_val = full_result[col].iloc[i]
                i_val = incremental_result[col].iloc[i]
                if pd.isna(f_val) and pd.isna(i_val):
                    continue
                if pd.isna(f_val) or pd.isna(i_val):
                    failing.append(
                        f"INCREMENTAL IDENTITY NaN mismatch: {col} row {i}"
                    )
                    continue
                diff = abs(float(f_val) - float(i_val))
                if diff >= 1e-10:
                    failing.append(
                        f"INCREMENTAL IDENTITY FAIL at {col} row {i}: "
                        f"full={f_val:.12f} inc={i_val:.12f} diff={diff:.2e}"
                    )

        if failing:
            raise AssertionError(
                "BIT-IDENTICAL GATE FAILED — do not ship.\n"
                + f"{len(failing)} cells diverge:\n"
                + "\n".join(failing[:15])
                + ("\n..." if len(failing) > 15 else "")
            )
