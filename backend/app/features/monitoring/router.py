from fastapi import APIRouter

from app.features.monitoring.endpoints.monitoring import router as monitoring_router

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])
router.include_router(monitoring_router)
