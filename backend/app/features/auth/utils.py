"""Auth-related helper utilities.

Includes password hashing/verification, session token generation,
and a dependency for retrieving the current authenticated user
from a session cookie.
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

import asyncpg
from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext

from app.features.core.dependencies import DbDep

from . import models


pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    """Hash a plain-text password using PBKDF2-SHA256."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plain-text password against a stored PBKDF2-SHA256 hash."""
    return pwd_context.verify(plain_password, password_hash)


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


async def get_current_user(
    request: Request, conn: asyncpg.Connection = DbDep
) -> asyncpg.Record:
    """Return the currently authenticated user based on the session cookie.

    Raises:
        HTTPException(401): if the session is missing, invalid, or expired.
    """
    session_token: Optional[str] = request.cookies.get("session_id")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    await models.ensure_auth_schema(conn)
    session = await models.get_session(conn, session_token=session_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    if session["expires_at"] <= datetime.now(timezone.utc):
        # Expired session; clean it up and reject.
        await models.delete_session(conn, session_token=session_token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    user = await models.get_user_by_email(
        conn, email=(await conn.fetchval("SELECT email FROM users WHERE id = $1", session["user_id"]))
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

