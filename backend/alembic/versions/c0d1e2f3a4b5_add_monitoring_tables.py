"""add monitoring tables (coverage, drift, alerts)

Revision ID: c0d1e2f3a4b5
Revises: 87167d0fe01e
Create Date: 2026-07-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c0d1e2f3a4b5"
down_revision: str | None = "87167d0fe01e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coverage_metrics",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("universe_id", sa.UUID(), sa.ForeignKey("universes.id"), nullable=False),
        sa.Column("horizon", sa.String(4), nullable=False),
        sa.Column("measurement_date", sa.Date(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("realized_coverage", sa.Numeric(6, 4), nullable=True),
        sa.Column("nominal_coverage", sa.Numeric(4, 2), server_default=sa.text("0.90"), nullable=False),
        sa.Column("num_tickets_resolved", sa.Integer(), nullable=True),
        sa.Column("is_alert", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("universe_id", "horizon", "measurement_date", "window_size"),
    )

    op.create_table(
        "feature_drift_metrics",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("universe_id", sa.UUID(), sa.ForeignKey("universes.id"), nullable=False),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("measurement_date", sa.Date(), nullable=False),
        sa.Column("kl_divergence", sa.Numeric(18, 8), nullable=True),
        sa.Column("threshold_breached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("training_run_id", sa.UUID(), sa.ForeignKey("training_runs.id"), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "system_alerts",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("universe_id", sa.UUID(), sa.ForeignKey("universes.id"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "idx_open_critical_alerts",
        "system_alerts",
        ["resolved_at", "severity"],
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    op.create_index(
        "idx_drift_metrics_universe_date",
        "feature_drift_metrics",
        ["universe_id", "measurement_date"],
    )

    op.create_index(
        "idx_coverage_metrics_universe",
        "coverage_metrics",
        ["universe_id", "horizon", "measurement_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_coverage_metrics_universe", table_name="coverage_metrics")
    op.drop_index("idx_drift_metrics_universe_date", table_name="feature_drift_metrics")
    op.drop_index("idx_open_critical_alerts", table_name="system_alerts")
    op.drop_table("system_alerts")
    op.drop_table("feature_drift_metrics")
    op.drop_table("coverage_metrics")
