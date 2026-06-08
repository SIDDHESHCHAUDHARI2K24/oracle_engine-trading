"""Cross-feature integration tests.

Tests the full lifecycle of universes and auth account management
using the service layer with the db_session fixture.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text

from app.features.auth import account_service
from app.features.auth import repository as auth_repo
from app.features.auth import service as auth_service
from app.features.auth.models import Session, User
from app.features.universes import repository as universes_repo
from app.features.universes import service as universes_service
from app.features.universes.shared.alpaca_assets import AssetInfo

pytestmark = pytest.mark.integration

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
}


@pytest.mark.asyncio
async def test_universe_lifecycle_full(db_session, monkeypatch):
    """Full lifecycle: create -> add tickers -> point-in-time -> remove -> soft-delete -> restore."""

    monkeypatch.setattr(
        "app.features.universes.service.get_alpaca_asset_map",
        lambda: MOCK_ALPACA_MAP,
    )

    # 1. Create custom universe
    universe = await universes_service.create_universe(
        db_session,
        name="test-lifecycle",
        display_name="Test Lifecycle",
        description="Integration test",
    )
    assert uuid.UUID(str(universe.id))
    assert universe.public_id is not None
    assert universe.public_id.startswith("uni_")
    assert universe.is_system_managed is False

    # 2. Add tickers (mock Alpaca)
    result = await universes_service.add_members(
        db_session, universe.id, ["AAPL", "FAKE", "MSFT"]
    )
    assert set(result.added) == {"AAPL", "MSFT"}
    assert result.invalid == ["FAKE"]
    assert len(result.already_present) == 0

    # 3. Verify active members
    members = await universes_service.get_members(db_session, universe.id)
    assert len(members) == 2
    member_symbols = {m.symbol for m in members}
    assert member_symbols == {"AAPL", "MSFT"}

    # 4. Point-in-time snapshot (before add)
    before = datetime.now(timezone.utc) - timedelta(days=30)
    members_before = await universes_service.get_members(
        db_session, universe.id, at_date=before
    )
    assert len(members_before) == 0

    # 5. Remove a ticker
    aapl_ticker = next(m for m in members if m.symbol == "AAPL")
    await universes_service.remove_member(db_session, universe.id, aapl_ticker.id)
    members_after_remove = await universes_service.get_members(db_session, universe.id)
    assert len(members_after_remove) == 1
    assert members_after_remove[0].symbol == "MSFT"

    # 6. Soft delete
    await universes_service.soft_delete_universe(db_session, universe.id)
    await db_session.flush()

    deleted_universe = await universes_repo.get_universe_by_id(
        db_session, universe.id, include_deleted=True
    )
    assert deleted_universe is not None
    assert deleted_universe.deleted_at is not None

    active_universe = await universes_repo.get_universe_by_id(db_session, universe.id)
    assert active_universe is None

    # 7. List excludes deleted by default
    result_list = await universes_service.list_universes(db_session)
    universe_ids = {u.id for u in result_list.universes}
    assert universe.id not in universe_ids

    # 8. Include deleted
    result_with_deleted = await universes_service.list_universes(
        db_session, include_deleted=True
    )
    universe_ids_with = {u.id for u in result_with_deleted.universes}
    assert universe.id in universe_ids_with

    # 9. Restore
    await universes_service.restore_universe(db_session, universe.id)
    result_restored = await universes_service.list_universes(db_session)
    restored_ids = {u.id for u in result_restored.universes}
    assert universe.id in restored_ids


@pytest.mark.asyncio
async def test_auth_account_management_flow(db_session, monkeypatch):
    """Full auth flow: create user -> change password -> verify sessions -> logout everywhere."""

    async def safe_delete_all_sessions(db, user_id, exclude_id=None):
        if exclude_id:
            await db.execute(
                text("DELETE FROM sessions WHERE user_id = :uid AND id != :exclude"),
                {"uid": user_id, "exclude": exclude_id},
            )
        else:
            await db.execute(
                text("DELETE FROM sessions WHERE user_id = :uid"),
                {"uid": user_id},
            )
        await db.flush()

    monkeypatch.setattr(auth_repo, "delete_all_sessions", safe_delete_all_sessions)

    # 1. Create a test user
    user = User(
        email="integration-test@example.com",
        hashed_password=auth_service.ph.hash("initial-password123"),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.flush()

    # 2. Create multiple sessions manually (avoid commit to stay within transaction)
    future = datetime.now(timezone.utc) + timedelta(days=30)

    s1 = Session(user_id=user.id, refresh_token_hash="hash-int1", expires_at=future)
    s2 = Session(user_id=user.id, refresh_token_hash="hash-int2", expires_at=future)
    s3 = Session(user_id=user.id, refresh_token_hash="hash-int3", expires_at=future)
    db_session.add_all([s1, s2, s3])
    await db_session.flush()

    # 3. Change password, keep current session s1
    await account_service.change_password(
        db_session,
        user.id,
        "initial-password123",
        "new-secure-password456",
        current_session_id=s1.id,
    )

    # 4. Verify new password works
    assert auth_service.verify_password("new-secure-password456", user.hashed_password)

    # 5. Verify sibling sessions revoked (s2, s3 gone); s1 retained
    result = await db_session.execute(select(Session).where(Session.user_id == user.id))
    all_sessions = result.scalars().all()
    session_ids = {s.id for s in all_sessions}
    assert len(all_sessions) == 1
    assert s1.id in session_ids
    assert s2.id not in session_ids
    assert s3.id not in session_ids

    # 6. Verify old password fails
    assert not auth_service.verify_password("initial-password123", user.hashed_password)

    # 7. Logout everywhere
    await account_service.logout_everywhere(db_session, user.id)

    result = await db_session.execute(select(Session).where(Session.user_id == user.id))
    remaining = result.scalars().all()
    assert len(remaining) == 0
