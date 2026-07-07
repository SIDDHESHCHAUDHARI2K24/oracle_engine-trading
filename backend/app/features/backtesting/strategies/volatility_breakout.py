import pandas as pd
from app.features.backtesting.shared.base import BaseStrategy


class VolatilityBreakout(BaseStrategy):
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        atr = df["atr_14"]
        close = df["close"]

        atr_ma14 = atr.rolling(14).mean()
        rolling_high20 = close.rolling(20).max().shift(1)

        entries = (atr > 1.25 * atr_ma14) & (close > rolling_high20)
        exits = close < 0.95 * close.rolling(20).max()

        return entries, exits
