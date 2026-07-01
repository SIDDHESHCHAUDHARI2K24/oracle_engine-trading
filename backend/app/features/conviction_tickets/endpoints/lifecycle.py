import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.dependencies import requires_role
from app.features.conviction_tickets.repository import get_ticket_by_id, update_ticket_status
from app.features.conviction_tickets.schemas import (
    LifecycleRequest,
    TicketActionResponse,
)
from app.features.core.database import get_async_session

router = APIRouter()

VALID_TRANSITIONS = {
    "TRADABLE": {"REVIEWED", "ACTIONED"},
    "REVIEWED": {"ACTIONED"},
    "ACTIONED": set(),
    "RESOLVED": set(),
    "EXPIRED": set(),
}


@router.post("/{ticket_id}/review", response_model=TicketActionResponse)
async def mark_reviewed(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(requires_role(["admin"])),
):
    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "TICKET_NOT_FOUND", "message": "Ticket not found"},
        )
    if ticket.status != "TRADABLE":
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_TRANSITION",
                "message": f"Cannot transition from {ticket.status} to REVIEWED",
            },
        )
    updated = await update_ticket_status(session, ticket_id, "REVIEWED")
    return {"message": "Ticket marked as reviewed", "ticket": updated}


@router.post("/{ticket_id}/action", response_model=TicketActionResponse)
async def mark_actioned(
    ticket_id: uuid.UUID,
    request: LifecycleRequest,
    session: AsyncSession = Depends(get_async_session),
    _=Depends(requires_role(["admin"])),
):
    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "TICKET_NOT_FOUND", "message": "Ticket not found"},
        )
    if ticket.status not in ("TRADABLE", "REVIEWED"):
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_TRANSITION",
                "message": f"Cannot transition from {ticket.status} to ACTIONED",
            },
        )
    updated = await update_ticket_status(session, ticket_id, "ACTIONED", request.notes)
    return {"message": "Ticket marked as actioned", "ticket": updated}
