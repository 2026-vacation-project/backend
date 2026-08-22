import argparse
import asyncio
from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from games.models import SyncState
from importers.igdb.importer import IGDBImporter, rebuild_search_indexes
from integrations.igdb.client import IGDBClient


GAME_FIELDS = """
fields id,name,slug,summary,storyline,first_release_date,rating,
alternative_names.name,alternative_names.comment,
game_localizations.name,
game_localizations.region.identifier,game_localizations.region.name,
platforms.id,platforms.name,platforms.abbreviation,
genres.id,genres.name,
involved_companies.developer,involved_companies.publisher,
involved_companies.company.id,involved_companies.company.name,
cover.image_id,cover.width,cover.height,
artworks.image_id,artworks.width,artworks.height,
screenshots.image_id,screenshots.width,screenshots.height,
external_games.external_game_source.name,external_games.uid,external_games.name;
""".replace("\n", " ")


async def sync_games_from_igdb(
    client: IGDBClient,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    batch_size: int = 500,
    full: bool = False,
    after_id: int | None = None,
    game_ids: Sequence[int] | None = None,
) -> int:
    if not 1 <= batch_size <= 500:
        raise ValueError("batch_size는 1부터 500까지 사용할 수 있습니다.")
    if after_id is not None and after_id < 0:
        raise ValueError("after_id는 0 이상이어야 합니다.")
    if full and after_id is not None:
        raise ValueError("full과 after_id는 함께 사용할 수 없습니다.")
    if game_ids and (full or after_id is not None):
        raise ValueError("game_ids는 full 또는 after_id와 함께 사용할 수 없습니다.")
    if game_ids and any(game_id <= 0 for game_id in game_ids):
        raise ValueError("game_ids에는 1 이상의 IGDB ID만 사용할 수 있습니다.")

    if game_ids:
        return await _sync_selected_games(client, session_factory, batch_size, game_ids)

    if after_id is not None:
        last_processed_id = after_id
    else:
        last_processed_id = 0 if full else _last_processed_id(session_factory)
    imported_count = 0

    while True:
        body = (
            f"{GAME_FIELDS} "
            f"where id > {last_processed_id}; "
            "sort id asc; "
            f"limit {batch_size};"
        )
        payloads = await client.query("games", body)
        if not payloads:
            with session_factory() as db:
                IGDBImporter(db).mark_complete("IGDB", last_processed_id or None)
            return imported_count

        with session_factory() as db:
            imported_count += IGDBImporter(db).import_batch(payloads)
        last_processed_id = max(int(payload["id"]) for payload in payloads)
        print(f"IGDB 게임 {imported_count:,}개 동기화 · 마지막 ID {last_processed_id}")


async def _sync_selected_games(
    client: IGDBClient,
    session_factory: Callable[[], Session],
    batch_size: int,
    game_ids: Sequence[int],
) -> int:
    imported_count = 0
    unique_ids = sorted(set(game_ids))
    for offset in range(0, len(unique_ids), batch_size):
        batch_ids = unique_ids[offset : offset + batch_size]
        joined_ids = ",".join(str(game_id) for game_id in batch_ids)
        payloads = await client.query(
            "games",
            f"{GAME_FIELDS} where id = ({joined_ids}); sort id asc; limit {len(batch_ids)};",
        )
        with session_factory() as db:
            imported_count += IGDBImporter(db).import_batch(payloads, source="IGDB_MANUAL")
    return imported_count


def _last_processed_id(session_factory: Callable[[], Session]) -> int:
    with session_factory() as db:
        state = db.scalar(select(SyncState).where(SyncState.source == "IGDB"))
        if state is None or state.last_processed_id is None:
            return 0
        return state.last_processed_id


def rebuild_index(session_factory: Callable[[], Session] = SessionLocal) -> None:
    with session_factory() as db:
        rebuild_search_indexes(db)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력해 주세요.")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("0 이상의 정수를 입력해 주세요.")
    return parsed


def _batch_size(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= IGDBImporter.MAX_BATCH_SIZE:
        raise argparse.ArgumentTypeError(
            f"1부터 {IGDBImporter.MAX_BATCH_SIZE}까지의 정수를 입력해 주세요."
        )
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="게임 데이터베이스 동기화")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="IGDB 데이터를 동기화합니다.")
    start_options = sync_parser.add_mutually_exclusive_group()
    start_options.add_argument("--full", action="store_true", help="처음부터 다시 동기화합니다.")
    start_options.add_argument(
        "--after-id",
        type=_non_negative_int,
        help="지정한 IGDB ID 다음 게임부터 동기화합니다.",
    )
    start_options.add_argument(
        "--game-id",
        type=_positive_int,
        action="append",
        help="지정한 IGDB 게임만 동기화합니다. 여러 번 지정할 수 있습니다.",
    )
    sync_parser.add_argument("--batch-size", type=_batch_size, default=500)
    subparsers.add_parser("rebuild-index", help="게임 이름 검색 인덱스를 다시 만듭니다.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "rebuild-index":
        rebuild_index()
        print("게임 검색 인덱스를 다시 만들었습니다.")
        return

    async def run() -> int:
        async with IGDBClient() as client:
            return await sync_games_from_igdb(
                client,
                batch_size=args.batch_size,
                full=args.full,
                after_id=args.after_id,
                game_ids=args.game_id,
            )

    imported_count = asyncio.run(run())
    print(f"동기화 완료 · {imported_count:,}개 처리")


if __name__ == "__main__":
    main()
