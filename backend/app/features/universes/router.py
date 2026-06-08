"""Universes API router — list, detail, create, update, delete."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import get_current_user
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.endpoints.create import create_universe
from app.features.universes.endpoints.delete import delete_universe
from app.features.universes.endpoints.import_membership import import_membership_router
from app.features.universes.endpoints.membership import membership_router
from app.features.universes.endpoints.update import update_universe
from app.features.universes.schemas import UniverseDetail, UniverseListResponse

universes_router = APIRouter(prefix="/api/v1/universes", tags=["universes"])


@universes_router.get("", response_model=UniverseListResponse)
async def list_universes(
    include_deleted: bool = Query(False),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
) -> UniverseListResponse:
    """List universes. Pass ?include_deleted=true to include soft-deleted."""
    return await universes_service.list_universes(db, include_deleted=include_deleted)


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
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": f"Universe {universe_id} not found",
            },
        )
    return detail


universes_router.post(
    "", response_model=UniverseDetail, status_code=status.HTTP_201_CREATED
)(create_universe)
universes_router.patch(
    "/{universe_id}", response_model=UniverseDetail
)(update_universe)
universes_router.delete("/{universe_id}", status_code=status.HTTP_200_OK)(
    delete_universe
)

universes_router.include_router(membership_router)
universes_router.include_router(import_membership_router)
