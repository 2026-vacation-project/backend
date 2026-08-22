from sqlalchemy.orm import Session

from games import repository
from games.normalization import normalize_game_name
from games.schemas import GameSearchResult


def search_games(db: Session, query: str, limit: int) -> list[GameSearchResult]:
    normalized_query = normalize_game_name(query)
    if not normalized_query:
        return []

    games = repository.search_games(db, query, normalized_query, limit)
    return [
        GameSearchResult(
            id=game.igdb_id,
            name=game.korean_name or game.name,
            slug=game.slug,
            cover_url=repository.get_cover_url(game),
            first_release_date=game.first_release_date,
            rating=game.rating,
            platforms=sorted(platform.name for platform in game.platforms),
        )
        for game in games
    ]
