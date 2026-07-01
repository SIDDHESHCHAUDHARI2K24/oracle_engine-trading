import pandas as pd
import numpy as np
from scipy.stats import linregress
from app.features.backtesting.shared.base import BaseStrategy


class StatArb(BaseStrategy):
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        close = df['close']
        spy_close = df['spy_close']
        n = len(df)

        if n < 61:
            return pd.Series([False]*n, index=df.index), pd.Series([False]*n, index=df.index)

        residuals = pd.Series(np.nan, index=df.index)

        for i in range(60, n):
            asset_slice = close.iloc[i-60:i]
            spy_slice = spy_close.iloc[i-60:i]

            if spy_slice.isna().any() or asset_slice.isna().any():
                continue

            result = linregress(spy_slice, asset_slice)
            predicted = result.slope * spy_close.iloc[i] + result.intercept
            residuals.iloc[i] = close.iloc[i] - predicted

        rolling_mean = residuals.rolling(60).mean()
        rolling_std = residuals.rolling(60).std()
        z_score = (residuals - rolling_mean) / rolling_std

        entries = z_score < -2.0
        exits = z_score > -0.5

        return entries.fillna(False), exits.fillna(False)
