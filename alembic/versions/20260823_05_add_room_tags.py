"""Connect recruiting rooms to the tags they are looking for.

Revision ID: 20260823_05
Revises: 20260823_04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260823_05"
down_revision: str | None = "20260823_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "room_tags",
        sa.Column("room_id", sa.BigInteger(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("room_tags")
