import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conviction_tickets.models import ConvictionTicket, FilterRun


async def upsert_tickets(
    session: AsyncSession,
    tickets: list[dict],
) -> int:
    if not tickets:
        return 0

    stmt = (
        pg_insert(ConvictionTicket)
        .values(tickets)
        .on_conflict_do_nothing(
            index_elements=["inference_run_id", "ticker_id", "horizon"]
        )
        .returning(ConvictionTicket.id)
    )
    result = await session.execute(stmt)
    await session.flush()
    rows = result.fetchall()
    return len(rows)


async def create_filter_run(
    session: AsyncSession,
    inference_run_id: uuid.UUID,
    backtest_run_id: uuid.UUID | None,
    num_evaluated: int,
    num_emitted: int,
    config: dict,
) -> FilterRun:
    run = FilterRun(
        inference_run_id=inference_run_id,
        backtest_run_id=backtest_run_id,
        num_predictions_evaluated=num_evaluated,
        num_tickets_emitted=num_emitted,
        filter_config=config,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()
    return run


async def get_tickets_inbox(
    session: AsyncSession,
    universe_id: uuid.UUID | None = None,
    status: str = "TRADABLE",
    limit: int = 100,
    offset: int = 0,
) -> list[ConvictionTicket]:
    stmt = select(ConvictionTicket).where(ConvictionTicket.status == status)
    if universe_id is not None:
        stmt = stmt.where(ConvictionTicket.universe_id == universe_id)
    stmt = stmt.order_by(ConvictionTicket.conviction_score.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_ticket_by_id(
    session: AsyncSession,
    ticket_id: uuid.UUID,
) -> ConvictionTicket | None:
    return await session.get(ConvictionTicket, ticket_id)


async def get_tickets_history(
    session: AsyncSession,
    universe_id: uuid.UUID | None = None,
    outcome: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ConvictionTicket]:
    stmt = select(ConvictionTicket)
    if universe_id is not None:
        stmt = stmt.where(ConvictionTicket.universe_id == universe_id)
    if outcome is not None:
        stmt = stmt.where(ConvictionTicket.outcome == outcome)
    stmt = stmt.order_by(ConvictionTicket.inference_date.desc())
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_ticket_status(
    session: AsyncSession,
    ticket_id: uuid.UUID,
    new_status: str,
    user_notes: str | None = None,
    user_id: uuid.UUID | None = None,
) -> ConvictionTicket | None:
    ticket = await session.get(ConvictionTicket, ticket_id)
    if ticket is None:
        return None
    ticket.status = new_status
    ticket.updated_at = datetime.now(timezone.utc)
    if user_notes is not None:
        ticket.user_notes = user_notes
    if user_id is not None:
        ticket.created_by_user_id = user_id
    await session.flush()
    return ticket


async def get_tickets_for_resolution(
    session: AsyncSession,
    as_of_date: date,
) -> list[ConvictionTicket]:
    stmt = select(ConvictionTicket).where(
        ConvictionTicket.resolution_date <= as_of_date,
        ConvictionTicket.status.in_(["TRADABLE", "REVIEWED", "ACTIONED"]),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
