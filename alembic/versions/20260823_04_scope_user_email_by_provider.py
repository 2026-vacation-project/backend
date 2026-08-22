"""Scope user email uniqueness to each OAuth provider.

Revision ID: 20260823_04
Revises: 20260823_03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260823_04"
down_revision: str | None = "20260823_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "users",
            naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
        ) as batch_op:
            batch_op.drop_constraint("uq_users_email", type_="unique")
    else:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_constraint("users_email_key", type_="unique")

    provider_filter = {
        "postgresql_where": sa.text("id LIKE 'G-%'"),
        "sqlite_where": sa.text("id LIKE 'G-%'"),
    }
    op.create_index(
        "uq_users_google_email",
        "users",
        ["email"],
        unique=True,
        **provider_filter,
    )

    provider_filter = {
        "postgresql_where": sa.text("id LIKE 'D-%'"),
        "sqlite_where": sa.text("id LIKE 'D-%'"),
    }
    op.create_index(
        "uq_users_discord_email",
        "users",
        ["email"],
        unique=True,
        **provider_filter,
    )


def downgrade() -> None:
    op.drop_index("uq_users_discord_email", table_name="users")
    op.drop_index("uq_users_google_email", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_email", ["email"])
