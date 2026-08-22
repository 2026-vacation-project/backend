from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from games.models import (
    Company,
    Game,
    GameCompany,
    GameExternalId,
    GameImage,
    GameName,
    GameNameType,
    Genre,
    Platform,
    SyncState,
    game_genres,
    game_platforms,
)
from games.normalization import normalize_game_name
from importers.igdb.mapper import MappedGame, MappedName, map_game


class IGDBImporter:
    MAX_BATCH_SIZE = 500

    def __init__(self, db: Session) -> None:
        self.db = db

    def import_batch(self, payloads: Iterable[dict], source: str = "IGDB") -> int:
        payload_list = list(payloads)
        if len(payload_list) > self.MAX_BATCH_SIZE:
            raise ValueError(f"한 번에 최대 {self.MAX_BATCH_SIZE}개까지 가져올 수 있습니다.")

        mapped_by_igdb_id = {game.igdb_id: game for game in map(map_game, payload_list)}
        mapped_games = list(mapped_by_igdb_id.values())
        if not mapped_games:
            return 0

        try:
            self._preserve_existing_korean_names(mapped_games)
            self._upsert_games(mapped_games)
            game_ids = self._entity_ids(Game, [game.igdb_id for game in mapped_games])

            platform_rows = self._platform_rows(mapped_games)
            genre_rows = self._genre_rows(mapped_games)
            company_rows = self._company_rows(mapped_games)
            self._upsert_rows(Platform.__table__, platform_rows, ["igdb_id"], ["name", "abbreviation"])
            self._upsert_rows(Genre.__table__, genre_rows, ["igdb_id"], ["name"])
            self._upsert_rows(Company.__table__, company_rows, ["igdb_id"], ["name"])

            platform_ids = self._entity_ids(Platform, [row["igdb_id"] for row in platform_rows])
            genre_ids = self._entity_ids(Genre, [row["igdb_id"] for row in genre_rows])
            company_ids = self._entity_ids(Company, [row["igdb_id"] for row in company_rows])
            self._replace_game_relations(mapped_games, game_ids, platform_ids, genre_ids, company_ids)

            last_processed_id = max(game.igdb_id for game in mapped_games)
            self._update_sync_state(source, last_processed_id, complete=False)
            self.db.commit()
            return len(mapped_games)
        except Exception:
            self.db.rollback()
            raise

    def mark_complete(self, source: str, last_processed_id: int | None) -> None:
        try:
            self._update_sync_state(source, last_processed_id, complete=True)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _preserve_existing_korean_names(self, mapped_games: list[MappedGame]) -> None:
        igdb_ids = [game.igdb_id for game in mapped_games]
        statement = select(Game.igdb_id, Game.korean_name).where(
            Game.igdb_id.in_(igdb_ids),
            Game.korean_name.is_not(None),
        )
        existing = dict(self.db.execute(statement).all())
        for game in mapped_games:
            if game.korean_name or not existing.get(game.igdb_id):
                continue
            game.korean_name = existing[game.igdb_id]
            preserved = MappedName(
                name=game.korean_name,
                normalized_name=normalize_game_name(game.korean_name),
                language="ko",
                type=GameNameType.LOCALIZED,
            )
            if preserved not in game.names:
                game.names.append(preserved)

    def _upsert_games(self, games: list[MappedGame]) -> None:
        rows = [
            {
                "igdb_id": game.igdb_id,
                "slug": game.slug,
                "name": game.name,
                "korean_name": game.korean_name,
                "summary": game.summary,
                "storyline": game.storyline,
                "first_release_date": game.first_release_date,
                "rating": game.rating,
            }
            for game in games
        ]
        statement = self._dialect_insert(Game.__table__).values(rows)
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=["igdb_id"],
            set_={
                "slug": excluded.slug,
                "name": excluded.name,
                "korean_name": func.coalesce(excluded.korean_name, Game.__table__.c.korean_name),
                "summary": excluded.summary,
                "storyline": excluded.storyline,
                "first_release_date": excluded.first_release_date,
                "rating": excluded.rating,
                "updated_at": func.now(),
            },
        )
        self.db.execute(statement)

    def _replace_game_relations(
        self,
        games: list[MappedGame],
        game_ids: dict[int, int],
        platform_ids: dict[int, int],
        genre_ids: dict[int, int],
        company_ids: dict[int, int],
    ) -> None:
        internal_game_ids = list(game_ids.values())
        for table in (GameName, GameCompany, GameExternalId, GameImage):
            self.db.execute(delete(table).where(table.game_id.in_(internal_game_ids)))
        self.db.execute(delete(game_platforms).where(game_platforms.c.game_id.in_(internal_game_ids)))
        self.db.execute(delete(game_genres).where(game_genres.c.game_id.in_(internal_game_ids)))

        name_rows = []
        platform_links = set()
        genre_links = set()
        company_links = {}
        external_rows = {}
        image_rows = {}

        for game in games:
            game_id = game_ids[game.igdb_id]
            name_rows.extend(
                {
                    "game_id": game_id,
                    "name": name.name,
                    "normalized_name": name.normalized_name,
                    "language": name.language,
                    "type": name.type,
                }
                for name in game.names
            )
            platform_links.update(
                (game_id, platform_ids[platform.igdb_id])
                for platform in game.platforms
                if platform.igdb_id in platform_ids
            )
            genre_links.update(
                (game_id, genre_ids[genre.igdb_id])
                for genre in game.genres
                if genre.igdb_id in genre_ids
            )
            for company in game.companies:
                if company.igdb_id not in company_ids:
                    continue
                key = (game_id, company_ids[company.igdb_id])
                current = company_links.setdefault(key, {"developer": False, "publisher": False})
                current["developer"] = current["developer"] or company.developer
                current["publisher"] = current["publisher"] or company.publisher
            for external in game.external_ids:
                external_rows[(external.source, external.external_id)] = {
                    "game_id": game_id,
                    "source": external.source,
                    "external_id": external.external_id,
                }
            for image in game.images:
                image_rows[(game_id, image.type, image.url)] = {
                    "game_id": game_id,
                    "type": image.type,
                    "url": image.url,
                    "width": image.width,
                    "height": image.height,
                }

        self._insert_if_any(GameName.__table__, name_rows)
        self._insert_if_any(
            game_platforms,
            [{"game_id": game_id, "platform_id": platform_id} for game_id, platform_id in platform_links],
        )
        self._insert_if_any(
            game_genres,
            [{"game_id": game_id, "genre_id": genre_id} for game_id, genre_id in genre_links],
        )
        self._insert_if_any(
            GameCompany.__table__,
            [
                {
                    "game_id": key[0],
                    "company_id": key[1],
                    "developer": flags["developer"],
                    "publisher": flags["publisher"],
                }
                for key, flags in company_links.items()
            ],
        )
        self._upsert_external_ids(list(external_rows.values()))
        self._insert_if_any(GameImage.__table__, list(image_rows.values()))

    def _entity_ids(self, model, igdb_ids: list[int]) -> dict[int, int]:
        if not igdb_ids:
            return {}
        statement = select(model.igdb_id, model.id).where(model.igdb_id.in_(set(igdb_ids)))
        return dict(self.db.execute(statement).all())

    def _update_sync_state(self, source: str, last_processed_id: int | None, complete: bool) -> None:
        values = {
            "source": source,
            "cursor": str(last_processed_id) if last_processed_id is not None else None,
            "last_processed_id": last_processed_id,
            "last_sync_at": datetime.now(timezone.utc) if complete else None,
            "updated_at": datetime.now(timezone.utc),
        }
        statement = self._dialect_insert(SyncState.__table__).values(values)
        excluded = statement.excluded
        update_values = {
            "cursor": excluded.cursor,
            "last_processed_id": excluded.last_processed_id,
            "updated_at": excluded.updated_at,
        }
        if complete:
            update_values["last_sync_at"] = excluded.last_sync_at
        statement = statement.on_conflict_do_update(index_elements=["source"], set_=update_values)
        self.db.execute(statement)

    def _upsert_rows(self, table, rows: list[dict], keys: list[str], update_columns: list[str]) -> None:
        if not rows:
            return
        statement = self._dialect_insert(table).values(rows)
        excluded = statement.excluded
        statement = statement.on_conflict_do_update(
            index_elements=keys,
            set_={column: getattr(excluded, column) for column in update_columns},
        )
        self.db.execute(statement)

    def _dialect_insert(self, table):
        dialect = self.db.bind.dialect.name if self.db.bind is not None else ""
        if dialect == "postgresql":
            return postgresql_insert(table)
        if dialect == "sqlite":
            return sqlite_insert(table)
        raise RuntimeError(f"지원하지 않는 데이터베이스입니다: {dialect}")

    def _upsert_external_ids(self, rows: list[dict]) -> None:
        if not rows:
            return
        statement = self._dialect_insert(GameExternalId.__table__).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=["source", "external_id"],
            set_={"game_id": statement.excluded.game_id},
        )
        self.db.execute(statement)

    def _insert_if_any(self, table, rows: list[dict]) -> None:
        if rows:
            self.db.execute(insert(table), rows)

    @staticmethod
    def _platform_rows(games: list[MappedGame]) -> list[dict]:
        unique = {
            platform.igdb_id: {
                "igdb_id": platform.igdb_id,
                "name": platform.name,
                "abbreviation": platform.abbreviation,
            }
            for game in games
            for platform in game.platforms
        }
        return list(unique.values())

    @staticmethod
    def _genre_rows(games: list[MappedGame]) -> list[dict]:
        unique = {
            genre.igdb_id: {"igdb_id": genre.igdb_id, "name": genre.name}
            for game in games
            for genre in game.genres
        }
        return list(unique.values())

    @staticmethod
    def _company_rows(games: list[MappedGame]) -> list[dict]:
        unique = {
            company.igdb_id: {"igdb_id": company.igdb_id, "name": company.name}
            for game in games
            for company in game.companies
        }
        return list(unique.values())


def rebuild_search_indexes(db: Session) -> None:
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    db.execute(text("REINDEX INDEX ix_game_names_normalized_name_trgm"))
    db.commit()
