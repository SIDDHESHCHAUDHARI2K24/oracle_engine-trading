"""Feature engineering persistence layer.

Handles bulk upserts for feature_matrix rows and normalization_stats
into TimescaleDB hypertables.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.feature_engineering.models import FeatureMatrix, NormalizationStats


async def bulk_upsert_feature_matrix(
    session: AsyncSession,
    records: list[dict],
    schema_version: str = "v1.0",
) -> int:
    """Bulk upsert feature matrix rows. Returns count inserted/updated.

    Uses INSERT ... ON CONFLICT (ticker_id, bar_date, feature_schema_version)
    DO UPDATE so re-runs are idempotent.
    """
    if not records:
        return 0

    now = datetime.now(timezone.utc)
    enriched = []
    for r in records:
        row = {
            "ticker_id": r["ticker_id"],
            "bar_date": r["bar_date"],
            "feature_schema_version": schema_version,
            "computed_at": now,
        }
        for k, v in r.items():
            if k not in ("ticker_id", "bar_date"):
                row[k] = v
        enriched.append(row)

    stmt = insert(FeatureMatrix).values(enriched)
    update_cols = {}
    for col in FeatureMatrix.__table__.columns:
        col_name = str(col.name)
        if col_name not in ("ticker_id", "bar_date", "feature_schema_version"):
            update_cols[col_name] = getattr(stmt.excluded, col_name)

    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker_id", "bar_date", "feature_schema_version"],
        set_=update_cols,
    )

    await session.execute(stmt)
    await session.flush()
    return len(enriched)


async def bulk_upsert_normalization_stats(
    session: AsyncSession,
    records: list[dict],
) -> int:
    """Bulk upsert normalization stats. Returns count inserted/updated."""
    if not records:
        return 0

    stmt = insert(NormalizationStats).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker_id", "bar_date", "feature_name"],
        set_={
            "rolling_mean": stmt.excluded.rolling_mean,
            "rolling_std": stmt.excluded.rolling_std,
        },
    )

    await session.execute(stmt)
    await session.flush()
    return len(records)


async def get_latest_feature_date(
    session: AsyncSession, ticker_id: uuid.UUID
) -> date | None:
    """Return the most recent bar_date in feature_matrix for a ticker."""
    stmt = select(func.max(FeatureMatrix.bar_date)).where(
        FeatureMatrix.ticker_id == ticker_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_feature_row(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    bar_date: date,
    schema_version: str = "v1.0",
) -> FeatureMatrix | None:
    """Get a single feature matrix row by PK."""
    stmt = select(FeatureMatrix).where(
        FeatureMatrix.ticker_id == ticker_id,
        FeatureMatrix.bar_date == bar_date,
        FeatureMatrix.feature_schema_version == schema_version,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_normalization_stats(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    bar_date: date,
) -> list[NormalizationStats]:
    """Get normalization stats for one (ticker, date)."""
    stmt = select(NormalizationStats).where(
        NormalizationStats.ticker_id == ticker_id,
        NormalizationStats.bar_date == bar_date,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_feature_rows_for_ticker(
    session: AsyncSession,
    ticker_id: uuid.UUID,
    from_date: date | None = None,
) -> int:
    """Delete feature matrix rows for a ticker, optionally from a date."""
    stmt = FeatureMatrix.__table__.delete().where(FeatureMatrix.ticker_id == ticker_id)  # type: ignore[attr-defined]
    if from_date is not None:
        stmt = stmt.where(FeatureMatrix.bar_date >= from_date)
    result = await session.execute(stmt)  # type: ignore[assignment]
    await session.flush()
    return result.rowcount  # type: ignore[attr-defined,union-attr]
