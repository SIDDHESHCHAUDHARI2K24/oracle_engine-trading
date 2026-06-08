"""POST /api/v1/universes — admin-only create."""

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.schemas import UniverseCreate, UniverseDetail


async def create_universe(
    body: UniverseCreate,
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> UniverseDetail:
    try:
        universe = await universes_service.create_universe(
            db,
            name=body.name,
            display_name=body.display_name,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "DUPLICATE_UNIVERSE_NAME",
                "message": str(exc),
            },
        )
    await db.commit()
    return UniverseDetail(
        id=universe.id,
        name=universe.name,
        display_name=universe.display_name,
        description=universe.description,
        public_id=universe.public_id,
        last_retrain_at=universe.last_retrain_at,
        is_system_managed=universe.is_system_managed,
        created_at=universe.created_at,
        tickers=[],
        ticker_count=0,
    )
