"""Model health API router."""

from fastapi import APIRouter

from app.features.ml_models.endpoints.model_health import model_health_router

router = APIRouter(prefix="/api/v1/model-health", tags=["model_health"])
router.include_router(model_health_router)
