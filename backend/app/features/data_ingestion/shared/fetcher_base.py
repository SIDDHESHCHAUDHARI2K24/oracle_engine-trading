"""Abstract Base Class for all OHLCV and macro data fetchers.

Defines the uniform interface that the NumericalOrchestrator uses
for transparent failover across sources. All concrete fetchers
inherit from this ABC and return identically-shaped DataFrames.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar

import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import FetcherError

F = TypeVar("F", bound=Callable[..., Any])


def fetcher_retry(func: F) -> F:
    """Decorator that applies tenacity retry (3 attempts, exponential backoff).

    Applied to each concrete fetcher's network call so the orchestrator
    can rely on the fetcher either returning data or raising on exhaustion.
    """
    decorated = retry(
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((FetcherError, ConnectionError, TimeoutError)),
        reraise=True,
    )(func)
    return decorated  # type: ignore[return-value]


def strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Strip timezone information from a DataFrame index.

    Non-negotiable for TimescaleDB merges — mixing timezone-aware and
    timezone-naive indexes causes implicit alignment failures.
    """
    df = df.copy()
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def enforce_ohlcv_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce the standard OHLCV schema: correct dtypes, no NaNs in OHLCV.

    Returns a cleaned DataFrame or raises on unrecoverable schema violations.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise FetcherError("schema_enforcer", [], original_error=ValueError(f"Missing columns: {missing}"))

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

    if df[["open", "high", "low", "close"]].isna().any().any():
        df = df.dropna(subset=["open", "high", "low", "close"])

    return df


class DataFetcher(ABC):
    """Abstract Base Class for all numerical data fetchers.

    Subclasses implement `fetch()` to return per-symbol OHLCV DataFrames
    or a single macro DataFrame. The Orchestrator iterates failover
    sources by calling each concrete fetcher in order.

    Per spec a1.2: __init__(**kwargs), @abstractmethod fetch() -> pd.DataFrame | dict[str, pd.DataFrame].
    """

    def __init__(self, **kwargs: Any):
        self._config = kwargs

    @abstractmethod
    def fetch(self, symbols: list[str], start_date: str, end_date: str) -> dict[str, pd.DataFrame]:
        """Fetch OHLCV data for the given symbols and date range.

        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'MSFT'])
            start_date: ISO-format start date string
            end_date: ISO-format end date string

        Returns:
            dict mapping symbol → DataFrame with columns:
            [open, high, low, close, adjusted_close, volume] and a date index.

        Raises:
            FetcherError: On failure after retries (triggers failover)
            EmptyDataError: When the source returns zero rows
        """
        ...

    @property
    def source_name(self) -> str:
        """Human-readable source identifier (e.g., 'yfinance', 'alpaca', 'stooq')."""
        return self.__class__.__name__.replace("Fetcher", "").lower()
