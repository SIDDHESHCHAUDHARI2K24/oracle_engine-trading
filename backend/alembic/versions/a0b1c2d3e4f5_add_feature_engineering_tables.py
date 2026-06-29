"""add_feature_engineering_tables

Revision ID: a0b1c2d3e4f5
Revises: 9b2c3d4e5f6c
Create Date: 2026-06-28 21:48:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "9b2c3d4e5f6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_matrix",
        sa.Column(
            "ticker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bar_date", sa.Date(), nullable=False),
        # 5 raw
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        # 19 technical
        sa.Column("returns_1d", sa.Numeric(18, 8), nullable=True),
        sa.Column("returns_5d", sa.Numeric(18, 8), nullable=True),
        sa.Column("returns_10d", sa.Numeric(18, 8), nullable=True),
        sa.Column("returns_20d", sa.Numeric(18, 8), nullable=True),
        sa.Column("rsi_14", sa.Numeric(18, 6), nullable=True),
        sa.Column("macd", sa.Numeric(18, 8), nullable=True),
        sa.Column("macd_signal", sa.Numeric(18, 8), nullable=True),
        sa.Column("macd_hist", sa.Numeric(18, 8), nullable=True),
        sa.Column("bb_upper", sa.Numeric(18, 6), nullable=True),
        sa.Column("bb_middle", sa.Numeric(18, 6), nullable=True),
        sa.Column("bb_lower", sa.Numeric(18, 6), nullable=True),
        sa.Column("bb_width", sa.Numeric(18, 8), nullable=True),
        sa.Column("atr_14", sa.Numeric(18, 6), nullable=True),
        sa.Column("volatility_20d", sa.Numeric(18, 8), nullable=True),
        sa.Column("volume_z_score", sa.Numeric(18, 8), nullable=True),
        sa.Column("sma_50", sa.Numeric(18, 6), nullable=True),
        sa.Column("sma_200", sa.Numeric(18, 6), nullable=True),
        sa.Column("price_to_sma50", sa.Numeric(18, 8), nullable=True),
        sa.Column("price_to_sma200", sa.Numeric(18, 8), nullable=True),
        # 7 macro
        sa.Column("fed_funds_rate", sa.Numeric(18, 6), nullable=True),
        sa.Column("cpi", sa.Numeric(18, 6), nullable=True),
        sa.Column("unemployment", sa.Numeric(18, 6), nullable=True),
        sa.Column("gdp", sa.Numeric(18, 6), nullable=True),
        sa.Column("yield_spread_10y_2y", sa.Numeric(18, 6), nullable=True),
        sa.Column("vix", sa.Numeric(18, 6), nullable=True),
        sa.Column("high_yield_spread", sa.Numeric(18, 6), nullable=True),
        # 4 targets
        sa.Column("target_t1", sa.Numeric(18, 8), nullable=True),
        sa.Column("target_t5", sa.Numeric(18, 8), nullable=True),
        sa.Column("target_t10", sa.Numeric(18, 8), nullable=True),
        sa.Column("target_t15", sa.Numeric(18, 8), nullable=True),
        # metadata
        sa.Column(
            "feature_schema_version",
            sa.String(length=16),
            nullable=False,
            server_default="'v1.0'",
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint(
            "ticker_id", "bar_date", "feature_schema_version",
            name="pk_feature_matrix",
        ),
    )

    op.create_table(
        "normalization_stats",
        sa.Column(
            "ticker_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tickers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("feature_name", sa.String(length=64), nullable=False),
        sa.Column("rolling_mean", sa.Numeric(18, 8), nullable=False),
        sa.Column("rolling_std", sa.Numeric(18, 8), nullable=False),
        sa.PrimaryKeyConstraint(
            "ticker_id", "bar_date", "feature_name",
            name="pk_normalization_stats",
        ),
    )

    op.create_index(
        "ix_feature_matrix_ticker_date",
        "feature_matrix",
        ["ticker_id", sa.text("bar_date DESC")],
    )
    op.create_index(
        "ix_normalization_stats_ticker_date",
        "normalization_stats",
        ["ticker_id", "bar_date"],
    )

    op.execute(
        "SELECT create_hypertable('feature_matrix', 'bar_date', if_not_exists => TRUE);"
    )
    op.execute(
        "SELECT create_hypertable('normalization_stats', 'bar_date', if_not_exists => TRUE);"
    )
    op.execute(
        "SELECT set_chunk_time_interval('feature_matrix', INTERVAL '1 month');"
    )
    op.execute(
        "SELECT set_chunk_time_interval('normalization_stats', INTERVAL '1 month');"
    )


def downgrade() -> None:
    op.drop_table("normalization_stats")
    op.drop_table("feature_matrix")
