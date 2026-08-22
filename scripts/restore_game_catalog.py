#!/usr/bin/env python3
"""Restore and verify a game catalog SQLite DB from committed chunks."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="분할된 게임 DB를 복원하고 검증합니다.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("game_catalog/manifest.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("game_catalog.db"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest_path = args.manifest.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"출력 파일이 이미 있습니다: {output}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="game-catalog-restore-", dir=output.parent) as temp_dir:
        temporary = Path(temp_dir)
        archive = temporary / "game_catalog.db.gz"
        restored = temporary / "game_catalog.db"

        with archive.open("wb") as combined:
            for part_info in manifest["parts"]:
                part = (root / part_info["path"]).resolve()
                if not part.is_relative_to(root):
                    raise RuntimeError(f"잘못된 조각 경로입니다: {part}")
                if part.stat().st_size != part_info["size_bytes"] or sha256(part) != part_info["sha256"]:
                    raise RuntimeError(f"DB 조각 검증에 실패했습니다: {part.name}")
                with part.open("rb") as source:
                    shutil.copyfileobj(source, combined, length=4 * 1024 * 1024)

        if sha256(archive) != manifest["archive"]["sha256"]:
            raise RuntimeError("결합한 압축 파일의 검증에 실패했습니다.")

        with gzip.open(archive, "rb") as source, restored.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=4 * 1024 * 1024)

        expected_database = manifest["database"]
        if (
            restored.stat().st_size != expected_database["size_bytes"]
            or sha256(restored) != expected_database["sha256"]
        ):
            raise RuntimeError("복원한 DB의 검증에 실패했습니다.")

        connection = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("복원한 DB의 SQLite 무결성 검사에 실패했습니다.")
        finally:
            connection.close()

        os.replace(restored, output)

    print(f"게임 DB를 복원했습니다: {output}")


if __name__ == "__main__":
    main()
