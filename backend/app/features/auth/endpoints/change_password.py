"""POST /api/v1/auth/change-password — Change password endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import account_service
from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.auth.schemas import ChangePasswordRequest
from app.features.core.database import get_async_session
from app.features.core.dependencies import get_request_id

router = APIRouter()


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
    request_id: str = Depends(get_request_id),
):
    try:
        await account_service.change_password(
            db, user.id, request.old_password, request.new_password
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_PASSWORD",
                "message": str(e),
                "details": {},
                "request_id": request_id,
            },
        )
    return {"detail": "Password changed"}
