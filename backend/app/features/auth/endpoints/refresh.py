from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import service as auth_service
from app.features.auth.schemas import TokenResponse, UserResponse
from app.features.auth.repository import get_user_by_id
from app.features.core.database import get_async_session


async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "NO_REFRESH_TOKEN",
                "message": "Refresh token missing",
            },
        )

    result = await auth_service.rotate_refresh(db, refresh_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_REFRESH_TOKEN",
                "message": "Invalid or expired refresh token",
            },
        )

    access_token, new_refresh = result
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )

    user_id = auth_service.verify_access_token(access_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_ACCESS_TOKEN",
                "message": "Invalid access token after refresh",
            },
        )
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "USER_NOT_FOUND",
                "message": "User associated with token no longer exists",
            },
        )
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )
