# Game catalog snapshot

IGDB에서 가져온 게임 카탈로그만 담은 SQLite 스냅샷입니다. 사용자, 그룹, 모집방 데이터는
포함하지 않습니다. GitHub 파일 크기 제한과 저장소 경고 기준을 피하기 위해 gzip 압축 파일을
45MiB 이하 조각으로 나눴습니다.

## 복원

저장소 루트에서 실행합니다.

```bash
python scripts/restore_game_catalog.py --output game_catalog.db
```

복원 과정에서 각 조각, 결합한 gzip, 최종 SQLite DB의 SHA-256과 SQLite 무결성을 모두
검사합니다. 기존 파일은 자동으로 덮어쓰지 않습니다.

게임 수와 테이블별 행 수, 생성 시각, 해시는 `manifest.json`에서 확인할 수 있습니다.
이 파일은 게임 카탈로그 전용 SQLite 스냅샷이며 PostgreSQL dump는 아닙니다.

## 다시 생성

로컬 `app.db`의 게임 테이블만 새 스냅샷으로 만들 때 사용합니다.

```bash
python scripts/export_game_catalog.py --source app.db --output-dir game_catalog
```

기존 `game_catalog/parts`와 `game_catalog/manifest.json`은 안전을 위해 자동으로 삭제하거나
덮어쓰지 않습니다.
