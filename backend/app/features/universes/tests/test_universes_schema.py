"""Schema-level tests for universes — must run before implementation changes."""

import uuid
from datetime import datetime, timezone

from app.features.universes.schemas import UniverseSummary


def test_universe_summary_has_ticker_count() -> None:
    summary = UniverseSummary(
        id=uuid.uuid4(),
        name="sp500",
        display_name="S&P 500",
        is_system_managed=True,
        created_at=datetime.now(timezone.utc),
        ticker_count=3,
    )
    assert summary.ticker_count == 3
