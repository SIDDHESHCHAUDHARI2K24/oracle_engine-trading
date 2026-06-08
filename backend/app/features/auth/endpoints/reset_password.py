"""POST /api/v1/auth/reset-password — Consume password reset token."""

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import account_service
from app.features.auth import repository as auth_repo
from app.features.auth import service as auth_service
from app.features.core.database import get_async_session

router = APIRouter()


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_async_session),
):
    try:
        account_service.validate_password_strength(body.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_PASSWORD",
                "message": str(e),
            },
        )

    user = await auth_repo.get_user_by_email(db, body.email)
    if (
        user is None
        or user.reset_token_hash is None
        or user.reset_token_expires_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_RESET_TOKEN",
                "message": "Invalid or expired reset token",
            },
        )

    if user.reset_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_RESET_TOKEN",
                "message": "Invalid or expired reset token",
            },
        )

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    if token_hash != user.reset_token_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_RESET_TOKEN",
                "message": "Invalid or expired reset token",
            },
        )

    user.hashed_password = auth_service.ph.hash(body.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    await auth_repo.delete_all_sessions(db, user.id)
    await db.flush()

    return {"detail": "Password reset successfully"}
