import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.features.core.base import Base, UUIDPrimaryKey


def _utc_now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class CoverageMetric(Base, UUIDPrimaryKey):
    __tablename__ = "coverage_metrics"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=False
    )
    horizon: Mapped[str] = mapped_column(String(4), nullable=False)
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False)
    realized_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    nominal_coverage: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.90, server_default="0.90"
    )
    num_tickets_resolved: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("universe_id", "horizon", "measurement_date", "window_size"),
    )


class FeatureDriftMetric(Base, UUIDPrimaryKey):
    __tablename__ = "feature_drift_metrics"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=False
    )
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    kl_divergence: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold_breached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    training_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_runs.id"), nullable=True
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )


class SystemAlert(Base, UUIDPrimaryKey):
    __tablename__ = "system_alerts"

    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    universe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("universes.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=func.jsonb_build_object()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
