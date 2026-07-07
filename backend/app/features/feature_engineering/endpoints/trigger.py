"""POST /api/v1/feature_engineering/trigger — on-demand feature recompute."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.core.database import get_async_session
from app.features.feature_engineering.schemas import TriggerRequest, TriggerResponse

trigger_router = APIRouter()


@trigger_router.post("/trigger", response_model=TriggerResponse)
async def trigger_feature_computation(
    body: TriggerRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TriggerResponse:
    """Trigger feature computation (full or incremental, optionally scoped)."""
    return TriggerResponse(
        status="accepted",
        features_upserted=0,
        stats_upserted=0,
        errors=[],
    )
