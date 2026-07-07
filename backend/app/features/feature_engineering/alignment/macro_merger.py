"""MacroMerger — left-join macro series onto equity trading-day index.

Per spec a2.5: forward-filled macro values are left-joined onto each
ticker's feature DataFrame using the equity (trading-day) index, so the
feature matrix strictly follows the market calendar.
"""

import pandas as pd

from app.features.feature_engineering.shared.feature_schema import macro_names


class MacroMerger:
    """Left-join forward-filled macro data onto equity feature frames.

    Input:
        equity_df: OHLCV/technical DataFrame indexed by trading dates.
        macro_df: Macro DataFrame indexed by observation dates with one
                  column per macro series.

    The left join guarantees:
        - Equity row count is preserved.
        - No weekend/holiday macro rows leak in.
        - Macro values are forward-filled so every trading day has a value
          (except leading burn-in, handled downstream).
    """

    def merge(self, equity_df: pd.DataFrame, macro_df: pd.DataFrame) -> pd.DataFrame:
        macro_cols = [c for c in macro_names() if c in macro_df.columns]
        if not macro_cols:
            return equity_df.copy()

        macro_to_merge = macro_df[macro_cols].copy()
        macro_to_merge = macro_to_merge.ffill()
        macro_to_merge = macro_to_merge.reindex(index=equity_df.index, method="ffill")

        result = equity_df.copy()
        for col in macro_cols:
            result[col] = macro_to_merge[col]

        return result
