"""FastAPI auth dependencies — JWT verification and role checking."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import repository as auth_repo
from app.features.auth.models import User
from app.features.auth.service import verify_access_token
from app.features.core.database import get_async_session


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "UNAUTHORIZED",
                "message": "Missing or invalid token",
            },
        )
    token = auth_header.removeprefix("Bearer ")
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "UNAUTHORIZED",
                "message": "Invalid or expired token",
            },
        )
    user = await auth_repo.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "UNAUTHORIZED", "message": "User not found"},
        )
    return user


def requires_role(roles: list[str]):
    async def checker(user=Depends(get_current_user)):
        if "admin" in roles and not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "FORBIDDEN", "message": "Admin access required"},
            )
        return user

    return checker
