"""FeatureScaler — rolling 252-day Z-score normalization per feature per ticker.

Applies z_t = (x_t - mean(x_{t-252:t})) / std(x_{t-252:t}) to each of
the 31 input features using a strict trailing rolling window. Targets
are NEVER touched.  Per-ticker isolation is preserved structurally —
each call is for one ticker only.

Zero-standard-deviation features (e.g., constant or halted) produce 0
instead of inf/NaN.
"""

import numpy as np
import pandas as pd

from app.features.feature_engineering.shared.feature_schema import (
    input_feature_names,
)

WINDOW = 252
MIN_PERIODS = 252


class FeatureScaler:
    """Rolling Z-score normalizer for one ticker at a time.

    Usage:
        scaler = FeatureScaler()
        scaled_df, stats = scaler.fit_transform(ticker_id, df)

        scaled_df: Same shape as df, with 31 input columns normalized
        stats: list[dict] with keys (ticker_id, bar_date, feature_name,
               rolling_mean, rolling_std) for persistence.
    """

    def fit_transform(
        self, ticker_id: str, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[dict]]:
        """Apply rolling Z-score and collect normalization stats.

        Args:
            ticker_id: Identifier string for the ticker (for stats).
            df: DataFrame with all 31 input features + 4 targets,
                indexed by date.

        Returns:
            Tuple of (scaled_df, stats) where scaled_df has Z-scored
            features and untouched targets, and stats is a list of
            per-(date, feature) normalization parameters.
        """
        result = df.copy()
        stats: list[dict] = []

        feature_cols = [c for c in input_feature_names() if c in df.columns]

        for col in feature_cols:
            series = df[col].astype(float)
            rolling_mean = series.rolling(window=WINDOW, min_periods=MIN_PERIODS).mean()
            rolling_std = series.rolling(window=WINDOW, min_periods=MIN_PERIODS).std()

            z = np.full_like(series.values, np.nan, dtype=np.float64)
            valid = rolling_std.notna() & (rolling_std > 0)
            z[valid.values] = (
                series[valid].values - rolling_mean[valid].values
            ) / rolling_std[valid].values
            zero_std = rolling_std.notna() & (rolling_std <= 0)
            z[zero_std.values] = 0.0

            result[col] = z

            for idx in valid[valid].index:
                stats.append(
                    {
                        "ticker_id": ticker_id,
                        "bar_date": idx,
                        "feature_name": col,
                        "rolling_mean": float(rolling_mean.loc[idx]),
                        "rolling_std": float(rolling_std.loc[idx]),
                    }
                )

        return result, stats
