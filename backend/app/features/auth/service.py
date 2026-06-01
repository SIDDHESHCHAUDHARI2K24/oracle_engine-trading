"""Auth service — password verification, JWT issuance, session management."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import repository as auth_repo
from app.features.auth.models import User
from app.features.core.config import settings

ph = PasswordHasher()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await auth_repo.get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def issue_tokens(db: AsyncSession, user_id: uuid.UUID) -> tuple[str, str]:
    access = issue_access_token(user_id)
    refresh_raw = secrets.token_urlsafe(32)
    refresh_hash = _hash_token(refresh_raw)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)
    await auth_repo.create_session(db, user_id, refresh_hash, expires)
    return access, refresh_raw


async def rotate_refresh(db: AsyncSession, refresh_token: str) -> tuple[str, str] | None:
    token_hash = _hash_token(refresh_token)
    session = await auth_repo.get_session_by_hash(db, token_hash)
    if session is None or session.expires_at < datetime.now(timezone.utc):
        return None
    await auth_repo.delete_session_by_hash(db, token_hash)
    return await issue_tokens(db, session.user_id)


async def revoke_refresh(db: AsyncSession, refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    await auth_repo.delete_session_by_hash(db, token_hash)
