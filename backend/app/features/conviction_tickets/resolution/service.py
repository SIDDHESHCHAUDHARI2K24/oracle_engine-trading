from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conviction_tickets.repository import get_tickets_for_resolution
from app.features.data_ingestion.models import OHLCVBar
from app.features.data_ingestion.shared.trading_calendar import (
    is_trading_day,
    trading_days,
)


async def _get_close_price(
    session: AsyncSession,
    ticker_id,
    bar_date: date,
) -> float | None:
    result = await session.execute(
        select(OHLCVBar.close).where(
            OHLCVBar.ticker_id == ticker_id,
            OHLCVBar.bar_date == bar_date,
        )
    )
    row = result.first()
    return float(row[0]) if row else None


async def resolve_tickets(
    session: AsyncSession,
    as_of_date: date | None = None,
) -> dict:
    as_of = as_of_date or date.today()

    tickets = await get_tickets_for_resolution(session, as_of)

    resolved = 0
    expired = 0
    deferred = 0
    errors = 0

    for ticket in tickets:
        try:
            base_close = await _get_close_price(
                session, ticket.ticker_id, ticket.inference_date
            )
            if base_close is None:
                deferred += 1
                continue

            actual_res_date = ticket.resolution_date
            if not is_trading_day(ticket.resolution_date):
                sessions = trading_days(
                    ticket.resolution_date,
                    ticket.resolution_date + timedelta(days=7),
                )
                if sessions:
                    actual_res_date = sessions[0]
                else:
                    deferred += 1
                    continue

            resolution_close = await _get_close_price(
                session, ticket.ticker_id, actual_res_date
            )
            if resolution_close is None:
                deferred += 1
                continue

            actual_return = resolution_close / base_close - 1.0

            if abs(actual_return) < 0.001:
                outcome = "flat"
            elif actual_return > 0:
                outcome = "win"
            else:
                outcome = "loss"

            ticket.actual_return = actual_return
            ticket.outcome = outcome

            if ticket.status == "TRADABLE":
                ticket.status = "EXPIRED"
                expired += 1
            else:
                ticket.status = "RESOLVED"
                resolved += 1

        except Exception:
            errors += 1
            continue

    await session.flush()
    return {
        "resolved": resolved,
        "expired": expired,
        "deferred": deferred,
        "errors": errors,
    }
