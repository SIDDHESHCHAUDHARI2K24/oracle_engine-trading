"""User login endpoint."""

from fastapi import HTTPException, Response, status

from app.features.core.dependencies import DbDep

from .. import models, schemas
from ..utils import generate_session_token, hash_password, verify_password


async def login(
    payload: schemas.LoginRequest,
    response: Response,
    conn=DbDep,
) -> schemas.UserOut:
    """Authenticate a user and establish a session via cookie."""
    await models.ensure_auth_schema(conn)

    user = await models.get_user_by_email(conn, email=payload.email)
    if user is None or not verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    session_token = generate_session_token()
    await models.create_session(conn, user_id=user["id"], session_token=session_token)

    # HttpOnly session cookie
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        samesite="lax",
    )

    return schemas.UserOut(
        id=user["id"],
        email=user["email"],
        created_at=user["created_at"],
    )

