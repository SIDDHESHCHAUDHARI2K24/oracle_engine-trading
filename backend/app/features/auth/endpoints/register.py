"""User registration endpoint."""

from fastapi import HTTPException, status

from app.features.core.dependencies import DbDep

from .. import models, schemas
from ..utils import hash_password


async def register(
    payload: schemas.RegisterRequest,
    conn=DbDep,
) -> schemas.UserOut:
    """Create a new user account."""
    await models.ensure_auth_schema(conn)

    existing = await models.get_user_by_email(conn, email=payload.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    password_hash = hash_password(payload.password)
    user_row = await models.create_user(
        conn, email=payload.email, password_hash=password_hash
    )
    return schemas.UserOut(
        id=user_row["id"],
        email=user_row["email"],
        created_at=user_row["created_at"],
    )

