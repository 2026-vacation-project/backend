"""Remove team-based room recruitment.

Revision ID: 20260823_02
Revises: 20260822_01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260823_02"
down_revision: str | None = "20260822_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("rooms") as batch_op:
        batch_op.drop_column("unit_type")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="unittype").drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        unit_type = postgresql.ENUM("INDIVIDUAL", "TEAM", name="unittype")
        unit_type.create(bind, checkfirst=True)
    else:
        unit_type = sa.Enum("INDIVIDUAL", "TEAM", name="unittype")

    with op.batch_alter_table("rooms") as batch_op:
        batch_op.add_column(
            sa.Column(
                "unit_type",
                unit_type,
                nullable=True,
                server_default="INDIVIDUAL",
            )
        )
