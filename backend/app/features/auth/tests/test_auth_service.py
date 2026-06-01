"""Unit tests for the auth service — T6.S2 TDD requirement.

Covers: password verification, JWT issuance/verification, session lifecycle.

Sync tests (no DB): verify_password, issue_access_token, verify_access_token.
Async tests (db_session fixture): authenticate, issue_tokens, rotate_refresh, revoke_refresh.

asyncio_mode = auto (set in pytest.ini) — no @pytest.mark.asyncio needed.
"""

import uuid

from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import service as auth_service
from app.features.auth.models import User

_ph = PasswordHasher()


# ─── Helper ────────────────────────────────────────────────────────────────


async def _make_user(db: AsyncSession, email: str) -> User:
    """Insert a test user with password 'correct-password' and return it."""
    user = User(email=email, hashed_password=_ph.hash("correct-password"))
    db.add(user)
    await db.flush()  # Assigns id/created_at; transaction rolls back after test.
    return user


# ─── verify_password ────────────────────────────────────────────────────────


def test_verify_password_correct_password_returns_true() -> None:
    hashed = _ph.hash("my-secret")
    assert auth_service.verify_password("my-secret", hashed) is True


def test_verify_password_wrong_password_returns_false() -> None:
    hashed = _ph.hash("my-secret")
    assert auth_service.verify_password("wrong", hashed) is False


# ─── JWT issuance + verification ───────────────────────────────────────────


def test_issue_access_token_is_three_part_jwt() -> None:
    token = auth_service.issue_access_token(uuid.uuid4())
    assert len(token.split(".")) == 3


def test_verify_access_token_roundtrip_returns_same_user_id() -> None:
    user_id = uuid.uuid4()
    token = auth_service.issue_access_token(user_id)
    assert auth_service.verify_access_token(token) == user_id


def test_verify_access_token_tampered_signature_returns_none() -> None:
    token = auth_service.issue_access_token(uuid.uuid4())
    header, payload, sig = token.split(".")
    tampered = f"{header}.{payload}.{sig[:-4]}XXXX"
    assert auth_service.verify_access_token(tampered) is None


def test_verify_access_token_garbage_returns_none() -> None:
    assert auth_service.verify_access_token("not.a.jwt") is None
    assert auth_service.verify_access_token("") is None


# ─── authenticate ──────────────────────────────────────────────────────────


async def test_authenticate_valid_credentials_returns_user(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, "auth-valid@test.example")
    result = await auth_service.authenticate(db_session, user.email, "correct-password")
    assert result is not None
    assert result.id == user.id


async def test_authenticate_wrong_password_returns_none(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, "auth-wrong@test.example")
    result = await auth_service.authenticate(db_session, user.email, "wrong-password")
    assert result is None


async def test_authenticate_unknown_email_returns_none(
    db_session: AsyncSession,
) -> None:
    result = await auth_service.authenticate(db_session, "nobody@test.example", "any")
    assert result is None


# ─── issue_tokens ──────────────────────────────────────────────────────────


async def test_issue_tokens_returns_valid_jwt_and_opaque_refresh(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session, "issue@test.example")
    access, refresh = await auth_service.issue_tokens(db_session, user.id)
    assert auth_service.verify_access_token(access) == user.id
    assert isinstance(refresh, str) and len(refresh) > 20


# ─── rotate_refresh ────────────────────────────────────────────────────────


async def test_rotate_refresh_returns_new_token_pair(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "rotate@test.example")
    _, old_refresh = await auth_service.issue_tokens(db_session, user.id)
    result = await auth_service.rotate_refresh(db_session, old_refresh)
    assert result is not None
    new_access, new_refresh = result
    assert auth_service.verify_access_token(new_access) == user.id
    assert new_refresh != old_refresh


async def test_rotate_refresh_old_token_is_consumed(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "consume@test.example")
    _, refresh = await auth_service.issue_tokens(db_session, user.id)
    await auth_service.rotate_refresh(db_session, refresh)  # consume once
    result = await auth_service.rotate_refresh(
        db_session, refresh
    )  # reuse -> must fail
    assert result is None


async def test_rotate_refresh_bogus_token_returns_none(
    db_session: AsyncSession,
) -> None:
    assert await auth_service.rotate_refresh(db_session, "not-a-real-token") is None


# ─── revoke_refresh ────────────────────────────────────────────────────────


async def test_revoke_refresh_invalidates_token(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, "revoke@test.example")
    _, refresh = await auth_service.issue_tokens(db_session, user.id)
    await auth_service.revoke_refresh(db_session, refresh)
    result = await auth_service.rotate_refresh(db_session, refresh)
    assert result is None
