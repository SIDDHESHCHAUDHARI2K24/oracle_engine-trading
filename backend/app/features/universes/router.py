"""Universes API router — list and detail."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.schemas import UniverseDetail, UniverseListResponse

universes_router = APIRouter(prefix="/api/v1/universes", tags=["universes"])


@universes_router.get("", response_model=UniverseListResponse)
async def list_universes(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UniverseListResponse:
    """List all non-deleted universes. Requires authentication."""
    return await universes_service.list_universes(db)


@universes_router.get("/{universe_id}", response_model=UniverseDetail)
async def get_universe(
    universe_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UniverseDetail:
    """Get universe detail with its active tickers. Requires authentication."""
    detail = await universes_service.get_universe_detail(db, universe_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "UNIVERSE_NOT_FOUND", "message": f"Universe {universe_id} not found"},
        )
    return detail
