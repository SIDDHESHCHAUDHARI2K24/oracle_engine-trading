from fastapi import APIRouter

from app.features.conviction_tickets.endpoints.lifecycle import (
    router as lifecycle_router,
)
from app.features.conviction_tickets.endpoints.tickets import router as tickets_router

router = APIRouter(prefix="/api/v1/tickets", tags=["conviction_tickets"])
router.include_router(tickets_router)
router.include_router(lifecycle_router)
