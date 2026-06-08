"""Membership management endpoints — add, remove, list members."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.schemas import AddMembersRequest, AddResult, TickerSummary

membership_router = APIRouter(tags=["membership"])


@membership_router.post(
    "/{universe_id}/membership",
    response_model=AddResult,
    status_code=status.HTTP_201_CREATED,
)
async def add_members(
    universe_id: uuid.UUID,
    body: AddMembersRequest,
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> AddResult:
    try:
        result = await universes_service.add_members(db, universe_id, body.symbols)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": str(exc),
            },
        )
    await db.commit()
    return result


@membership_router.delete(
    "/{universe_id}/membership/{ticker_id}",
    status_code=status.HTTP_200_OK,
)
async def remove_member(
    universe_id: uuid.UUID,
    ticker_id: uuid.UUID,
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    try:
        await universes_service.remove_member(db, universe_id, ticker_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "MEMBERSHIP_NOT_FOUND",
                "message": str(exc),
            },
        )
    await db.commit()
    return {"detail": "ok"}


@membership_router.get(
    "/{universe_id}/membership",
    response_model=list[TickerSummary],
)
async def get_members(
    universe_id: uuid.UUID,
    at: date | None = Query(None),
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> list[TickerSummary]:
    try:
        at_dt = datetime(at.year, at.month, at.day, tzinfo=timezone.utc) if at else None
        members = await universes_service.get_members(db, universe_id, at_date=at_dt)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": str(exc),
            },
        )
    return [TickerSummary.model_validate(t) for t in members]
