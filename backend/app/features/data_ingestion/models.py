"""SQLAlchemy ORM models for the data_ingestion feature.

Tables: ohlcv_bars (TimescaleDB hypertable), macro_observations (TimescaleDB hypertable),
ingest_runs (plain table).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.features.core.base import Base, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.features.universes.models import Ticker


class OHLCVBar(Base):
    __tablename__ = "ohlcv_bars"

    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    bar_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    ingest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    ticker: Mapped["Ticker"] = relationship("Ticker")  # type: ignore[type-arg]
    ingest_run: Mapped["IngestRun | None"] = relationship(
        "IngestRun", back_populates="ohlcv_bars"
    )

    __table_args__ = (
        PrimaryKeyConstraint("ticker_id", "bar_date", name="pk_ohlcv_bars"),
    )


class MacroObservation(Base):
    __tablename__ = "macro_observations"

    series_name: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), default="fred", server_default="'fred'"
    )
    is_forward_filled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    ingest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingest_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    ingest_run: Mapped["IngestRun | None"] = relationship(
        "IngestRun", back_populates="macro_observations"
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "series_name", "observed_date", name="pk_macro_observations"
        ),
    )


class IngestRun(Base, UUIDPrimaryKey):
    __tablename__ = "ingest_runs"

    triggered_by: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="running", server_default="'running'"
    )
    ohlcv_rows_inserted: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    macro_rows_inserted: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    failed_tickers: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    stale_macro: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=dict, nullable=True
    )

    ohlcv_bars: Mapped[list["OHLCVBar"]] = relationship(
        "OHLCVBar", back_populates="ingest_run"
    )
    macro_observations: Mapped[list["MacroObservation"]] = relationship(
        "MacroObservation", back_populates="ingest_run"
    )
