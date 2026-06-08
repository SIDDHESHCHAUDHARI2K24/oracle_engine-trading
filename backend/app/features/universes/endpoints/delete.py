"""DELETE /api/v1/universes/{universe_id} — admin-only soft-delete."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.auth.models import User
from app.features.core.database import get_async_session
from app.features.universes import service as universes_service


async def delete_universe(
    universe_id: uuid.UUID,
    _admin: User = Depends(requires_role(["admin"])),
    db: AsyncSession = Depends(get_async_session),
) -> dict:
    try:
        await universes_service.soft_delete_universe(db, universe_id)
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
    return {"detail": "ok"}
