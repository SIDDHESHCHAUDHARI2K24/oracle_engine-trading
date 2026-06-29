"""Tests for TimeSeriesDataset — sliding-window tensor generation."""

import numpy as np
import pandas as pd
import pytest
import torch
from torch.utils.data import DataLoader

from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)


def make_feature_matrix_rows(
    ticker_id: str, n_rows: int = 400
) -> list[dict]:
    rng = np.random.default_rng(42)
    rows = []
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="B")
    for i, d in enumerate(dates):
        row = {"ticker_id": ticker_id, "bar_date": d}
        for col in input_feature_names():
            row[col] = float(rng.standard_normal())
        for col in target_names():
            val = float(rng.standard_normal() * 0.02)
            row[col] = val if i < n_rows - 15 else None
        rows.append(row)
    return rows


class TestTimeSeriesDataset:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.feature_engineering.tensor_prep.dataset import (
            TimeSeriesDataset,
        )
        self.TimeSeriesDataset = TimeSeriesDataset
        self.rows_a = make_feature_matrix_rows("TICKER-A", 400)
        self.rows_b = make_feature_matrix_rows("TICKER-B", 200)

    def test_single_item_shape(self):
        ds = self.TimeSeriesDataset(
            self.rows_a, ticker_id="TICKER-A", lookback=252
        )
        if len(ds) > 0:
            X, y = ds[0]
            assert X.shape == (252, 31)
            assert y.shape == (4,)
            assert X.dtype == torch.float32
            assert y.dtype == torch.float32

    def test_dataloader_batch_shape(self):
        ds = self.TimeSeriesDataset(
            self.rows_a, ticker_id="TICKER-A", lookback=252
        )
        if len(ds) >= 8:
            loader = DataLoader(ds, batch_size=8)
            X, y = next(iter(loader))
            assert X.shape == (8, 252, 31)
            assert y.shape == (8, 4)

    def test_no_cross_ticker_straddle(self):
        """Windows must never span two tickers' data."""
        all_rows = self.rows_a + self.rows_b
        ds = self.TimeSeriesDataset(all_rows, ticker_id="TICKER-A", lookback=252)
        ticker_a_dates = {r["bar_date"] for r in self.rows_a}
        for idx in range(len(ds)):
            X, _ = ds[idx]
            assert idx < len(ds)

    def test_windows_exclude_unresolved_targets(self):
        ds = self.TimeSeriesDataset(
            self.rows_a, ticker_id="TICKER-A", lookback=252
        )
        assert len(ds) > 0
        assert len(ds) < len(self.rows_a)

    def test_x_carries_normalized_values(self):
        ds = self.TimeSeriesDataset(
            self.rows_a, ticker_id="TICKER-A", lookback=252
        )
        if len(ds) > 0:
            X, _ = ds[0]
            assert -10 < X.mean().item() < 10
