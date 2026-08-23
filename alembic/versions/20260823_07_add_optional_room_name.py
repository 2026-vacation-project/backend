"""Add an optional display name to recruiting rooms.

Revision ID: 20260823_07
Revises: 20260823_06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260823_07"
down_revision: str | None = "20260823_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("name", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("rooms", "name")
