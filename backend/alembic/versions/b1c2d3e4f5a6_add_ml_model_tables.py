"""add_ml_model_tables

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-29 00:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "universe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("universes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="'running'"),
        sa.Column("train_window_start", sa.Date(), nullable=True),
        sa.Column("train_window_end", sa.Date(), nullable=True),
        sa.Column("calibration_window_start", sa.Date(), nullable=True),
        sa.Column("calibration_window_end", sa.Date(), nullable=True),
        sa.Column("validation_window_start", sa.Date(), nullable=True),
        sa.Column("validation_window_end", sa.Date(), nullable=True),
        sa.Column("num_tickers", sa.Integer(), nullable=True),
        sa.Column("num_training_samples", sa.BigInteger(), nullable=True),
        sa.Column("hyperparams_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("validation_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("jsonb_build_object()"),
        ),
    )
    op.create_index(
        "ix_training_runs_universe_started",
        "training_runs",
        ["universe_id", sa.text("started_at DESC")],
    )

    op.create_table(
        "model_artifacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "universe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("universes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "training_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_role", sa.String(), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("jsonb_build_object()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_model_artifacts_universe_role_created",
        "model_artifacts",
        ["universe_id", "model_role", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_model_artifacts_active "
        "ON model_artifacts (universe_id, model_role) "
        "WHERE is_active = true"
    )

    op.create_table(
        "inference_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "universe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("universes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_by", sa.String(), nullable=False),
        sa.Column("inference_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="'running'"),
        sa.Column(
            "artifact_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("jsonb_build_array()"),
        ),
        sa.Column("num_tickers_scored", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "predictions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "inference_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inference_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "ticker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "universe_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("universes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("inference_date", sa.Date(), nullable=False),
        # T+1 horizon
        sa.Column("pred_t1", sa.Float(), nullable=False),
        sa.Column("pred_lo_t1", sa.Float(), nullable=False),
        sa.Column("pred_hi_t1", sa.Float(), nullable=False),
        sa.Column("conviction_t1", sa.Float(), nullable=False),
        # T+5 horizon
        sa.Column("pred_t5", sa.Float(), nullable=False),
        sa.Column("pred_lo_t5", sa.Float(), nullable=False),
        sa.Column("pred_hi_t5", sa.Float(), nullable=False),
        sa.Column("conviction_t5", sa.Float(), nullable=False),
        # T+10 horizon
        sa.Column("pred_t10", sa.Float(), nullable=False),
        sa.Column("pred_lo_t10", sa.Float(), nullable=False),
        sa.Column("pred_hi_t10", sa.Float(), nullable=False),
        sa.Column("conviction_t10", sa.Float(), nullable=False),
        # T+15 horizon
        sa.Column("pred_t15", sa.Float(), nullable=False),
        sa.Column("pred_lo_t15", sa.Float(), nullable=False),
        sa.Column("pred_hi_t15", sa.Float(), nullable=False),
        sa.Column("conviction_t15", sa.Float(), nullable=False),
        # raw component outputs
        sa.Column("lstm_outputs", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("tft_q10", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("tft_q50", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column("tft_q90", postgresql.ARRAY(sa.Float()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", "inference_date", name="pk_predictions"),
        sa.UniqueConstraint(
            "ticker_id", "universe_id", "inference_date",
            name="uq_predictions_ticker_universe_date",
        ),
    )

    op.create_index(
        "ix_predictions_universe_date",
        "predictions",
        ["universe_id", sa.text("inference_date DESC")],
    )
    op.create_index(
        "ix_predictions_ticker_date",
        "predictions",
        ["ticker_id", sa.text("inference_date DESC")],
    )

    # NOTE: predictions is a regular table with a UUID primary key;
    # TimescaleDB hypertables require the partition column in every unique
    # constraint / primary key, which is incompatible with the UUID-only PK.
    # Indexes on (universe_id, inference_date) and (ticker_id, inference_date)
    # provide sufficient query performance for this workload.


def downgrade() -> None:
    op.drop_table("predictions")
    op.drop_table("inference_runs")
    op.drop_table("model_artifacts")
    op.drop_table("training_runs")
