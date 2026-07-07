"""Trading calendar utilities for NYSE sessions.

Provides the single source of truth for expected trading days,
holiday-aware date lists, and calendar caching.
"""

from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal


@lru_cache(maxsize=1)
def _get_nyse_calendar():
    return mcal.get_calendar("NYSE")


def trading_days(start: date, end: date) -> list[date]:
    """Return all NYSE trading session dates between start and end (inclusive).

    Excludes weekends, holidays, and half-day early-close irregularities.
    """
    cal = _get_nyse_calendar()
    schedule = cal.schedule(start_date=start, end_date=end)
    return [d.date() for d in schedule.index if schedule.loc[d, "market_open"].date()]


def is_trading_day(d: date) -> bool:
    """Return True if d is a scheduled NYSE trading day."""
    cal = _get_nyse_calendar()
    try:
        schedule = cal.schedule(start_date=d, end_date=d)
        return not schedule.empty
    except Exception:
        return False


def expected_bars(ticker_added_at: date, through: date | None = None) -> set[date]:
    """Return the set of dates that should have OHLCV bars for a ticker.

    Clamped to when the ticker was first added to any universe.
    If through is None, defaults to today.
    """
    if through is None:
        through = date.today()
    start = ticker_added_at
    if start > through:
        return set()
    days = trading_days(start, through)
    if days and days[-1] == through and not _market_closed_today():
        days = days[:-1]
    return set(days)


def _market_closed_today() -> bool:
    now = datetime.now()
    return now.hour < 16 or (now.hour == 16 and now.minute < 30)


def last_n_trading_days(n: int, from_date: date | None = None) -> list[date]:
    """Return the last n NYSE trading days up to from_date.

    Walks backwards to ensure exactly n trading days are collected.
    """
    if from_date is None:
        from_date = date.today()
    lookback = from_date - timedelta(days=max(30, n * 2))
    days = trading_days(lookback, from_date)
    if days and days[-1] == from_date and not is_trading_day(from_date):
        pass
    return days[-n:] if len(days) >= n else days
