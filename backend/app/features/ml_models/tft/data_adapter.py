from __future__ import annotations

from typing import Any

import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet
from pytorch_forecasting.data.encoders import NaNLabelEncoder

from app.features.feature_engineering.shared.feature_schema import (
    macro_names,
    raw_names,
    technical_names,
)

_macro_names: list[str] = macro_names()
_raw_names: list[str] = raw_names()
_technical_names: list[str] = technical_names()


def build_tft_dataset(
    df: pd.DataFrame,
    target_column: str,
    ticker_col: str = "ticker_id",
    date_col: str = "bar_date",
    max_encoder_length: int = 252,
    max_prediction_length: int = 1,
    **kwargs: Any,
) -> TimeSeriesDataSet:
    """Map feature_matrix rows to pytorch-forecasting TimeSeriesDataSet.

    Creates contiguous time_idx per ticker group (sequential integers
    mapping sorted dates within each group).  Handles tickers with fewer
    rows than ``max_encoder_length`` gracefully — pytorch-forecasting
    automatically pads short sequences.

    Covariate typing:
      - time_varying_known_reals:   macro features (7)
      - time_varying_unknown_reals: raw (5) + technical (19) features
      - static_categoricals:        ticker_col
      - target:                     target_column
    """

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    if ticker_col not in df.columns:
        raise KeyError(
            f"ticker_col='{ticker_col}' not found in DataFrame columns: {list(df.columns)}"
        )

    if target_column not in df.columns:
        raise KeyError(
            f"target_column='{target_column}' not found in DataFrame columns: {list(df.columns)}"
        )

    df = df.sort_values([ticker_col, date_col]).reset_index(drop=True)

    df["time_idx"] = (
        df.groupby(ticker_col, sort=False)[date_col].rank(method="dense").astype(int)
        - 1
    )

    time_varying_known = [c for c in _macro_names if c in df.columns]
    time_varying_unknown = [c for c in _raw_names + _technical_names if c in df.columns]

    min_encoder = min(
        max_encoder_length,
        int(df.groupby(ticker_col)["time_idx"].count().min() or max_encoder_length),
    )
    effective_encoder = max(1, min_encoder)

    ds = TimeSeriesDataSet(
        df,
        time_idx="time_idx",
        target=target_column,
        group_ids=[ticker_col],
        max_encoder_length=effective_encoder,
        max_prediction_length=max_prediction_length,
        min_encoder_length=1,
        time_varying_known_reals=time_varying_known,
        time_varying_unknown_reals=time_varying_unknown,
        static_categoricals=[ticker_col],
        categorical_encoders={ticker_col: NaNLabelEncoder()},
        allow_missing_timesteps=True,
        **kwargs,
    )

    return ds
