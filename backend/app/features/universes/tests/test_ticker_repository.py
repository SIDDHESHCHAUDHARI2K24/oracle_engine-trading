"""Ticker repository tests — TDD: validate_and_upsert_tickers does NOT exist yet.

These tests MUST fail (RED phase) before the implementation is written.
"""

import pytest

from app.features.universes.models import Ticker
from app.features.universes.shared.alpaca_assets import AssetInfo


MOCK_ALPACA_MAP = {
    "AAPL": AssetInfo(
        symbol="AAPL", exchange="NASDAQ", asset_type="equity", tradable=True
    ),
    "MSFT": AssetInfo(
        symbol="MSFT", exchange="NASDAQ", asset_type="equity", tradable=True
    ),
    "NVDA": AssetInfo(
        symbol="NVDA", exchange="NASDAQ", asset_type="equity", tradable=True
    ),
    "SPY": AssetInfo(
        symbol="SPY", exchange="ARCA", asset_type="etf", tradable=True
    ),
}


async def _assert_ticker_in_db(db, symbol: str):
    from sqlalchemy import select

    result = await db.execute(select(Ticker).where(Ticker.symbol == symbol))
    return result.scalar_one_or_none()


# ---- Tests that MUST FAIL (TDD RED phase) ----


@pytest.mark.asyncio
async def test_valid_symbol_inserts(db_session):
    """AAPL is valid per Alpaca → should be inserted."""
    from app.features.universes.repository import validate_and_upsert_tickers

    result = await validate_and_upsert_tickers(
        db=db_session, symbols=["AAPL"], alpaca_map=MOCK_ALPACA_MAP
    )
    assert result.inserted == 1
    assert result.skipped == 0
    assert result.invalid == []
    ticker = await _assert_ticker_in_db(db_session, "AAPL")
    assert ticker is not None
    assert ticker.name == "AAPL"
    assert ticker.exchange == "NASDAQ"
    assert ticker.asset_type == "equity"


@pytest.mark.asyncio
async def test_unknown_symbol_reported_invalid(db_session):
    """FAKE is NOT in Alpaca → marked invalid, NOT inserted."""
    from app.features.universes.repository import validate_and_upsert_tickers

    result = await validate_and_upsert_tickers(
        db=db_session, symbols=["FAKE"], alpaca_map=MOCK_ALPACA_MAP
    )
    assert result.inserted == 0
    assert result.skipped == 0
    assert result.invalid == ["FAKE"]
    ticker = await _assert_ticker_in_db(db_session, "FAKE")
    assert ticker is None


@pytest.mark.asyncio
async def test_duplicate_is_idempotent(db_session):
    """Insert AAPL twice → only inserted once, second call skips."""
    from app.features.universes.repository import validate_and_upsert_tickers

    r1 = await validate_and_upsert_tickers(
        db=db_session, symbols=["AAPL"], alpaca_map=MOCK_ALPACA_MAP
    )
    assert r1.inserted == 1

    r2 = await validate_and_upsert_tickers(
        db=db_session, symbols=["AAPL"], alpaca_map=MOCK_ALPACA_MAP
    )
    assert r2.inserted == 0
    assert r2.skipped == 1
    assert r2.invalid == []


@pytest.mark.asyncio
async def test_bulk_mixed_returns_breakdown(db_session):
    """Mix of valid and invalid → correct counts."""
    from app.features.universes.repository import validate_and_upsert_tickers

    result = await validate_and_upsert_tickers(
        db=db_session,
        symbols=["AAPL", "FAKE", "MSFT", "ZZZZ"],
        alpaca_map=MOCK_ALPACA_MAP,
    )
    assert result.inserted == 2
    assert result.skipped == 0
    assert set(result.invalid) == {"FAKE", "ZZZZ"}


@pytest.mark.asyncio
async def test_symbol_normalization(db_session):
    """'brk.b' normalizes to 'BRK-B' before Alpaca lookup."""
    from app.features.universes.repository import validate_and_upsert_tickers

    extended_map = {
        **MOCK_ALPACA_MAP,
        "BRK-B": AssetInfo(
            symbol="BRK-B", exchange="NYSE", asset_type="equity", tradable=True
        ),
    }
    result = await validate_and_upsert_tickers(
        db=db_session, symbols=["brk.b"], alpaca_map=extended_map
    )
    assert result.inserted == 1
    assert result.invalid == []
    ticker = await _assert_ticker_in_db(db_session, "BRK-B")
    assert ticker is not None
    assert ticker.symbol == "BRK-B"


@pytest.mark.asyncio
async def test_full_sync_endpoint_is_admin_only():
    """Placeholder — ensure the sync endpoint module can be imported later."""
    pass
