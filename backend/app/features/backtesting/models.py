import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.features.core.base import Base, UUIDPrimaryKey, Timestamped


class BacktestRun(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "backtest_runs"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)
    backtest_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    backtest_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    num_tickers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_strategies: Mapped[int] = mapped_column(Integer, default=4)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class BacktestMetrics(Base, UUIDPrimaryKey):
    __tablename__ = "backtest_metrics"

    backtest_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=False
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickers.id"), nullable=False
    )
    strategy_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(
        Boolean,
        Computed(
            "COALESCE(sharpe_ratio, 0) > 1.5 AND COALESCE(total_trades, 0) >= 10 AND COALESCE(max_drawdown, -999) > -0.40",
            persisted=True,
        ),
        nullable=False,
    )
    equity_curve: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("backtest_run_id", "ticker_id", "strategy_name"),
        Index(
            "idx_metrics_ticker_strategy_time",
            "ticker_id",
            "strategy_name",
            "computed_at",
        ),
        Index("idx_metrics_run_passed", "backtest_run_id", "passed"),
    )
