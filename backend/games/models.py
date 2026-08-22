from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


id_type = BigInteger().with_variant(Integer, "sqlite")


class GameNameType(str, enum.Enum):
    PRIMARY = "PRIMARY"
    LOCALIZED = "LOCALIZED"
    ALTERNATIVE = "ALTERNATIVE"
    STEAM = "STEAM"
    ALIAS = "ALIAS"


class GameExternalSource(str, enum.Enum):
    STEAM = "STEAM"
    PSN = "PSN"
    XBOX = "XBOX"
    EPIC = "EPIC"
    GOG = "GOG"
    NINTENDO = "NINTENDO"


class GameImageType(str, enum.Enum):
    COVER = "COVER"
    ARTWORK = "ARTWORK"
    SCREENSHOT = "SCREENSHOT"


game_platforms = Table(
    "game_platforms",
    Base.metadata,
    Column("game_id", id_type, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "platform_id",
        id_type,
        ForeignKey("platforms.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", id_type, ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", id_type, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    igdb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    slug: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    korean_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    storyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    names: Mapped[list[GameName]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    platforms: Mapped[list[Platform]] = relationship(secondary=game_platforms, back_populates="games")
    genres: Mapped[list[Genre]] = relationship(secondary=game_genres, back_populates="games")
    company_links: Mapped[list[GameCompany]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    external_ids: Mapped[list[GameExternalId]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    images: Mapped[list[GameImage]] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GameName(Base):
    __tablename__ = "game_names"
    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "normalized_name",
            "language",
            "type",
            name="uq_game_names_identity",
        ),
        Index("ix_game_names_normalized_name", "normalized_name"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        id_type,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="und", server_default="und")
    type: Mapped[GameNameType] = mapped_column(
        Enum(GameNameType, name="game_name_type"),
        nullable=False,
    )

    game: Mapped[Game] = relationship(back_populates="names")


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    igdb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(64), nullable=True)

    games: Mapped[list[Game]] = relationship(secondary=game_platforms, back_populates="platforms")


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    igdb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    games: Mapped[list[Game]] = relationship(secondary=game_genres, back_populates="genres")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    igdb_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    game_links: Mapped[list[GameCompany]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class GameCompany(Base):
    __tablename__ = "game_companies"

    game_id: Mapped[int] = mapped_column(
        id_type,
        ForeignKey("games.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        id_type,
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    developer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    publisher: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")

    game: Mapped[Game] = relationship(back_populates="company_links")
    company: Mapped[Company] = relationship(back_populates="game_links")


class GameExternalId(Base):
    __tablename__ = "game_external_ids"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_game_external_ids_source_value"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        id_type,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[GameExternalSource] = mapped_column(
        Enum(GameExternalSource, name="game_external_source"),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    game: Mapped[Game] = relationship(back_populates="external_ids")


class GameImage(Base):
    __tablename__ = "game_images"
    __table_args__ = (
        UniqueConstraint("game_id", "type", "url", name="uq_game_images_identity"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(
        id_type,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[GameImageType] = mapped_column(
        Enum(GameImageType, name="game_image_type"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    game: Mapped[Game] = relationship(back_populates="images")


class SyncState(Base):
    __tablename__ = "sync_states"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_processed_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
