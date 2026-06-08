"""Data access layer for the auth feature.

Centralizes all database queries for users and sessions.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import Session, User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create_session(
    db: AsyncSession, user_id: uuid.UUID, refresh_token_hash: str, expires_at
) -> Session:
    session = Session(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
    )
    db.add(session)
    await db.commit()
    return session


async def get_session_by_hash(db: AsyncSession, token_hash: str) -> Session | None:
    result = await db.execute(
        select(Session).where(Session.refresh_token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def delete_session_by_hash(db: AsyncSession, token_hash: str) -> None:
    await db.execute(
        text("DELETE FROM sessions WHERE refresh_token_hash = :hash"),
        {"hash": token_hash},
    )
    await db.commit()


async def list_active_sessions_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Session]:
    result = await db.execute(
        select(Session)
        .where(
            Session.user_id == user_id,
            Session.expires_at > datetime.now(timezone.utc),
        )
        .order_by(Session.created_at.desc())
    )
    return list(result.scalars().all())


async def delete_all_sessions(
    db: AsyncSession, user_id: uuid.UUID, exclude_id: uuid.UUID | None = None
) -> None:
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
    await db.commit()
