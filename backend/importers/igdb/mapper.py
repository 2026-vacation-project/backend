from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from games.models import GameExternalSource, GameImageType, GameNameType
from games.normalization import normalize_game_name
from integrations.igdb.schemas import IGDBGamePayload


IMAGE_URL = "https://images.igdb.com/igdb/image/upload/{size}/{image_id}.jpg"


@dataclass(frozen=True)
class MappedName:
    name: str
    normalized_name: str
    language: str
    type: GameNameType


@dataclass(frozen=True)
class MappedPlatform:
    igdb_id: int
    name: str
    abbreviation: str | None


@dataclass(frozen=True)
class MappedGenre:
    igdb_id: int
    name: str


@dataclass(frozen=True)
class MappedCompany:
    igdb_id: int
    name: str
    developer: bool
    publisher: bool


@dataclass(frozen=True)
class MappedExternalId:
    source: GameExternalSource
    external_id: str


@dataclass(frozen=True)
class MappedImage:
    type: GameImageType
    url: str
    width: int | None
    height: int | None


@dataclass
class MappedGame:
    igdb_id: int
    slug: str | None
    name: str
    korean_name: str | None
    summary: str | None
    storyline: str | None
    first_release_date: date | None
    rating: float | None
    names: list[MappedName] = field(default_factory=list)
    platforms: list[MappedPlatform] = field(default_factory=list)
    genres: list[MappedGenre] = field(default_factory=list)
    companies: list[MappedCompany] = field(default_factory=list)
    external_ids: list[MappedExternalId] = field(default_factory=list)
    images: list[MappedImage] = field(default_factory=list)


def map_game(payload: dict[str, Any]) -> MappedGame:
    source = IGDBGamePayload.model_validate(payload)
    korean_name = _korean_name(source.game_localizations)
    names = [MappedName(source.name, normalize_game_name(source.name), "und", GameNameType.PRIMARY)]

    for item in source.alternative_names:
        name = _string(item.get("name"))
        if not name:
            continue
        comment = _string(item.get("comment")) or ""
        name_type = GameNameType.ALIAS if "alias" in comment.casefold() else GameNameType.ALTERNATIVE
        names.append(MappedName(name, normalize_game_name(name), "und", name_type))

    for item in source.game_localizations:
        name = _string(item.get("name"))
        if not name:
            continue
        language = "ko" if _is_korean_localization(item) else _localization_code(item)
        names.append(MappedName(name, normalize_game_name(name), language, GameNameType.LOCALIZED))

    external_ids: list[MappedExternalId] = []
    for item in source.external_games:
        external_id = _string(item.get("uid"))
        external_source = _external_source(item)
        if not external_source or not external_id:
            continue
        external_ids.append(MappedExternalId(external_source, external_id))
        external_name = _string(item.get("name"))
        if external_source == GameExternalSource.STEAM and external_name:
            names.append(
                MappedName(external_name, normalize_game_name(external_name), "und", GameNameType.STEAM)
            )

    return MappedGame(
        igdb_id=source.id,
        slug=source.slug,
        name=source.name,
        korean_name=korean_name,
        summary=source.summary,
        storyline=source.storyline,
        first_release_date=_release_date(source.first_release_date),
        rating=source.rating,
        names=_deduplicate_names(names),
        platforms=[
            MappedPlatform(item["id"], item["name"], _string(item.get("abbreviation")))
            for item in source.platforms
            if isinstance(item.get("id"), int) and _string(item.get("name"))
        ],
        genres=[
            MappedGenre(item["id"], item["name"])
            for item in source.genres
            if isinstance(item.get("id"), int) and _string(item.get("name"))
        ],
        companies=_companies(source.involved_companies),
        external_ids=list(dict.fromkeys(external_ids)),
        images=list(dict.fromkeys(_images(source))),
    )


def _release_date(timestamp: int | None) -> date | None:
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    except (OSError, OverflowError, ValueError):
        return None


def _companies(items: list[dict[str, Any]]) -> list[MappedCompany]:
    companies = []
    for item in items:
        company = item.get("company")
        if not isinstance(company, dict):
            continue
        igdb_id = company.get("id")
        name = _string(company.get("name"))
        if isinstance(igdb_id, int) and name:
            companies.append(
                MappedCompany(
                    igdb_id=igdb_id,
                    name=name,
                    developer=bool(item.get("developer")),
                    publisher=bool(item.get("publisher")),
                )
            )
    return companies


def _images(source: IGDBGamePayload) -> list[MappedImage]:
    images: list[MappedImage] = []
    if source.cover:
        image = _image(source.cover, GameImageType.COVER)
        if image:
            images.append(image)
    for item in source.artworks:
        image = _image(item, GameImageType.ARTWORK)
        if image:
            images.append(image)
    for item in source.screenshots:
        image = _image(item, GameImageType.SCREENSHOT)
        if image:
            images.append(image)
    return images


def _image(item: dict[str, Any], image_type: GameImageType) -> MappedImage | None:
    image_id = _string(item.get("image_id"))
    if not image_id:
        return None
    return MappedImage(
        type=image_type,
        url=IMAGE_URL.format(
            size="t_cover_big" if image_type == GameImageType.COVER else "t_original",
            image_id=image_id,
        ),
        width=item.get("width") if isinstance(item.get("width"), int) else None,
        height=item.get("height") if isinstance(item.get("height"), int) else None,
    )


def _korean_name(localizations: list[dict[str, Any]]) -> str | None:
    for localization in localizations:
        if _is_korean_localization(localization):
            name = _string(localization.get("name"))
            if name:
                return name
    return None


def _is_korean_localization(localization: dict[str, Any]) -> bool:
    region = localization.get("region")
    if isinstance(region, dict):
        identifier = (_string(region.get("identifier")) or "").casefold().replace("_", "-")
        region_name = (_string(region.get("name")) or "").casefold()
        if identifier in {"ko", "kr", "kor", "ko-kr", "korea", "south-korea"}:
            return True
        if region_name in {"korea", "south korea", "republic of korea"}:
            return True
    locale = _string(localization.get("locale")) or ""
    return locale.casefold().replace("_", "-") in {"ko", "ko-kr"}


def _localization_code(localization: dict[str, Any]) -> str:
    region = localization.get("region")
    if isinstance(region, dict):
        return (_string(region.get("identifier")) or "und")[:16]
    return (_string(localization.get("locale")) or "und")[:16]


def _deduplicate_names(names: list[MappedName]) -> list[MappedName]:
    unique: dict[tuple[str, str, GameNameType], MappedName] = {}
    for name in names:
        if name.normalized_name:
            unique[(name.normalized_name, name.language, name.type)] = name
    return list(unique.values())


def _external_source(item: dict[str, Any]) -> GameExternalSource | None:
    source = item.get("external_game_source")
    if not isinstance(source, dict):
        return None
    source_name = normalize_game_name(_string(source.get("name")) or "")
    if "steam" in source_name:
        return GameExternalSource.STEAM
    if source_name.startswith("gog"):
        return GameExternalSource.GOG
    if "epic" in source_name:
        return GameExternalSource.EPIC
    if "playstation" in source_name or source_name == "psn":
        return GameExternalSource.PSN
    if "xbox" in source_name or source_name == "microsoft":
        return GameExternalSource.XBOX
    if "nintendo" in source_name:
        return GameExternalSource.NINTENDO
    return None


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
