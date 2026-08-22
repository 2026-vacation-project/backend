#!/usr/bin/env python3
"""Export only game catalog tables from the local SQLite application DB."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


GAME_TABLES = {
    "companies",
    "game_companies",
    "game_external_ids",
    "game_genres",
    "game_images",
    "game_names",
    "game_platforms",
    "games",
    "genres",
    "platforms",
    "sync_states",
}
DEFAULT_CHUNK_SIZE = 45 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def export_catalog(source: Path, destination: Path) -> dict[str, int]:
    source_connection = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
        destination_connection.execute("PRAGMA foreign_keys = OFF")
        destination_connection.execute("PRAGMA secure_delete = ON")

        existing_tables = {
            row[0]
            for row in destination_connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        missing_tables = GAME_TABLES - existing_tables
        if missing_tables:
            raise RuntimeError(f"게임 테이블이 없습니다: {', '.join(sorted(missing_tables))}")

        for table in sorted(existing_tables - GAME_TABLES):
            destination_connection.execute(f"DROP TABLE {quote_identifier(table)}")
        destination_connection.execute("DELETE FROM sync_states WHERE source != 'IGDB'")
        sqlite_sequence_exists = destination_connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
        ).fetchone()
        if sqlite_sequence_exists:
            destination_connection.execute(
                "DELETE FROM sqlite_sequence WHERE name NOT IN "
                f"({','.join('?' for _ in GAME_TABLES)})",
                tuple(sorted(GAME_TABLES)),
            )
        destination_connection.commit()
        destination_connection.execute("VACUUM")

        exported_tables = {
            row[0]
            for row in destination_connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if exported_tables != GAME_TABLES:
            raise RuntimeError("게임 전용 DB 검증에 실패했습니다.")
        if destination_connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("게임 전용 DB 무결성 검사에 실패했습니다.")

        return {
            table: destination_connection.execute(
                f"SELECT COUNT(*) FROM {quote_identifier(table)}"
            ).fetchone()[0]
            for table in sorted(GAME_TABLES)
        }
    finally:
        destination_connection.close()
        source_connection.close()


def compress(source: Path, destination: Path) -> None:
    with source.open("rb") as source_file, gzip.open(destination, "wb", compresslevel=9) as archive:
        shutil.copyfileobj(source_file, archive, length=4 * 1024 * 1024)


def split_archive(archive: Path, parts_directory: Path, chunk_size: int) -> list[dict[str, object]]:
    parts_directory.mkdir(parents=True, exist_ok=False)
    parts: list[dict[str, object]] = []
    with archive.open("rb") as source:
        index = 0
        while block := source.read(chunk_size):
            part = parts_directory / f"game_catalog.db.gz.part-{index:03d}"
            part.write_bytes(block)
            parts.append(
                {
                    "path": str(part.relative_to(parts_directory.parent)),
                    "size_bytes": part.stat().st_size,
                    "sha256": sha256(part),
                }
            )
            index += 1
    return parts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="게임 전용 SQLite DB를 압축 조각으로 내보냅니다.")
    parser.add_argument("--source", type=Path, default=Path("app.db"))
    parser.add_argument("--output-dir", type=Path, default=Path("game_catalog"))
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source = args.source.resolve()
    output_directory = args.output_dir.resolve()
    parts_directory = output_directory / "parts"
    manifest_path = output_directory / "manifest.json"

    if not source.is_file():
        raise SystemExit(f"원본 DB를 찾을 수 없습니다: {source}")
    if args.chunk_size <= 0:
        raise SystemExit("chunk-size는 1 이상이어야 합니다.")
    if parts_directory.exists() or manifest_path.exists():
        raise SystemExit("기존 parts 또는 manifest를 먼저 확인해 주세요. 자동으로 덮어쓰지 않습니다.")

    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="game-catalog-") as temporary_directory:
        temporary = Path(temporary_directory)
        database = temporary / "game_catalog.db"
        archive = temporary / "game_catalog.db.gz"
        counts = export_catalog(source, database)
        compress(database, archive)
        parts = split_archive(archive, parts_directory, args.chunk_size)

        manifest = {
            "format_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": {
                "filename": "game_catalog.db",
                "size_bytes": database.stat().st_size,
                "sha256": sha256(database),
                "tables": counts,
            },
            "archive": {
                "compression": "gzip",
                "size_bytes": archive.stat().st_size,
                "sha256": sha256(archive),
                "chunk_size_bytes": args.chunk_size,
            },
            "parts": parts,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(f"게임 {counts['games']:,}개를 {len(parts)}개 조각으로 내보냈습니다.")


if __name__ == "__main__":
    main()
