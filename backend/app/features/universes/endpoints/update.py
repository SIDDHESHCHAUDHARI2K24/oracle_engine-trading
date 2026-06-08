"""PATCH /api/v1/universes/{universe_id} — admin-only update."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service
from app.features.universes.schemas import UniverseDetail, UniverseUpdate


async def update_universe(
    universe_id: uuid.UUID,
    body: UniverseUpdate,
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> UniverseDetail:
    try:
        await universes_service.update_universe(
            db,
            universe_id=universe_id,
            name=body.name,
            display_name=body.display_name,
            description=body.description,
        )
    except universes_service.SystemManagedUniverseError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "SYSTEM_MANAGED_UNIVERSE",
                "message": str(exc),
            },
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "UNIVERSE_NOT_FOUND",
                "message": f"Universe {universe_id} not found",
            },
        )

    await db.commit()
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
