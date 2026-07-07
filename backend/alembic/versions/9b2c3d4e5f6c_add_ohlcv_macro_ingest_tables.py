"""add_ohlcv_macro_ingest_tables

Revision ID: 9b2c3d4e5f6c
Revises: 8a1c2d3e4f5b
Create Date: 2026-06-07 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9b2c3d4e5f6c"
down_revision: Union[str, Sequence[str], None] = "8a1c2d3e4f5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("triggered_by", sa.String(length=32), nullable=False),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="'running'",
        ),
        sa.Column(
            "ohlcv_rows_inserted",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "macro_rows_inserted",
            sa.Integer(),
            server_default="0",
        ),
        sa.Column(
            "failed_tickers",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "stale_macro",
            sa.Boolean(),
            server_default="false",
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=True,
        ),
    )

    op.create_table(
        "ohlcv_bars",
        sa.Column(
            "ticker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(18, 6), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "ingest_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("ticker_id", "bar_date", name="pk_ohlcv_bars"),
    )

    op.create_table(
        "macro_observations",
        sa.Column("series_name", sa.String(length=64), nullable=False),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default="'fred'",
        ),
        sa.Column(
            "is_forward_filled",
            sa.Boolean(),
            server_default="false",
        ),
        sa.Column(
            "ingest_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingest_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "series_name", "observed_date", name="pk_macro_observations"
        ),
    )

    op.create_index(
        "ix_ohlcv_bars_ticker_date",
        "ohlcv_bars",
        ["ticker_id", sa.text("bar_date DESC")],
    )
    op.create_index(
        "ix_macro_observations_series_date",
        "macro_observations",
        ["series_name", "observed_date"],
    )
    op.create_index(
        "ix_ingest_runs_triggered_at",
        "ingest_runs",
        [sa.text("triggered_at DESC")],
    )

    op.execute(
        "SELECT create_hypertable('ohlcv_bars', 'bar_date', if_not_exists => TRUE);"
    )
    op.execute(
        "SELECT create_hypertable('macro_observations', 'observed_date', if_not_exists => TRUE);"
    )

    op.execute("SELECT set_chunk_time_interval('ohlcv_bars', INTERVAL '1 month');")
    op.execute(
        "SELECT set_chunk_time_interval('macro_observations', INTERVAL '1 month');"
    )


def downgrade() -> None:
    op.drop_table("ohlcv_bars")
    op.drop_table("macro_observations")
    op.drop_table("ingest_runs")
