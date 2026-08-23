"""Add Discord Gateway notification settings.

Revision ID: 20260824_08
Revises: 20260823_07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_08"
down_revision: str | None = "20260823_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("discord_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("discord_notification_channel_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("discord_notification_message_id", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_users_discord_user_id", ["discord_user_id"])

    op.execute(sa.text("UPDATE users SET notifications_enabled = TRUE WHERE fcm_token IS NOT NULL"))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_discord_user_id", type_="unique")
        batch_op.drop_column("discord_notification_message_id")
        batch_op.drop_column("discord_notification_channel_id")
        batch_op.drop_column("discord_user_id")
        batch_op.drop_column("notifications_enabled")
