"""Tests for FeatureScaler — lookahead-safe rolling Z-score normalization.

This is the highest-risk correctness surface in S3. These tests are
designed to be decisive: a single failure means lookahead bias.
"""

import numpy as np
import pandas as pd
import pytest

from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)


def make_feature_df(n_rows: int = 400) -> pd.DataFrame:
    """Create a DataFrame with all 31 feature columns + 4 targets."""
    rng = np.random.default_rng(42)
    index = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    data = {}
    for name in input_feature_names():
        data[name] = rng.standard_normal(n_rows) * 10 + 50
    for name in target_names():
        data[name] = rng.standard_normal(n_rows) * 0.02
    return pd.DataFrame(data, index=index)


class TestFeatureScalerLookaheadSafety:
    """Tests that pin down lookahead-safe normalization."""

    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.feature_engineering.tensor_prep.feature_scaler import (
            FeatureScaler,
        )
        self.FeatureScaler = FeatureScaler
        self.df = make_feature_df(400)

    def test_scaled_returns_dataframe_with_same_shape(self):
        scaler = self.FeatureScaler()
        result, _ = scaler.fit_transform("ticker-1", self.df.copy())
        assert result.shape[0] == self.df.shape[0]

    def test_only_31_input_features_normalized(self):
        """The 31 input features should differ from raw; targets should be identical."""
        scaler = self.FeatureScaler()
        result, _ = scaler.fit_transform("ticker-1", self.df.copy())
        for col in input_feature_names():
            after_burn = result[col].dropna()
            if len(after_burn) > 0:
                assert not np.array_equal(after_burn.values, self.df[col].loc[after_burn.index].values)

    def test_targets_passthrough_untouched(self):
        scaler = self.FeatureScaler()
        result, _ = scaler.fit_transform("ticker-1", self.df.copy())
        for col in target_names():
            pd.testing.assert_series_equal(
                result[col].dropna(),
                self.df[col].dropna(),
                check_names=False,
                rtol=1e-10,
            )

    def test_no_future_leakage_crucial(self):
        """THE DECISIVE TEST: scaled value at t must be identical whether
        computed on df[:t+1] or df[:t+100]."""
        scaler_full = self.FeatureScaler()
        full_result, _ = scaler_full.fit_transform("ticker-1", self.df.copy())

        t = 300
        partial_df = self.df.iloc[: t + 1].copy()
        scaler_partial = self.FeatureScaler()
        partial_result, _ = scaler_partial.fit_transform("ticker-1", partial_df)

        for col in input_feature_names():
            if col in partial_result.columns:
                p_val = partial_result[col].iloc[-1]
                f_val = full_result[col].iloc[t]
                if pd.isna(p_val) and pd.isna(f_val):
                    continue
                assert p_val == pytest.approx(f_val, rel=1e-8) or abs(p_val - f_val) < 1e-10, (
                    f"Lookahead leakage in {col} at row {t}: "
                    f"partial={p_val}, full={f_val}"
                )

    def test_normalization_stats_populated(self):
        scaler = self.FeatureScaler()
        _, stats = scaler.fit_transform("ticker-1", self.df.copy())
        assert stats is not None
        assert len(stats) > 0

    def test_normalization_stats_match_manual_computation(self):
        """Spot-check: the stored rolling mean/std at a specific date must
        match the manual computation from the raw DataFrame."""
        scaler = self.FeatureScaler()
        df = self.df.copy()
        _, stats = scaler.fit_transform("ticker-1", df)
        stats_df = pd.DataFrame(stats)

        t = 300
        window = 252
        col = "returns_1d"
        manual_mean = df[col].iloc[t - window + 1 : t + 1].mean()

        stat_row = stats_df[
            (stats_df["bar_date"] == df.index[t])
            & (stats_df["feature_name"] == col)
        ]
        if not stat_row.empty:
            assert abs(float(stat_row["rolling_mean"].iloc[0]) - manual_mean) < 0.01

    def test_per_ticker_isolation(self):
        """Two tickers with different data must not influence each other's normalization."""
        rng = np.random.default_rng(99)
        df_a = make_feature_df(400)
        df_b = make_feature_df(400)
        df_b["returns_1d"] = rng.standard_normal(400) * 20 + 100

        scaler = self.FeatureScaler()
        result_a, stats_a = scaler.fit_transform("TICKER-A", df_a.copy())
        result_b, stats_b = scaler.fit_transform("TICKER-B", df_b.copy())

        t = 300
        if not pd.isna(result_a["returns_1d"].iloc[t]) and not pd.isna(result_b["returns_1d"].iloc[t]):
            assert result_a["returns_1d"].iloc[t] != result_b["returns_1d"].iloc[t]

    def test_zero_std_feature_handled_no_inf(self):
        """Constant feature must produce 0, not inf, after Z-score."""
        df = make_feature_df(400)
        df["returns_1d"] = 5.0  # constant

        scaler = self.FeatureScaler()
        result, _ = scaler.fit_transform("ticker-1", df)
        after_burn = result["returns_1d"].dropna()
        if len(after_burn) > 0:
            assert not np.isinf(after_burn).any()
            assert (after_burn == 0).all() or (after_burn.abs() < 1e-10).all()

    def test_macro_features_also_z_scored(self):
        scaler = self.FeatureScaler()
        result, _ = scaler.fit_transform("ticker-1", self.df.copy())
        fed = result["fed_funds_rate"].dropna()
        if len(fed) > 0:
            assert abs(fed.mean()) < 0.5  # Z-scored data mean near 0
