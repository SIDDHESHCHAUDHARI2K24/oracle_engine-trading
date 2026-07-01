import pandas as pd
from app.features.backtesting.shared.base import BaseStrategy


class MomentumCross(BaseStrategy):
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        sma_50 = df['sma_50']
        sma_200 = df['sma_200']
        entries = (sma_50 > sma_200) & (sma_50.shift(1) <= sma_200.shift(1))
        exits = (sma_50 < sma_200) & (sma_50.shift(1) >= sma_200.shift(1))
        return entries, exits
