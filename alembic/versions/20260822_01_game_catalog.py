"""Add the local game catalog and PostgreSQL search indexes.

Revision ID: 20260822_01
Revises: 20260822_00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260822_01"
down_revision: str | None = "20260822_00"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str):
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        enum_type = postgresql.ENUM(*values, name=name, create_type=False)
        enum_type.create(bind, checkfirst=True)
        return enum_type
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    id_type = sa.Integer() if bind.dialect.name == "sqlite" else sa.BigInteger()
    game_name_type = _enum(
        "game_name_type",
        "PRIMARY",
        "LOCALIZED",
        "ALTERNATIVE",
        "STEAM",
        "ALIAS",
    )
    external_source = _enum("game_external_source", "STEAM", "PSN", "XBOX", "EPIC", "GOG", "NINTENDO")
    image_type = _enum("game_image_type", "COVER", "ARTWORK", "SCREENSHOT")

    op.create_table(
        "games",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("igdb_id", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("korean_name", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("storyline", sa.Text(), nullable=True),
        sa.Column("first_release_date", sa.Date(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_games_igdb_id", "games", ["igdb_id"], unique=True)
    op.create_index("ix_games_slug", "games", ["slug"], unique=False)

    op.create_table(
        "game_names",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("language", sa.String(16), nullable=False, server_default="und"),
        sa.Column("type", game_name_type, nullable=False),
        sa.UniqueConstraint(
            "game_id",
            "normalized_name",
            "language",
            "type",
            name="uq_game_names_identity",
        ),
    )
    op.create_index("ix_game_names_normalized_name", "game_names", ["normalized_name"])
    if bind.dialect.name == "postgresql":
        op.create_index(
            "ix_game_names_normalized_name_pattern",
            "game_names",
            ["normalized_name"],
            postgresql_ops={"normalized_name": "text_pattern_ops"},
        )
        op.create_index(
            "ix_game_names_normalized_name_trgm",
            "game_names",
            ["normalized_name"],
            postgresql_using="gin",
            postgresql_ops={"normalized_name": "gin_trgm_ops"},
        )

    op.create_table(
        "platforms",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("igdb_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("abbreviation", sa.String(64), nullable=True),
    )
    op.create_index("ix_platforms_igdb_id", "platforms", ["igdb_id"], unique=True)
    op.create_table(
        "genres",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("igdb_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_index("ix_genres_igdb_id", "genres", ["igdb_id"], unique=True)
    op.create_table(
        "companies",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("igdb_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_index("ix_companies_igdb_id", "companies", ["igdb_id"], unique=True)
    op.create_table(
        "game_platforms",
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "platform_id",
            id_type,
            sa.ForeignKey("platforms.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "game_genres",
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", id_type, sa.ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "game_companies",
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "company_id",
            id_type,
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("developer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publisher", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "game_external_ids",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", external_source, nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.UniqueConstraint("source", "external_id", name="uq_game_external_ids_source_value"),
    )
    op.create_table(
        "game_images",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("game_id", id_type, sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", image_type, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.UniqueConstraint("game_id", "type", "url", name="uq_game_images_identity"),
    )
    op.create_table(
        "sync_states",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(64), nullable=False, unique=True),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("last_processed_id", sa.BigInteger(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("sync_states")
    op.drop_table("game_images")
    op.drop_table("game_external_ids")
    op.drop_table("game_companies")
    op.drop_table("game_genres")
    op.drop_table("game_platforms")
    op.drop_index("ix_companies_igdb_id", table_name="companies")
    op.drop_table("companies")
    op.drop_index("ix_genres_igdb_id", table_name="genres")
    op.drop_table("genres")
    op.drop_index("ix_platforms_igdb_id", table_name="platforms")
    op.drop_table("platforms")
    if bind.dialect.name == "postgresql":
        op.drop_index("ix_game_names_normalized_name_trgm", table_name="game_names")
        op.drop_index("ix_game_names_normalized_name_pattern", table_name="game_names")
    op.drop_index("ix_game_names_normalized_name", table_name="game_names")
    op.drop_table("game_names")
    op.drop_index("ix_games_slug", table_name="games")
    op.drop_index("ix_games_igdb_id", table_name="games")
    op.drop_table("games")

    if bind.dialect.name == "postgresql":
        for enum_name in ("game_image_type", "game_external_source", "game_name_type"):
            postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
