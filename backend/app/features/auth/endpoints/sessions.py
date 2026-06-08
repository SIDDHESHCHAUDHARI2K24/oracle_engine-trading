"""GET /api/v1/auth/sessions — List active sessions endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import account_service
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.core.database import get_async_session

router = APIRouter()


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    return await account_service.list_sessions(db, user.id)
