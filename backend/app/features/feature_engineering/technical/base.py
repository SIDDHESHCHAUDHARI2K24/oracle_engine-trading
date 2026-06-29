"""Abstract base class for feature engineers.

Every asset-class-specific engineer inherits from this ABC and
implements `generate_features` with an append-don't-overwrite contract.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseFeatureEngineer(ABC):
    """Compute technical features for a single ticker's OHLCV history.

    Subclasses receive a DataFrame with at least open/high/low/close/volume
    columns and **append** derived feature columns without modifying or
    overwriting the original raw OHLCV data.
    """

    def __init__(self, **kwargs) -> None:
        self._config = kwargs

    @abstractmethod
    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Append feature columns to the input DataFrame.

        Args:
            df: OHLCV DataFrame indexed by date with columns
                open, high, low, close, volume.

        Returns:
            Same DataFrame with feature columns appended.
            Original columns must remain unmodified.
        """
        ...
