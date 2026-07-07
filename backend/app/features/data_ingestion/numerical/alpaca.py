"""Alpaca Market Data OHLCV fetcher — secondary source (Block A1).

Uses alpaca-py's StockHistoricalDataClient for daily bars.
Returns identical schema to YahooFinanceFetcher for transparent failover.
"""

import logging

import pandas as pd

from app.features.core.config import settings

from ..shared.exceptions import EmptyDataError, FetcherError
from ..shared.fetcher_base import (
    DataFetcher,
    enforce_ohlcv_schema,
    fetcher_retry,
    strip_tz,
)

logger = logging.getLogger(__name__)


class AlpacaFetcher(DataFetcher):
    """Secondary OHLCV source via Alpaca Market Data API.

    Requires ALPACA_API_KEY + ALPACA_SECRET_KEY (free paper-trading account).
    Returns identical schema to YahooFinance for transparent failover.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def fetch(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}
        if not settings.alpaca_api_key or not settings.alpaca_secret_key:
            raise FetcherError(
                self.source_name,
                symbols,
                original_error=ValueError("Alpaca API keys not configured"),
            )

        validated = [s.strip().upper() for s in symbols]
        return self._fetch_all(validated, start_date, end_date)

    @fetcher_retry
    def _fetch_all(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        try:
            client = StockHistoricalDataClient(
                api_key=settings.alpaca_api_key,
                secret_key=settings.alpaca_secret_key,
            )
            request_params = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=TimeFrame(1, TimeFrameUnit.Day),
                start=pd.Timestamp(start_date).to_pydatetime(),
                end=pd.Timestamp(end_date).to_pydatetime(),
                adjustment="all",  # type: ignore[arg-type]
            )
            bars = client.get_stock_bars(request_params)
        except Exception as e:
            raise FetcherError(self.source_name, symbols, original_error=e) from e

        return self._unpack_bars(bars, symbols)  # type: ignore[arg-type]

    def _unpack_bars(self, bars: dict, symbols: list[str]) -> dict[str, pd.DataFrame]:
        results: dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            try:
                symbol_bars = bars.get(symbol)
                if symbol_bars is None or len(symbol_bars) == 0:
                    continue

                records = [
                    {
                        "bar_date": b.timestamp.date(),
                        "open": float(b.open),
                        "high": float(b.high),
                        "low": float(b.low),
                        "close": float(b.close),
                        "adjusted_close": float(b.close),
                        "volume": int(b.volume),
                    }
                    for b in symbol_bars
                ]
                df = pd.DataFrame(records)
                if df.empty:
                    continue
                df = df.set_index("bar_date")
                df.index = pd.to_datetime(df.index)
                df.index.name = None
                df = strip_tz(df)
                df = enforce_ohlcv_schema(df)
                results[symbol] = df
            except Exception:
                logger.warning("Failed to unpack %s from Alpaca bars", symbol)

        if not results:
            raise EmptyDataError(self.source_name, symbols)

        return results
