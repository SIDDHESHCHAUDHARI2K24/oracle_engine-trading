import sqlalchemy as sa
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import DateTime, Float, Integer, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.features.core.base import Base, UUIDPrimaryKey


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TrainingRun(Base, UUIDPrimaryKey):
    __tablename__ = "training_runs"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("universes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggered_by: Mapped[str] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(nullable=False, default="running")
    train_window_start: Mapped[date | None] = mapped_column(nullable=True)
    train_window_end: Mapped[date | None] = mapped_column(nullable=True)
    calibration_window_start: Mapped[date | None] = mapped_column(nullable=True)
    calibration_window_end: Mapped[date | None] = mapped_column(nullable=True)
    validation_window_start: Mapped[date | None] = mapped_column(nullable=True)
    validation_window_end: Mapped[date | None] = mapped_column(nullable=True)
    num_tickers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_training_samples: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hyperparams_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(nullable=True)
    model_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.jsonb_build_object(),
    )


class ModelArtifact(Base, UUIDPrimaryKey):
    __tablename__ = "model_artifacts"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("universes.id", ondelete="CASCADE"),
        nullable=False,
    )
    training_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("training_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_role: Mapped[str] = mapped_column(nullable=False)
    artifact_path: Mapped[str] = mapped_column(nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=False)
    model_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=func.jsonb_build_object(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InferenceRun(Base, UUIDPrimaryKey):
    __tablename__ = "inference_runs"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("universes.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_by: Mapped[str] = mapped_column(nullable=False)
    inference_date: Mapped[date] = mapped_column(nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(nullable=False, default="running")
    artifact_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=func.jsonb_build_array()
    )
    num_tickers_scored: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    inference_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("inference_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("universes.id", ondelete="CASCADE"),
        nullable=False,
    )
    inference_date: Mapped[date] = mapped_column(nullable=False)

    pred_t1: Mapped[float] = mapped_column(Float, nullable=False)
    pred_lo_t1: Mapped[float] = mapped_column(Float, nullable=False)
    pred_hi_t1: Mapped[float] = mapped_column(Float, nullable=False)
    conviction_t1: Mapped[float] = mapped_column(Float, nullable=False)

    pred_t5: Mapped[float] = mapped_column(Float, nullable=False)
    pred_lo_t5: Mapped[float] = mapped_column(Float, nullable=False)
    pred_hi_t5: Mapped[float] = mapped_column(Float, nullable=False)
    conviction_t5: Mapped[float] = mapped_column(Float, nullable=False)

    pred_t10: Mapped[float] = mapped_column(Float, nullable=False)
    pred_lo_t10: Mapped[float] = mapped_column(Float, nullable=False)
    pred_hi_t10: Mapped[float] = mapped_column(Float, nullable=False)
    conviction_t10: Mapped[float] = mapped_column(Float, nullable=False)

    pred_t15: Mapped[float] = mapped_column(Float, nullable=False)
    pred_lo_t15: Mapped[float] = mapped_column(Float, nullable=False)
    pred_hi_t15: Mapped[float] = mapped_column(Float, nullable=False)
    conviction_t15: Mapped[float] = mapped_column(Float, nullable=False)

    lstm_outputs: Mapped[list] = mapped_column(ARRAY(Float), nullable=False)
    tft_q10: Mapped[list] = mapped_column(ARRAY(Float), nullable=False)
    tft_q50: Mapped[list] = mapped_column(ARRAY(Float), nullable=False)
    tft_q90: Mapped[list] = mapped_column(ARRAY(Float), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        server_default=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", "inference_date", name="pk_predictions"),
        UniqueConstraint(
            "ticker_id",
            "universe_id",
            "inference_date",
            name="uq_predictions_ticker_universe_date",
        ),
    )
