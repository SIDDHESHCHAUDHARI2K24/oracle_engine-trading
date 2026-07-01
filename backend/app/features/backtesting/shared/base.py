from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Return (entries: pd.Series[bool], exits: pd.Series[bool])."""
        ...
