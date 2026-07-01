import pandas as pd
from app.features.backtesting.shared.base import BaseStrategy


class MeanReversion(BaseStrategy):
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        entries = df['close'] < df['bb_lower']
        exits = df['close'] > df['bb_middle']
        return entries, exits
