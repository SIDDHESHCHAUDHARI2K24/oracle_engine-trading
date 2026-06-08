"""POST /api/v1/auth/logout-everywhere — Logout everywhere endpoint."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import account_service
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.core.database import get_async_session

router = APIRouter()


@router.post("/logout-everywhere")
async def logout_everywhere(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    await account_service.logout_everywhere(db, user.id)
    response.delete_cookie("refresh_token")
    return {"detail": "ok"}
