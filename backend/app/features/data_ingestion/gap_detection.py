"""Gap detection — calendar-aware comparison of expected vs present bar dates.

Drives the daily flow's self-healing gap-fill mechanism.
"""

import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from .repository import get_present_bar_dates
from .shared.trading_calendar import expected_bars

logger = logging.getLogger(__name__)


async def detect_gaps(
    session: AsyncSession,
    ticker_id: str,
    added_at: date,
    through: date | None = None,
    max_lookback_days: int = 30,
) -> list[date]:
    """Return missing bar dates for a ticker.

    Compares expected trading days (since the ticker was added to
    any universe) against actually-present bar dates in the DB.

    Args:
        session: DB session.
        ticker_id: Ticker UUID.
        added_at: Date the ticker was first added to a universe.
        through: End date for comparison (defaults to today).
        max_lookback_days: Max trading days to look back for gaps
            (prevents huge backfills inside the daily flow).

    Returns:
        Sorted list of missing trading dates.
    """
    all_expected = expected_bars(added_at, through)
    present = await get_present_bar_dates(session, ticker_id)
    gaps = sorted(all_expected - present)

    if max_lookback_days > 0 and len(gaps) > max_lookback_days:
        logger.info(
            "Ticker %s has %d gaps, capping lookback to %d days",
            ticker_id,
            len(gaps),
            max_lookback_days,
        )
        today = through or date.today()
        from .shared.trading_calendar import last_n_trading_days

        recent_trading_days = set(last_n_trading_days(max_lookback_days, today))
        gaps = sorted(set(gaps) & recent_trading_days)

    return gaps


async def detect_gaps_batch(
    session: AsyncSession,
    ticker_added_map: dict[str, date],
    through: date | None = None,
) -> dict[str, list[date]]:
    """Detect gaps for multiple tickers in batch.

    Args:
        session: DB session.
        ticker_added_map: Mapping of ticker_id → date added.
        through: End date for comparison.

    Returns:
        Mapping of ticker_id → list of missing dates.
    """
    results: dict[str, list[date]] = {}
    for ticker_id, added_at in ticker_added_map.items():
        gaps = await detect_gaps(session, ticker_id, added_at, through)
        if gaps:
            results[ticker_id] = gaps
    return results
