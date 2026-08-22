"""Store the public display name supplied by the OAuth provider.

Revision ID: 20260823_06
Revises: 20260823_05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260823_06"
down_revision: str | None = "20260823_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
    op.execute(sa.text("UPDATE users SET display_name = name WHERE display_name IS NULL"))


def downgrade() -> None:
    op.drop_column("users", "display_name")
