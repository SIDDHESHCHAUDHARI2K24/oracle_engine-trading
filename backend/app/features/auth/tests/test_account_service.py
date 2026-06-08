"""Tests for account management service — TDD red phase (T1).

Covers: change_password, list_sessions, logout_everywhere.
"""

from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import account_service
from app.features.auth import repository as auth_repo
from app.features.auth import service as auth_service
from app.features.auth.models import Session, User

_ph = PasswordHasher()


async def _make_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, hashed_password=_ph.hash("correct-password"))
    db.add(user)
    await db.flush()
    return user


# ─── change_password ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_change_password_success(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "change-pass@test.example")
    old_hash = user.hashed_password

    await account_service.change_password(
        db_session, user.id, "correct-password", "new-password-123"
    )

    await db_session.refresh(user)
    assert user.hashed_password != old_hash
    assert not auth_service.verify_password("correct-password", user.hashed_password)
    assert auth_service.verify_password("new-password-123", user.hashed_password)


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "wrong-old@test.example")

    with pytest.raises(ValueError, match="old password"):
        await account_service.change_password(
            db_session, user.id, "wrong-old-pass", "new-password-123"
        )


@pytest.mark.asyncio
async def test_change_password_revokes_sibling_sessions(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, "revoke-sibs@test.example")
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    s1 = await auth_repo.create_session(db_session, user.id, "hash-a", expires)
    s2 = await auth_repo.create_session(db_session, user.id, "hash-b", expires)
    s3 = await auth_repo.create_session(db_session, user.id, "hash-c", expires)

    await account_service.change_password(
        db_session,
        user.id,
        "correct-password",
        "new-password-456",
        current_session_id=s2.id,
    )

    result = await db_session.execute(
        select(Session).where(Session.user_id == user.id)
    )
    sessions = result.scalars().all()
    session_ids = {s.id for s in sessions}

    assert s2.id in session_ids
    assert s1.id not in session_ids
    assert s3.id not in session_ids
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_change_password_enforces_min_length(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "minlen@test.example")

    with pytest.raises(ValueError, match="12"):
        await account_service.change_password(
            db_session, user.id, "correct-password", "short"
        )


# ─── list_sessions ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_sessions_returns_active(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "list-active@test.example")
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=30)
    past = now - timedelta(days=1)

    s1 = await auth_repo.create_session(db_session, user.id, "hash-a1", future)
    s2 = await auth_repo.create_session(db_session, user.id, "hash-a2", future)
    s3 = await auth_repo.create_session(db_session, user.id, "hash-exp", past)

    result = await account_service.list_sessions(db_session, user.id)

    result_ids = {r.id for r in result}
    assert len(result) == 2
    assert s1.id in result_ids
    assert s2.id in result_ids
    assert s3.id not in result_ids


@pytest.mark.asyncio
async def test_list_sessions_flags_current(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "flag-current@test.example")
    future = datetime.now(timezone.utc) + timedelta(days=30)

    s1 = await auth_repo.create_session(db_session, user.id, "hash-c1", future)
    await auth_repo.create_session(db_session, user.id, "hash-c2", future)

    result = await account_service.list_sessions(
        db_session, user.id, current_session_id=s1.id
    )

    for r in result:
        if r.id == s1.id:
            assert r.is_current is True
        else:
            assert r.is_current is False


# ─── logout_everywhere ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logout_everywhere_deletes_all(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "logout-all@test.example")
    future = datetime.now(timezone.utc) + timedelta(days=30)

    await auth_repo.create_session(db_session, user.id, "hash-d1", future)
    await auth_repo.create_session(db_session, user.id, "hash-d2", future)
    await auth_repo.create_session(db_session, user.id, "hash-d3", future)

    await account_service.logout_everywhere(db_session, user.id)

    result = await db_session.execute(
        select(Session).where(Session.user_id == user.id)
    )
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_logout_everywhere_keeps_current(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "logout-keep@test.example")
    future = datetime.now(timezone.utc) + timedelta(days=30)

    s1 = await auth_repo.create_session(db_session, user.id, "hash-k1", future)
    await auth_repo.create_session(db_session, user.id, "hash-k2", future)

    await account_service.logout_everywhere(
        db_session, user.id, keep_current_session_id=s1.id
    )

    result = await db_session.execute(
        select(Session).where(Session.user_id == user.id)
    )
    sessions = result.scalars().all()
    assert len(sessions) == 1
    assert sessions[0].id == s1.id
