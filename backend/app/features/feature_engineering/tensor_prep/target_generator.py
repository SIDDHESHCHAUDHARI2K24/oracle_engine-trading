"""TargetGenerator — continuous forward returns for 4 horizons.

Per spec a3.2: computes targets using the exact subtraction formula
(close.shift(-H) - close) / close, NOT pct_change which can produce
inverse-denominator errors.

Targets are stored as nullable — trailing unresolved rows get NaN.
"""

import pandas as pd

from app.features.feature_engineering.shared.feature_schema import TARGETS


class TargetGenerator:
    """Generate 4-horizon continuous forward-return targets.

    Usage:
        gen = TargetGenerator()
        df_with_targets = gen.generate(df["close"])
    """

    def generate(self, close: pd.Series) -> pd.DataFrame:
        """Compute T+1, T+5, T+10, T+15 continuous returns.

        Args:
            close: Close price series indexed by date.

        Returns:
            DataFrame with columns target_t1..target_t15, same index.
        """
        result = pd.DataFrame(index=close.index)

        for target in TARGETS:
            horizon = target.horizon
            shifted = close.shift(-horizon)
            result[target.name] = (shifted - close) / close

        return result
