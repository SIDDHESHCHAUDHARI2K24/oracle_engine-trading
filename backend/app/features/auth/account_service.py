"""Account management service — password changes, session listing, logout."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import repository as auth_repo
from app.features.auth.models import User
from app.features.auth.schemas import SessionInfo
from app.features.auth.service import ph, verify_password


def validate_password_strength(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")


async def _get_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await auth_repo.get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    return user


async def change_password(
    db: AsyncSession,
    user_id: uuid.UUID,
    old_password: str,
    new_password: str,
    current_session_id: uuid.UUID | None = None,
) -> None:
    user = await _get_user(db, user_id)
    if not verify_password(old_password, user.hashed_password):
        raise ValueError("old password is incorrect")
    validate_password_strength(new_password)
    user.hashed_password = ph.hash(new_password)
    await auth_repo.delete_all_sessions(db, user.id, exclude_id=current_session_id)
    await db.flush()


async def list_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_session_id: uuid.UUID | None = None,
) -> list[SessionInfo]:
    sessions = await auth_repo.list_active_sessions_for_user(db, user_id)
    return [
        SessionInfo(
            id=s.id,
            created_at=s.created_at,
            expires_at=s.expires_at,
            last_used_at=s.last_used_at,
            user_agent=s.user_agent,
            ip=s.ip,
            is_current=(s.id == current_session_id),
        )
        for s in sessions
    ]


async def logout_everywhere(
    db: AsyncSession,
    user_id: uuid.UUID,
    keep_current_session_id: uuid.UUID | None = None,
) -> None:
    await auth_repo.delete_all_sessions(db, user_id, exclude_id=keep_current_session_id)
