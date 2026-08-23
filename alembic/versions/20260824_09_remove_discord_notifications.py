"""Remove Discord DM notification state.

Revision ID: 20260824_09
Revises: 20260824_08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_09"
down_revision: str | None = "20260824_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("discord_notification_message_id")
        batch_op.drop_column("discord_notification_channel_id")
        batch_op.drop_column("notifications_enabled")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("discord_notification_channel_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("discord_notification_message_id", sa.String(), nullable=True))

    op.execute(sa.text("UPDATE users SET notifications_enabled = TRUE WHERE fcm_token IS NOT NULL"))
