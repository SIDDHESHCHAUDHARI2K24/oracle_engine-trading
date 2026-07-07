"""Data ingestion persistence layer.

Handles bulk upserts for OHLCV bars and macro observations into
TimescaleDB hypertables, plus IngestRun lifecycle management.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IngestRun, MacroObservation, OHLCVBar


async def bulk_upsert_ohlcv(
    session: AsyncSession,
    records: list[dict],
    ingest_run_id: uuid.UUID,
    source: str,
) -> int:
    """Bulk upsert OHLCV rows. Returns count of rows inserted/updated.

    Uses INSERT ... ON CONFLICT (ticker_id, bar_date) DO UPDATE so
    backfills are resumable — re-running the same date range is idempotent.
    """
    if not records:
        return 0

    enriched = []
    now = datetime.now(timezone.utc)
    for r in records:
        enriched.append({
            "ticker_id": r["ticker_id"],
            "bar_date": r["bar_date"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "adjusted_close": r.get("adjusted_close"),
            "volume": r["volume"],
            "source": source,
            "ingest_run_id": ingest_run_id,
            "created_at": now,
        })

    stmt = insert(OHLCVBar).values(enriched)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker_id", "bar_date"],
        set_={
            "open": stmt.excluded.open,
            "high": stmt.excluded.high,
            "low": stmt.excluded.low,
            "close": stmt.excluded.close,
            "adjusted_close": stmt.excluded.adjusted_close,
            "volume": stmt.excluded.volume,
            "source": stmt.excluded.source,
            "ingest_run_id": stmt.excluded.ingest_run_id,
        },
    )

    await session.execute(stmt)
    await session.flush()
    return len(enriched)


async def bulk_upsert_macro(
    session: AsyncSession,
    records: list[dict],
    ingest_run_id: uuid.UUID,
    source: str = "fred",
) -> int:
    """Bulk upsert macro observation rows. Returns count inserted/updated.

    Uses INSERT ... ON CONFLICT (series_name, observed_date) DO UPDATE.
    """
    if not records:
        return 0

    enriched = []
    now = datetime.now(timezone.utc)
    for r in records:
        enriched.append({
            "series_name": r["series_name"],
            "observed_date": r["observed_date"],
            "value": r["value"],
            "source": source,
            "is_forward_filled": r.get("is_forward_filled", False),
            "ingest_run_id": ingest_run_id,
            "created_at": now,
        })

    stmt = insert(MacroObservation).values(enriched)
    stmt = stmt.on_conflict_do_update(
        index_elements=["series_name", "observed_date"],
        set_={
            "value": stmt.excluded.value,
            "source": stmt.excluded.source,
            "is_forward_filled": stmt.excluded.is_forward_filled,
            "ingest_run_id": stmt.excluded.ingest_run_id,
        },
    )

    await session.execute(stmt)
    await session.flush()
    return len(enriched)


async def get_latest_bar_date(
    session: AsyncSession, ticker_id: uuid.UUID
) -> date | None:
    """Return the most recent bar date for a ticker, or None."""
    stmt = (
        select(func.max(OHLCVBar.bar_date))
        .where(OHLCVBar.ticker_id == ticker_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_bar_dates(
    session: AsyncSession, ticker_ids: list[uuid.UUID]
) -> dict[uuid.UUID, date]:
    """Return the latest bar date per ticker. Drives incremental fetching."""
    if not ticker_ids:
        return {}

    stmt = (
        select(OHLCVBar.ticker_id, func.max(OHLCVBar.bar_date))
        .where(OHLCVBar.ticker_id.in_(ticker_ids))
        .group_by(OHLCVBar.ticker_id)
    )
    result = await session.execute(stmt)
    return {row[0]: row[1] for row in result.fetchall()}


async def get_present_bar_dates(
    session: AsyncSession, ticker_id: uuid.UUID
) -> set[date]:
    """Return all bar dates present in the database for a ticker."""
    stmt = select(OHLCVBar.bar_date).where(OHLCVBar.ticker_id == ticker_id)
    result = await session.execute(stmt)
    return {row[0] for row in result.fetchall()}


async def get_bars_in_range(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    start: date,
    end: date,
) -> list[OHLCVBar]:
    """Return OHLCV bars for a ticker within a date range, sorted by date."""
    stmt = (
        select(OHLCVBar)
        .where(
            OHLCVBar.ticker_id == ticker_id,
            OHLCVBar.bar_date >= start,
            OHLCVBar.bar_date <= end,
        )
        .order_by(OHLCVBar.bar_date)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ── IngestRun lifecycle ────────────────────────────────────────────


async def create_ingest_run(
    session: AsyncSession,
    triggered_by: str = "on_demand",
) -> IngestRun:
    """Create a new IngestRun in 'running' status and return it."""
    run = IngestRun(
        triggered_by=triggered_by,
        triggered_at=datetime.now(timezone.utc),
        status="running",
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_ingest_run(
    session: AsyncSession,
    run: IngestRun,
    status: str,
    ohlcv_rows: int = 0,
    macro_rows: int = 0,
    failed_tickers: list[str] | None = None,
    stale_macro: bool = False,
    error_summary: str | None = None,
) -> IngestRun:
    """Update an IngestRun to its terminal state with run statistics."""
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    run.ohlcv_rows_inserted = ohlcv_rows
    run.macro_rows_inserted = macro_rows
    run.failed_tickers = failed_tickers or []
    run.stale_macro = stale_macro
    run.error_summary = error_summary
    await session.flush()
    return run


async def get_latest_ingest_run(
    session: AsyncSession,
    status: str | None = None,
) -> IngestRun | None:
    """Return the most recent IngestRun, optionally filtered by status."""
    stmt = select(IngestRun).order_by(IngestRun.triggered_at.desc()).limit(1)
    if status:
        stmt = stmt.where(IngestRun.status == status)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
