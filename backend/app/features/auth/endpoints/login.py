from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import service as auth_service
from app.features.auth.schemas import LoginRequest, TokenResponse, UserResponse
from app.features.core.database import get_async_session
from app.features.core.limiter import limiter


@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_async_session),
):
    user = await auth_service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
            },
        )

    access_token, refresh_token = await auth_service.issue_tokens(db, user.id)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 30,
    )
    return TokenResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )
