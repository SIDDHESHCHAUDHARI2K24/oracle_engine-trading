import logging

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth import service as auth_service
from app.features.core.database import get_async_session

logger = logging.getLogger("mbi.auth")


async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_async_session),
):
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await auth_service.revoke_refresh(db, refresh_token)
    response.delete_cookie("refresh_token")
    logger.info("logout")
    return {"status": "ok"}
