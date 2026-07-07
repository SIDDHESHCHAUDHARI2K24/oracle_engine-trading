"""Tests for the MacroMerger — left-join alignment of macro data."""

import pandas as pd
import pytest

from app.features.feature_engineering.shared.feature_schema import macro_names


def make_equity_df(n_days: int = 252) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {
            "close": 100.0 + pd.Series(range(n_days), dtype=float),
            "volume": 1_000_000,
        },
        index=dates,
    )


def make_macro_df() -> pd.DataFrame:
    """Monthly macro data: sparse dates, forward-fill carries values."""
    dates = pd.to_datetime(
        [
            "2024-01-02",
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
            "2024-05-01",
            "2024-06-03",
            "2024-07-01",
        ]
    )
    return pd.DataFrame(
        {
            "fed_funds_rate": [5.33, 5.33, 5.33, 5.33, 5.33, 5.33, 5.50],
            "cpi": [308.0, 309.0, 310.0, 311.0, 312.0, 313.0, 314.0],
            "unemployment": [3.7, 3.9, 3.8, 3.9, 4.0, 4.1, 4.3],
            "gdp": [28.2, 28.2, 28.2, 28.5, 28.5, 28.5, 29.0],
            "yield_spread_10y_2y": [-0.35, -0.30, -0.25, -0.20, -0.15, -0.10, -0.05],
            "vix": [13.0, 14.0, 15.0, 18.0, 16.0, 14.0, 12.0],
            "high_yield_spread": [3.5, 3.6, 3.7, 3.8, 3.9, 4.0, 3.8],
        },
        index=dates,
    )


class TestMacroMerger:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.feature_engineering.alignment.macro_merger import (
            MacroMerger,
        )

        self.MacroMerger = MacroMerger
        self.equity = make_equity_df(252)
        self.macro = make_macro_df()

    def test_preserves_equity_row_count(self):
        merger = self.MacroMerger()
        result = merger.merge(self.equity.copy(), self.macro.copy())
        assert len(result) == len(self.equity)

    def test_all_7_macro_columns_attached(self):
        merger = self.MacroMerger()
        result = merger.merge(self.equity.copy(), self.macro.copy())
        for col in macro_names():
            assert col in result.columns

    def test_no_non_trading_days_introduced(self):
        merger = self.MacroMerger()
        result = merger.merge(self.equity.copy(), self.macro.copy())
        assert result.index.equals(self.equity.index)

    def test_original_equity_columns_preserved(self):
        merger = self.MacroMerger()
        result = merger.merge(self.equity.copy(), self.macro.copy())
        for col in self.equity.columns:
            assert col in result.columns

    def test_forward_fill_propagates_macro_values(self):
        """After forward-fill, CPI should be constant between monthly releases."""
        merger = self.MacroMerger()
        result = merger.merge(self.equity.copy(), self.macro.copy())
        feb_values = result.loc["2024-02-01":"2024-02-28", "cpi"]
        assert feb_values.nunique() == 1

    def test_leading_macro_nan_handled(self):
        """When macro starts later than equity, leading rows get NaN macro."""
        late_macro = self.macro.copy()
        late_macro.index = late_macro.index + pd.DateOffset(days=90)
        early_equity = make_equity_df(60)
        merger = self.MacroMerger()
        result = merger.merge(early_equity.copy(), late_macro.copy())
        assert result["cpi"].iloc[0] is pd.NA or pd.isna(result["cpi"].iloc[0])
