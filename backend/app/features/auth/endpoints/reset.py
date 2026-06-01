"""Password reset endpoint (no email flow)."""

from fastapi import HTTPException, status

from app.features.core.dependencies import DbDep

from .. import models, schemas
from ..utils import hash_password


class ResetRequest(schemas.RegisterRequest):
    """Request payload for resetting a password using email + new password."""


async def reset_password(
    payload: ResetRequest,
    conn=DbDep,
) -> dict[str, str]:
    """Reset a user's password directly without an email link."""
    await models.ensure_auth_schema(conn)

    new_hash = hash_password(payload.password)
    updated_rows = await models.update_user_password(
        conn, email=payload.email, new_password_hash=new_hash
    )
    if updated_rows == 0:
        # For security, don't reveal whether the email exists.
        return {"detail": "If the account exists, the password was reset"}

    return {"detail": "Password reset"}

