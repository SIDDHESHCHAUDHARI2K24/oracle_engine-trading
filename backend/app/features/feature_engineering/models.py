"""SQLAlchemy ORM models for the feature_engineering feature.

Tables: feature_matrix (TimescaleDB hypertable), normalization_stats (TimescaleDB hypertable).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.features.core.base import Base


class FeatureMatrix(Base):
    __tablename__ = "feature_matrix"

    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    bar_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 5 raw
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 19 technical
    returns_1d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    returns_5d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    returns_10d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    returns_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    rsi_14: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    macd_signal: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    macd_hist: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    bb_upper: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    bb_middle: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    bb_lower: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    bb_width: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    atr_14: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volatility_20d: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    volume_z_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    sma_50: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    sma_200: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_to_sma50: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    price_to_sma200: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # 7 macro
    fed_funds_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cpi: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    unemployment: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    gdp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    yield_spread_10y_2y: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    vix: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    high_yield_spread: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    # 4 targets
    target_t1: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    target_t5: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    target_t10: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    target_t15: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # metadata
    feature_schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="v1.0"
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "ticker_id", "bar_date", "feature_schema_version",
            name="pk_feature_matrix",
        ),
    )


class NormalizationStats(Base):
    __tablename__ = "normalization_stats"

    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    bar_date: Mapped[date] = mapped_column(Date, nullable=False)
    feature_name: Mapped[str] = mapped_column(String(64), nullable=False)
    rolling_mean: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    rolling_std: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "ticker_id", "bar_date", "feature_name",
            name="pk_normalization_stats",
        ),
    )
