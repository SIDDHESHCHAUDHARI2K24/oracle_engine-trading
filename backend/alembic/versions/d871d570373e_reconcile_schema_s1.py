"""reconcile_schema_s1

Revision ID: d871d570373e
Revises: 3ae032551074
Create Date: 2026-06-01 19:31:51.496444

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d871d570373e"
down_revision: Union[str, Sequence[str], None] = "3ae032551074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("sessions", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("ip", sa.String(length=50), nullable=True))
    op.add_column(
        "sessions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "sessions", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("universes", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "full_name")
    op.drop_column("universes", "description")
    op.drop_column("sessions", "updated_at")
    op.drop_column("sessions", "created_at")
    op.drop_column("sessions", "ip")
    op.drop_column("sessions", "user_agent")
    op.drop_column("sessions", "last_used_at")
