"""add_s1_columns_universes_users

Revision ID: 8a1c2d3e4f5b
Revises: d871d570373e
Create Date: 2026-06-01 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a1c2d3e4f5b"
down_revision: Union[str, Sequence[str], None] = "d871d570373e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "universes", sa.Column("public_id", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "universes",
        sa.Column("last_retrain_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("reset_token_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
    op.drop_column("universes", "last_retrain_at")
    op.drop_column("universes", "public_id")
