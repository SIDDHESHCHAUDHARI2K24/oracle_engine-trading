import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.features.core.base import Base, UUIDPrimaryKey, Timestamped


class ConvictionTicket(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "conviction_tickets"

    inference_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inference_runs.id"), nullable=False
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickers.id"), nullable=False
    )
    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=False
    )
    inference_date: Mapped[date] = mapped_column(Date, nullable=False)
    horizon: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), default="LONG")
    predicted_return: Mapped[float] = mapped_column(Float, nullable=False)
    conviction_score: Mapped[float] = mapped_column(Float, nullable=False)
    conformal_lower: Mapped[float] = mapped_column(Float, nullable=False)
    conformal_upper: Mapped[float] = mapped_column(Float, nullable=False)
    conformal_alpha: Mapped[float] = mapped_column(Float, default=0.10)
    backtest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=True
    )
    backtest_passes: Mapped[int] = mapped_column(Integer, nullable=False)
    backtest_pass_strategies: Mapped[list] = mapped_column(
        ARRAY(String), default=list
    )
    status: Mapped[str] = mapped_column(String(20), default="TRADABLE")
    resolution_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    user_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("inference_run_id", "ticker_id", "horizon"),
        Index("idx_tickets_inbox", "universe_id", "status", "conviction_score"),
        Index("idx_tickets_resolution", "resolution_date", "status"),
        Index("idx_tickets_ticker_date", "ticker_id", "inference_date"),
    )


class FilterRun(Base, UUIDPrimaryKey):
    __tablename__ = "filter_runs"

    inference_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inference_runs.id"), nullable=False
    )
    backtest_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    num_predictions_evaluated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_tickets_emitted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filter_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
