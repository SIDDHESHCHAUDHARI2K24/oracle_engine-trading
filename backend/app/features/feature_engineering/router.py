"""Feature engineering API router."""

from fastapi import APIRouter

from app.features.feature_engineering.endpoints.inspect import inspect_router
from app.features.feature_engineering.endpoints.trigger import trigger_router

router = APIRouter(prefix="/api/v1/feature_engineering", tags=["feature_engineering"])
router.include_router(trigger_router)
router.include_router(inspect_router)
