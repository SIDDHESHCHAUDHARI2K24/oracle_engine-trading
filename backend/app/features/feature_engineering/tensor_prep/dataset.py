"""TimeSeriesDataset — PyTorch Dataset yielding [252, 31] / [4] tensors.

Per spec a3.3: reads normalized feature_matrix rows, produces sliding
252-day lookback windows of normalized features with 4-horizon targets.
"""

import pandas as pd
import torch
from torch.utils.data import Dataset

from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
    target_names,
)

LOOKBACK = 252
N_FEATURES = 31
N_TARGETS = 4


class TimeSeriesDataset(Dataset):
    """Sliding-window tensor generator for ML model training/inference.

    Args:
        rows: List of dicts from feature_matrix, sorted by bar_date.
        ticker_id: Optional filter — only include windows for this ticker.
        lookback: Sliding window size in trading days (default 252).

    Each call to __getitem__ returns:
        X: torch.Tensor of shape [lookback, 31] — normalized features
        y: torch.Tensor of shape [4] — continuous return targets
    """

    def __init__(
        self,
        rows: list[dict],
        ticker_id: str | None = None,
        lookback: int = LOOKBACK,
    ):
        self.lookback = lookback
        self.feature_cols = [c for c in input_feature_names()]
        self.target_cols = [c for c in target_names()]

        df = pd.DataFrame(rows)
        df = df.sort_values("bar_date").reset_index(drop=True)

        if ticker_id is not None:
            ticker_mask = df["ticker_id"].astype(str) == str(ticker_id)
            df = df[ticker_mask].reset_index(drop=True)

        self._build_windows(df)

    def _build_windows(self, df: pd.DataFrame) -> None:
        """Build valid-window index. Windows must never straddle tickers."""
        self.windows: list[dict] = []

        feature_cols_present = [c for c in self.feature_cols if c in df.columns]
        target_cols_present = [c for c in self.target_cols if c in df.columns]

        if not feature_cols_present:
            return

        feature_array = df[feature_cols_present].to_numpy(dtype="float32")
        target_array = (
            df[target_cols_present].to_numpy(dtype="float32")
            if target_cols_present
            else None
        )

        for i in range(self.lookback - 1, len(df)):
            start = i - self.lookback + 1
            end = i + 1

            if target_array is not None:
                targets = target_array[i]
                if pd.isna(targets).any():
                    continue

            self.windows.append(
                {
                    "features": torch.tensor(
                        feature_array[start:end], dtype=torch.float32
                    ),
                    "targets": (
                        torch.tensor(target_array[i], dtype=torch.float32)
                        if target_array is not None
                        else torch.zeros(N_TARGETS, dtype=torch.float32)
                    ),
                }
            )

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        w = self.windows[idx]
        return w["features"], w["targets"]
