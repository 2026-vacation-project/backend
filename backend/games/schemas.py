from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class GameSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str | None = None
    cover_url: str | None = None
    first_release_date: date | None = None
    rating: float | None = None
    platforms: list[str] = Field(default_factory=list)
