from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IGDBGamePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    slug: str | None = None
    summary: str | None = None
    storyline: str | None = None
    first_release_date: int | None = None
    rating: float | None = None
    alternative_names: list[dict[str, Any]] = Field(default_factory=list)
    game_localizations: list[dict[str, Any]] = Field(default_factory=list)
    platforms: list[dict[str, Any]] = Field(default_factory=list)
    genres: list[dict[str, Any]] = Field(default_factory=list)
    involved_companies: list[dict[str, Any]] = Field(default_factory=list)
    cover: dict[str, Any] | None = None
    artworks: list[dict[str, Any]] = Field(default_factory=list)
    screenshots: list[dict[str, Any]] = Field(default_factory=list)
    external_games: list[dict[str, Any]] = Field(default_factory=list)
