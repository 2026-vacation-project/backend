from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session, selectinload

from games.models import Game, GameCompany, GameImage, GameName


def search_games(db: Session, query: str, normalized_query: str, limit: int) -> list[Game]:
    raw_exact = func.lower(GameName.name) == query.casefold()
    normalized_exact = GameName.normalized_name == normalized_query
    prefix_match = GameName.normalized_name.like(f"{normalized_query}%")
    substring_match = GameName.normalized_name.like(f"%{normalized_query}%")

    rank = case(
        (raw_exact, 0),
        (normalized_exact, 1),
        (prefix_match, 2),
        (substring_match, 3),
        else_=4,
    )

    # A raw-name match is also a normalized exact match, so it is only needed
    # for ranking. Keeping lower(name) out of the WHERE clause lets PostgreSQL
    # use the normalized-name indexes for every candidate lookup.
    match_conditions = [normalized_exact, prefix_match]
    if len(normalized_query) >= 3:
        match_conditions.append(substring_match)

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        similarity = func.similarity(GameName.normalized_name, normalized_query)
        if len(normalized_query) >= 3:
            match_conditions.append(GameName.normalized_name.op("%")(normalized_query))
    else:
        similarity = literal(0.0)

    scores = (
        select(
            GameName.game_id.label("game_id"),
            func.min(rank).label("match_rank"),
            func.max(similarity).label("similarity"),
        )
        .where(or_(*match_conditions))
        .group_by(GameName.game_id)
        .subquery()
    )

    statement = (
        select(Game)
        .join(scores, scores.c.game_id == Game.id)
        .options(selectinload(Game.platforms), selectinload(Game.images))
        .order_by(scores.c.match_rank, scores.c.similarity.desc(), Game.name)
        .limit(limit)
    )
    return list(db.scalars(statement).unique().all())


def get_game(db: Session, igdb_id: int) -> Game | None:
    statement = (
        select(Game)
        .where(Game.igdb_id == igdb_id)
        .options(
            selectinload(Game.names),
            selectinload(Game.platforms),
            selectinload(Game.genres),
            selectinload(Game.images),
            selectinload(Game.external_ids),
            selectinload(Game.company_links).selectinload(GameCompany.company),
        )
    )
    return db.scalar(statement)


def get_game_names(db: Session, game_id: int) -> list[GameName]:
    statement = select(GameName).where(GameName.game_id == game_id).order_by(GameName.type, GameName.name)
    return list(db.scalars(statement).all())


def get_cover_url(game: Game) -> str | None:
    cover = next((image for image in game.images if image.type.value == "COVER"), None)
    return cover.url if cover else None
