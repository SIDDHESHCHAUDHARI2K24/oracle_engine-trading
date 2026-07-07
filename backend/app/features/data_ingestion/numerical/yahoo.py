"""Yahoo Finance OHLCV fetcher — primary data source (Block A1).

Fetches daily OHLCV via yfinance with per-symbol isolation,
empty-return detection, and strict schema enforcement.
"""

import logging

import pandas as pd
import yfinance as yf

from ..shared.exceptions import EmptyDataError, FetcherError
from ..shared.fetcher_base import (
    DataFetcher,
    enforce_ohlcv_schema,
    fetcher_retry,
    strip_tz,
)

logger = logging.getLogger(__name__)


class YahooFinanceFetcher(DataFetcher):
    """Primary OHLCV source via yfinance.

    Fetches daily bars for multiple symbols, detects and raises on
    empty returns (the #1 yfinance gotcha), and enforces strict schema.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._max_symbols_per_batch = kwargs.get("max_symbols_per_batch", 50)

    def fetch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}

        validated_symbols = self._normalize_symbols(symbols)
        return self._fetch_all(validated_symbols, start_date, end_date)

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        return [s.strip().upper().replace("-", ".") for s in symbols]

    @fetcher_retry
    def _fetch_all(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        batches = [
            symbols[i : i + self._max_symbols_per_batch]
            for i in range(0, len(symbols), self._max_symbols_per_batch)
        ]
        results: dict[str, pd.DataFrame] = {}

        for batch in batches:
            batch_results = self._fetch_batch(batch, start_date, end_date)
            results.update(batch_results)

        if not results:
            raise EmptyDataError(self.source_name, symbols)

        return results

    def _fetch_batch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        try:
            df = yf.download(
                symbols,
                start=start_date,
                end=end_date,
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=False,
            )
        except Exception as e:
            raise FetcherError(self.source_name, symbols, original_error=e) from e

        if df.empty:
            raise EmptyDataError(self.source_name, symbols)

        return self._unpack_batch(df, symbols)

    def _unpack_batch(
        self, df: pd.DataFrame, symbols: list[str]
    ) -> dict[str, pd.DataFrame]:
        results: dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            try:
                ticker_df = self._extract_symbol(df, symbol)
                if ticker_df is not None and not ticker_df.empty:
                    clean = self._clean(ticker_df)
                    results[symbol] = clean
            except Exception:
                logger.warning("Failed to unpack %s from yfinance batch", symbol)

        return results

    def _extract_symbol(
        self, df: pd.DataFrame, symbol: str
    ) -> pd.DataFrame | None:
        if isinstance(df.columns, pd.MultiIndex):
            if symbol not in df.columns.get_level_values(0):
                return None
            ticker_df = df.xs(symbol, axis=1, level=0).copy()
        else:
            ticker_df = df.copy()

        if ticker_df.empty:
            return None

        ticker_df.columns = [c.lower().replace(" ", "_") for c in ticker_df.columns]
        column_map = {
            "adj_close": "adjusted_close",
            "adj close": "adjusted_close",
        }
        ticker_df = ticker_df.rename(columns=column_map)

        if "adjusted_close" not in ticker_df.columns and "close" in ticker_df.columns:
            ticker_df["adjusted_close"] = ticker_df["close"]

        return ticker_df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = strip_tz(df)
        df = enforce_ohlcv_schema(df)

        has_adjusted_close = "adjusted_close" in df.columns
        required_cols = ["open", "high", "low", "close", "volume"]
        if has_adjusted_close:
            required_cols.append("adjusted_close")
        for col in required_cols:
            if col not in df.columns:
                raise FetcherError(
                    self.source_name, [],
                    original_error=ValueError(f"Missing column: {col}"),
                )

        return df[required_cols]
