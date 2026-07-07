"""FRED macroeconomic data fetcher (Block A1).

Fetches 7 macro series from FRED via fredapi, renames to standardized
column names, and returns a single date-indexed DataFrame.

Per spec a1.4: forward-filling to the trading calendar happens in the
NumericalOrchestrator — this fetcher returns raw series as-is.
"""

import logging

import pandas as pd

from app.features.core.config import settings

from ..shared.exceptions import EmptyDataError, FetcherError
from ..shared.fetcher_base import DataFetcher, fetcher_retry

logger = logging.getLogger(__name__)

FRED_SERIES = {
    "DFF": "fed_funds_rate",
    "CPIAUCSL": "cpi",
    "UNRATE": "unemployment",
    "GDP": "gdp",
    "T10Y2Y": "yield_spread_10y_2y",
    "VIXCLS": "vix",
    "BAMLH0A0HYM2": "high_yield_spread",
}


class FREDFetcher(DataFetcher):
    """Macroeconomic data fetcher via FRED (uncontested — no failover).

    Fetches all 7 macro series and returns a single DataFrame with
    standardized column names. The Orchestrator handles forward-fill
    alignment to the NYSE trading calendar.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def fetch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        if not settings.fred_api_key:
            raise FetcherError(
                self.source_name,
                [],
                original_error=ValueError("FRED_API_KEY not configured"),
            )

        df = self._fetch_all(start_date, end_date)
        return {"__macro__": df}

    @fetcher_retry
    def _fetch_all(self, start_date: str, end_date: str) -> pd.DataFrame:
        from fredapi import Fred

        try:
            fred = Fred(api_key=settings.fred_api_key)
        except Exception as e:
            raise FetcherError(self.source_name, [], original_error=e) from e

        series_frames: dict[str, pd.Series] = {}
        latest_dates: dict[str, pd.Timestamp] = {}

        for fred_id, col_name in FRED_SERIES.items():
            try:
                raw = fred.get_series(
                    fred_id, observation_start=start_date, observation_end=end_date
                )
                if raw.empty:
                    logger.warning("FRED series %s returned no data", fred_id)
                    continue
                raw.name = col_name
                series_frames[col_name] = raw
                latest_dates[col_name] = (
                    raw.index[-1]
                    if isinstance(raw.index, pd.DatetimeIndex)
                    else pd.Timestamp(raw.index[-1])
                )
            except Exception as e:
                logger.warning("FRED series %s fetch failed: %s", fred_id, e)
                continue

        if not series_frames:
            raise EmptyDataError(self.source_name, list(FRED_SERIES.keys()))

        df = pd.DataFrame(series_frames)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        self._latest_dates = latest_dates
        return df

    def get_latest_dates(self) -> dict[str, pd.Timestamp]:
        """Return the most recent observation date per macro series.

        Used by the Orchestrator for stale_macro detection.
        """
        return getattr(self, "_latest_dates", {})
