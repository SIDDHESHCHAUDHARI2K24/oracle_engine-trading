"""Tests for the TargetGenerator — continuous forward returns."""

import numpy as np
import pandas as pd
import pytest

from app.features.feature_engineering.shared.feature_schema import target_names


def make_close_series(n: int = 100) -> pd.Series:
    rng = np.random.default_rng(42)
    base = 100.0
    closes = base + rng.standard_normal(n).cumsum() * 0.5
    closes = np.maximum(closes, 10.0)
    return pd.Series(closes, name="close")


class TestTargetGenerator:
    @pytest.fixture(autouse=True)
    def _setup(self) -> None:
        from app.features.feature_engineering.tensor_prep.target_generator import (
            TargetGenerator,
        )

        self.TargetGenerator = TargetGenerator
        self.close = make_close_series(100)

    def test_generates_4_target_columns(self):
        gen = self.TargetGenerator()
        result = gen.generate(self.close)
        for col in target_names():
            assert col in result.columns

    def test_forward_direction_correct(self):
        gen = self.TargetGenerator()
        close = self.close.values
        result = gen.generate(self.close)
        t = 10
        manual_t5 = (close[t + 5] - close[t]) / close[t]
        assert result["target_t5"].iloc[t] == pytest.approx(manual_t5, rel=1e-6)

    def test_denominator_is_current_close(self):
        gen = self.TargetGenerator()
        close = self.close.values
        result = gen.generate(self.close)
        t = 20
        manual_t10 = (close[t + 10] - close[t]) / close[t]
        assert result["target_t10"].iloc[t] == pytest.approx(manual_t10, rel=1e-6)

    def test_last_15_rows_have_null_target_t15(self):
        gen = self.TargetGenerator()
        result = gen.generate(self.close)
        assert result["target_t15"].iloc[-15:].isna().all()

    def test_last_5_rows_have_null_target_t5(self):
        gen = self.TargetGenerator()
        result = gen.generate(self.close)
        assert result["target_t5"].iloc[-5:].isna().all()

    def test_preserves_input_index(self):
        gen = self.TargetGenerator()
        result = gen.generate(self.close)
        assert result.index.equals(self.close.index)

    def test_input_unchanged(self):
        gen = self.TargetGenerator()
        original = self.close.copy()
        _ = gen.generate(self.close)
        assert (self.close == original).all()
