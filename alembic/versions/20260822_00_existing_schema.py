"""Baseline the existing application schema.

Revision ID: 20260822_00
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260822_00"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    unit_type = sa.Enum("INDIVIDUAL", "TEAM", name="unittype")
    room_status = sa.Enum("RECRUITING", "COMPLETED", "CANCELLED", name="roomstatus")

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("profile_image", sa.String(), nullable=True),
        sa.Column("fcm_token", sa.String(), nullable=True),
        sa.Column("preferred_games", sa.JSON(), nullable=True),
    )
    op.create_table(
        "groups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id"), nullable=False),
        sa.Column("host_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("game_name", sa.String(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("unit_type", unit_type, nullable=True),
        sa.Column("status", room_status, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "group_members",
        sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("groups.id"), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.BigInteger(), sa.ForeignKey("roles.id"), primary_key=True),
    )
    op.create_table(
        "room_participants",
        sa.Column("room_id", sa.BigInteger(), sa.ForeignKey("rooms.id"), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("room_participants")
    op.drop_table("user_roles")
    op.drop_table("group_members")
    op.drop_table("rooms")
    op.drop_table("roles")
    op.drop_table("groups")
    op.drop_table("users")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="roomstatus").drop(bind, checkfirst=True)
        sa.Enum(name="unittype").drop(bind, checkfirst=True)
