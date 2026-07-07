"""Stooq OHLCV fetcher — last-resort CSV source (Block A1).

Downloads daily OHLCV from Stooq's public CSV endpoint.
Returns identical schema to YahooFinanceFetcher for transparent failover.
"""

import logging

import pandas as pd

from ..shared.exceptions import EmptyDataError
from ..shared.fetcher_base import (
    DataFetcher,
    enforce_ohlcv_schema,
    fetcher_retry,
    strip_tz,
)

logger = logging.getLogger(__name__)

STOOQ_BASE_URL = "https://stooq.com/q/d/l/"


class StooqFetcher(DataFetcher):
    """Last-resort OHLCV source via Stooq CSV download.

    Fetches one symbol per request. Normalizes Stooq's column names
    to the standard OHLCV schema for transparent failover.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def fetch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}

        validated = [s.strip().upper() for s in symbols]
        return self._fetch_all(validated, start_date, end_date)

    @fetcher_retry
    def _fetch_all(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        import httpx

        results: dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            try:
                url = (
                    f"{STOOQ_BASE_URL}?s={symbol}.us&i=d&d1={start_date}&d2={end_date}"
                )
                response = httpx.get(url, timeout=30.0, follow_redirects=True)
                response.raise_for_status()

                if not response.text.strip() or "No data" in response.text:
                    continue

                df = self._parse_csv(response.text)
                if df is not None and not df.empty:
                    results[symbol] = df
            except Exception as e:
                logger.warning("Stooq fetch failed for %s: %s", symbol, e)
                continue

        if not results:
            raise EmptyDataError(self.source_name, symbols)

        return results

    def _parse_csv(self, content: str) -> pd.DataFrame | None:
        from io import StringIO

        try:
            df = pd.read_csv(StringIO(content))
        except Exception:
            return None

        if df.empty:
            return None

        column_rename = {
            "Date": "bar_date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=column_rename)

        if "bar_date" not in df.columns:
            return None

        df["bar_date"] = pd.to_datetime(df["bar_date"], errors="coerce")
        df = df.dropna(subset=["bar_date"])
        df = df.set_index("bar_date")
        df.index.name = None

        if "close" in df.columns:
            df["adjusted_close"] = df["close"]

        df = strip_tz(df)
        df = enforce_ohlcv_schema(df)
        return df
