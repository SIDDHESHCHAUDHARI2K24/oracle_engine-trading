"""add_backtesting_conviction_tickets_tables

Revision ID: 87167d0fe01e
Revises: b1c2d3e4f5a6
Create Date: 2026-06-30 21:46:37.942595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '87167d0fe01e'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('backtest_runs',
        sa.Column('universe_id', sa.UUID(), nullable=False),
        sa.Column('triggered_by', sa.String(length=50), nullable=False),
        sa.Column('backtest_period_start', sa.Date(), nullable=False),
        sa.Column('backtest_period_end', sa.Date(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('num_tickers', sa.Integer(), nullable=True),
        sa.Column('num_strategies', sa.Integer(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['universe_id'], ['universes.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('backtest_metrics',
        sa.Column('backtest_run_id', sa.UUID(), nullable=False),
        sa.Column('ticker_id', sa.UUID(), nullable=False),
        sa.Column('strategy_name', sa.String(length=50), nullable=False),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('profit_factor', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('equity_curve', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['backtest_run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['ticker_id'], ['tickers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('backtest_run_id', 'ticker_id', 'strategy_name')
    )
    op.execute("""
        ALTER TABLE backtest_metrics ADD COLUMN passed BOOLEAN GENERATED ALWAYS AS (
            COALESCE(sharpe_ratio, 0) > 1.5
            AND COALESCE(total_trades, 0) >= 10
            AND COALESCE(max_drawdown, -999) > -0.40
        ) STORED
    """)
    op.create_index('idx_metrics_run_passed', 'backtest_metrics', ['backtest_run_id', 'passed'], unique=False)
    op.create_index('idx_metrics_ticker_strategy_time', 'backtest_metrics', ['ticker_id', 'strategy_name', 'computed_at'], unique=False)
    op.create_table('conviction_tickets',
        sa.Column('inference_run_id', sa.UUID(), nullable=False),
        sa.Column('ticker_id', sa.UUID(), nullable=False),
        sa.Column('universe_id', sa.UUID(), nullable=False),
        sa.Column('inference_date', sa.Date(), nullable=False),
        sa.Column('horizon', sa.String(length=10), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('predicted_return', sa.Float(), nullable=False),
        sa.Column('conviction_score', sa.Float(), nullable=False),
        sa.Column('conformal_lower', sa.Float(), nullable=False),
        sa.Column('conformal_upper', sa.Float(), nullable=False),
        sa.Column('conformal_alpha', sa.Float(), nullable=False),
        sa.Column('backtest_run_id', sa.UUID(), nullable=True),
        sa.Column('backtest_passes', sa.Integer(), nullable=False),
        sa.Column('backtest_pass_strategies', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('resolution_date', sa.Date(), nullable=False),
        sa.Column('actual_return', sa.Float(), nullable=True),
        sa.Column('outcome', sa.String(length=10), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['backtest_run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['inference_run_id'], ['inference_runs.id'], ),
        sa.ForeignKeyConstraint(['ticker_id'], ['tickers.id'], ),
        sa.ForeignKeyConstraint(['universe_id'], ['universes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('inference_run_id', 'ticker_id', 'horizon')
    )
    op.create_index('idx_tickets_inbox', 'conviction_tickets', ['universe_id', 'status', 'conviction_score'], unique=False)
    op.create_index('idx_tickets_resolution', 'conviction_tickets', ['resolution_date', 'status'], unique=False)
    op.create_index('idx_tickets_ticker_date', 'conviction_tickets', ['ticker_id', 'inference_date'], unique=False)
    op.create_table('filter_runs',
        sa.Column('inference_run_id', sa.UUID(), nullable=False),
        sa.Column('backtest_run_id', sa.UUID(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('num_predictions_evaluated', sa.Integer(), nullable=True),
        sa.Column('num_tickets_emitted', sa.Integer(), nullable=True),
        sa.Column('filter_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.ForeignKeyConstraint(['backtest_run_id'], ['backtest_runs.id'], ),
        sa.ForeignKeyConstraint(['inference_run_id'], ['inference_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('filter_runs')
    op.drop_index('idx_tickets_ticker_date', table_name='conviction_tickets')
    op.drop_index('idx_tickets_resolution', table_name='conviction_tickets')
    op.drop_index('idx_tickets_inbox', table_name='conviction_tickets')
    op.drop_table('conviction_tickets')
    op.drop_index('idx_metrics_ticker_strategy_time', table_name='backtest_metrics')
    op.drop_index('idx_metrics_run_passed', table_name='backtest_metrics')
    op.drop_table('backtest_metrics')
    op.drop_table('backtest_runs')
