"""Membership state-machine tests — TDD RED phase.

These tests MUST fail (ImportError/AttributeError) before implementation.
Mock Alpaca in ALL tests — never hit the live API.
"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.features.universes.models import Universe, Ticker, UniverseMembership
from app.features.universes.shared.alpaca_assets import AssetInfo

MOCK_ALPACA_MAP = {
    "AAPL": AssetInfo(symbol="AAPL", exchange="NASDAQ", asset_type="equity", tradable=True),
    "MSFT": AssetInfo(symbol="MSFT", exchange="NASDAQ", asset_type="equity", tradable=True),
    "NVDA": AssetInfo(symbol="NVDA", exchange="NASDAQ", asset_type="equity", tradable=True),
    "SPY": AssetInfo(symbol="SPY", exchange="ARCA", asset_type="etf", tradable=True),
}


async def _create_universe(db, name="test-universe", system_managed=False):
    universe = Universe(
        name=name,
        display_name=name,
        is_system_managed=system_managed,
        public_id="uni_test1234",
    )
    db.add(universe)
    await db.flush()
    return universe


async def _insert_ticker(db, symbol="AAPL"):
    ticker = Ticker(symbol=symbol, name=symbol, exchange="NASDAQ", asset_type="equity")
    db.add(ticker)
    await db.flush()
    return ticker


async def _membership_count(db, universe_id):
    result = await db.execute(
        select(UniverseMembership).where(
            UniverseMembership.universe_id == universe_id
        )
    )
    return len(result.scalars().all())


@pytest.mark.asyncio
async def test_add_ticker_creates_membership(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    result = await universes_service.add_members(db_session, universe.id, ["AAPL"])

    assert "AAPL" in result.added
    assert len(result.already_present) == 0
    assert len(result.invalid) == 0

    memberships = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id
            )
        )
    ).scalars().all()
    assert len(memberships) == 1
    assert memberships[0].added_at is not None
    assert memberships[0].removed_at is None


@pytest.mark.asyncio
async def test_add_invalid_symbol_reported(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    result = await universes_service.add_members(db_session, universe.id, ["FAKE"])

    assert len(result.added) == 0
    assert result.invalid == ["FAKE"]

    count = await _membership_count(db_session, universe.id)
    assert count == 0


@pytest.mark.asyncio
async def test_skip_already_active(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)

    r1 = await universes_service.add_members(db_session, universe.id, ["AAPL"])
    assert "AAPL" in r1.added

    r2 = await universes_service.add_members(db_session, universe.id, ["AAPL"])
    assert len(r2.added) == 0
    assert "AAPL" in r2.already_present

    count = await _membership_count(db_session, universe.id)
    assert count == 1


@pytest.mark.asyncio
async def test_remove_member_sets_removed_at(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    await universes_service.add_members(db_session, universe.id, ["AAPL"])

    memberships = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id, UniverseMembership.removed_at.is_(None)
            )
        )
    ).scalars().all()
    ticker_id = memberships[0].ticker_id

    await universes_service.remove_member(db_session, universe.id, ticker_id)
    await db_session.flush()

    m = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id,
                UniverseMembership.ticker_id == ticker_id,
            )
        )
    ).scalar_one_or_none()
    assert m is not None
    assert m.removed_at is not None


@pytest.mark.asyncio
async def test_remove_non_member_returns_404(db_session):
    from app.features.universes import service as universes_service

    universe = await _create_universe(db_session)
    ticker = await _insert_ticker(db_session)

    with pytest.raises(ValueError):
        await universes_service.remove_member(db_session, universe.id, ticker.id)


@pytest.mark.asyncio
async def test_readd_after_remove_creates_new_row(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)

    r1 = await universes_service.add_members(db_session, universe.id, ["AAPL"])
    assert "AAPL" in r1.added

    memberships = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id, UniverseMembership.removed_at.is_(None)
            )
        )
    ).scalars().all()
    ticker_id = memberships[0].ticker_id

    await universes_service.remove_member(db_session, universe.id, ticker_id)
    await db_session.flush()

    r2 = await universes_service.add_members(db_session, universe.id, ["AAPL"])
    assert "AAPL" in r2.added

    all_rows = (
        await db_session.execute(
            select(UniverseMembership).where(UniverseMembership.universe_id == universe.id)
        )
    ).scalars().all()
    assert len(all_rows) == 2

    active_rows = [r for r in all_rows if r.removed_at is None]
    assert len(active_rows) == 1


@pytest.mark.asyncio
async def test_active_members_query(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    await universes_service.add_members(db_session, universe.id, ["AAPL", "MSFT"])

    members = await universes_service.get_members(db_session, universe.id)
    symbols = {t.symbol for t in members}
    assert symbols == {"AAPL", "MSFT"}

    results = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id, UniverseMembership.removed_at.is_(None)
            )
        )
    ).scalars().all()
    ticker_id = results[0].ticker_id
    await universes_service.remove_member(db_session, universe.id, ticker_id)
    await db_session.flush()

    members_after = await universes_service.get_members(db_session, universe.id)
    assert len(members_after) == 1


@pytest.mark.asyncio
async def test_point_in_time_snapshot_before_add(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)

    before = datetime.now(timezone.utc) - timedelta(days=30)
    await universes_service.add_members(db_session, universe.id, ["AAPL"])

    members = await universes_service.get_members(db_session, universe.id, at_date=before)
    assert len(members) == 0


@pytest.mark.asyncio
async def test_point_in_time_snapshot_between_add_and_remove(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)

    await universes_service.add_members(db_session, universe.id, ["AAPL"])

    checkpoint = datetime.now(timezone.utc)

    results = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id, UniverseMembership.removed_at.is_(None)
            )
        )
    ).scalars().all()
    ticker_id = results[0].ticker_id
    await universes_service.remove_member(db_session, universe.id, ticker_id)
    await db_session.flush()

    members = await universes_service.get_members(db_session, universe.id, at_date=checkpoint)
    assert len(members) == 1
    assert members[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_point_in_time_snapshot_after_remove(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    await universes_service.add_members(db_session, universe.id, ["AAPL"])

    results = (
        await db_session.execute(
            select(UniverseMembership).where(
                UniverseMembership.universe_id == universe.id, UniverseMembership.removed_at.is_(None)
            )
        )
    ).scalars().all()
    ticker_id = results[0].ticker_id
    await universes_service.remove_member(db_session, universe.id, ticker_id)
    await db_session.flush()

    after_remove = datetime.now(timezone.utc) + timedelta(hours=1)
    members = await universes_service.get_members(db_session, universe.id, at_date=after_remove)
    assert len(members) == 0


@pytest.mark.asyncio
async def test_bulk_add_breakdown(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    result = await universes_service.add_members(
        db_session, universe.id, ["AAPL", "FAKE", "MSFT"]
    )
    assert set(result.added) == {"AAPL", "MSFT"}
    assert result.invalid == ["FAKE"]
    assert len(result.already_present) == 0


@pytest.mark.asyncio
async def test_cannot_modify_membership_on_deleted_universe(db_session, monkeypatch):
    from app.features.universes import service as universes_service

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    universe = await _create_universe(db_session)
    universe.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()

    with pytest.raises(ValueError):
        await universes_service.add_members(db_session, universe.id, ["AAPL"])

    ticker = await _insert_ticker(db_session)
    with pytest.raises(ValueError):
        await universes_service.remove_member(db_session, universe.id, ticker.id)
