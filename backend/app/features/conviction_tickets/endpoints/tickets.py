import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conviction_tickets.repository import (
    get_ticket_by_id,
    get_tickets_history,
    get_tickets_inbox,
)
from app.features.conviction_tickets.schemas import (
    ConvictionTicketResponse,
    TicketListResponse,
)
from app.features.core.database import get_async_session

router = APIRouter()


@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    universe_id: uuid.UUID | None = None,
    horizon: str | None = None,
    min_conviction: float | None = None,
    min_passes: int | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
):
    tickets = await get_tickets_inbox(
        session,
        universe_id=universe_id,
        status="TRADABLE",
        limit=limit,
        offset=offset,
    )

    if horizon:
        tickets = [t for t in tickets if t.horizon == horizon]
    if min_conviction is not None:
        tickets = [t for t in tickets if t.conviction_score >= min_conviction]
    if min_passes is not None:
        tickets = [t for t in tickets if t.backtest_passes >= min_passes]

    return TicketListResponse(tickets=tickets, total=len(tickets))  # type: ignore[arg-type]


@router.get("/{ticket_id}", response_model=ConvictionTicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    ticket = await get_ticket_by_id(session, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "TICKET_NOT_FOUND", "message": "Ticket not found"},
        )
    return ticket


@router.get("/history", response_model=TicketListResponse)
async def ticket_history(
    status: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
):
    tickets = await get_tickets_history(
        session,
        outcome=outcome,
        limit=limit,
        offset=offset,
    )
    if status:
        tickets = [t for t in tickets if t.status == status]
    return TicketListResponse(tickets=tickets, total=len(tickets))  # type: ignore[arg-type]
