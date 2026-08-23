# RoomMaker
Sunrin vacation project 2nd team. Room maker for people

## 기술 스택 - Backend

| 분류 | 기술 |
| --- | --- |
| 언어 | Python 3.12 |
| API 서버 | FastAPI, Uvicorn |
| 데이터베이스 | PostgreSQL, SQLAlchemy 2, psycopg 3 |
| DB 마이그레이션 | Alembic |
| 데이터 검증 | Pydantic 2 |
| 인증 | Google·Discord OAuth 2.0, JWT (PyJWT) |
| 외부 연동 | IGDB·Twitch API (HTTPX), Firebase Admin·FCM, Discord Gateway Bot |
| 테스트 | pytest |

운영 DB는 PostgreSQL을 사용하며, `DATABASE_URL`이 없는 로컬 환경에서는 SQLite로 실행할 수 있습니다.

## 실행

```bash
alembic upgrade head
python -m uvicorn main:app --reload
```

`.env`의 `DATABASE_URL`에는 PostgreSQL 연결 주소를 설정합니다.

```env
DATABASE_URL=postgresql+psycopg://teammoa:teammoa@localhost:5432/teammoa
```

## Firebase 알림 설정

Firebase Console에서 서비스 계정 JSON 키를 발급하고, `.env`에 다음 중 한 가지 방식으로
인증 정보를 설정합니다.

```env
# 권장: 서비스 계정 JSON 파일의 절대 경로
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/firebase-service-account.json

# 파일을 사용할 수 없는 배포 환경에서만 JSON 전체 문자열 사용
FIREBASE_SERVICE_ACCOUNT_JSON=

# 알림을 눌렀을 때 열 프론트엔드 주소
FRONTEND_BASE_URL=https://teammoa.example
```

서비스 계정 JSON은 저장소에 커밋하지 않습니다. 모집방이 생성되면 해당 그룹 멤버에게,
모집 인원이 모두 모이면 모집방 참가자 전원에게 Firebase Cloud Messaging 알림을 보냅니다.

## Discord Gateway 알림 설정

Discord Developer Portal에서 OAuth와 Bot을 같은 애플리케이션에 설정하고 Bot Token을 `.env`에
추가합니다. Interaction Endpoint URL과 Public Key는 사용하지 않습니다.

```env
DISCORD_BOT_TOKEN=your_discord_bot_token
```

API 서버와 별도로 Gateway Bot 프로세스를 실행합니다.

```bash
python discord_gateway.py
```

사용자가 Discord를 연결하면 Bot이 알림 설정 Embed DM을 전송합니다. 버튼 Interaction은
Gateway로 수신하며, 버튼 데이터가 아닌 Interaction을 실행한 Discord 사용자 ID로 연결 계정을
조회합니다. FCM 토큰이 있으면 FCM으로만 보내고, FCM 토큰이 없을 때만 Discord Embed DM을
사용합니다. 한 채널의 전송 실패를 다른 채널 fallback 조건으로 사용하지 않습니다.

기존 데이터베이스에 Alembic을 처음 연결할 때만 기존 스키마를 기준점으로 표시한 뒤 게임
카탈로그 마이그레이션을 적용합니다.

```bash
alembic stamp 20260822_00
alembic upgrade head
```

## 로컬 게임 검색 API

```http
GET /api/v1/games/search?query=Minecraft&limit=10
Authorization: Bearer <access_token>
```

- `query`: 검색할 게임 이름 (1~100자, 필수)
- `limit`: 최대 결과 수 (1~50, 기본값 20)
- 응답 필드: `id`, `name`, `slug`, `cover_url`, `first_release_date`, `rating`, `platforms`

검색 요청은 로컬 데이터베이스만 조회합니다. 응답의 `id`는 기존 프론트엔드와의 호환을 위해
내부 PK가 아니라 IGDB ID를 유지합니다. PostgreSQL에서는 `pg_trgm`과 게임명 GIN 인덱스를
사용하며, 같은 게임의 기본 이름·한국어 이름·대체 이름이 여러 개 일치해도 게임은 한 번만
반환됩니다.

## IGDB 동기화

IGDB는 아래 오프라인 작업에서만 호출합니다. API 서버의 검색 요청에서는 사용하지 않습니다.
인증에는 `.env`의 `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`을 사용합니다.

```bash
# 이전 체크포인트부터 이어서 동기화
PYTHONPATH=backend python -m jobs.sync_games sync

# 처음부터 다시 upsert
PYTHONPATH=backend python -m jobs.sync_games sync --full

# 지정한 IGDB ID 다음부터 시작
PYTHONPATH=backend python -m jobs.sync_games sync --after-id 100000

# 특정 게임만 동기화 (소량 샘플 확인에도 사용)
PYTHONPATH=backend python -m jobs.sync_games sync --game-id 119133

# 배치 크기 지정 (1~500)
PYTHONPATH=backend python -m jobs.sync_games sync --batch-size 250

# PostgreSQL 검색 인덱스 재생성
PYTHONPATH=backend python -m jobs.sync_games rebuild-index
```

동기화는 최대 500개 단위로 insert/upsert하고 배치마다 `sync_states`에 마지막 IGDB ID를
저장합니다. IGDB 클라이언트는 하나의 `httpx.AsyncClient`를 재사용하며 동시 요청 수, 초당
요청 수, timeout, 429 및 5xx 재시도를 제한합니다.

작업이 중간에 실패하면 `--full`을 빼고 같은 명령을 다시 실행하면 마지막으로 커밋된 ID부터
자동으로 이어집니다. 로그에 표시된 ID를 직접 지정하려면 `--after-id <마지막 ID>`를 사용합니다.
전체 목록은 offset을 계속 늘리지 않고 `id > 마지막 ID`와 `sort id asc`를 사용하는 안정적인
커서 방식으로 가져옵니다.

## 프론트엔드 API

아래 경로는 로그인 응답을 제외하고 JWT `Authorization: Bearer <access_token>` 헤더가 필요합니다.
그룹·태그·모집방 ID는 JavaScript 정밀도 손실을 방지하기 위해 JSON 문자열로 반환합니다.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login/{provider}` | OAuth 로그인 |
| `POST`, `DELETE` | `/api/v1/auth/discord/link` | Discord 계정 연결·해제 |
| `POST` | `/api/v1/auth/logout-all` | 모든 기기 로그아웃·모집방 참가 취소 |
| `GET` | `/api/v1/users` | 사용자 목록 |
| `GET` | `/api/v1/users/{user_id}` | 사용자 상세 |
| `PATCH` | `/api/v1/users/{user_id}/fcm-token` | FCM 토큰 수정 |
| `PATCH` | `/api/v1/users/{user_id}/notification-preference` | 웹·Discord 공통 알림 상태 수정 |
| `PATCH` | `/api/v1/users/{user_id}/preferences` | 선호 게임 수정 |
| `GET`, `POST` | `/api/v1/groups` | 공개 그룹·참여 중인 그룹 목록, 그룹 생성 |
| `GET`, `DELETE` | `/api/v1/groups/{group_id}` | 그룹 상세·삭제 |
| `PATCH` | `/api/v1/groups/{group_id}/visibility` | 그룹 공개 범위 변경 |
| `POST` | `/api/v1/groups/{group_id}/join` | 그룹 참여 |
| `POST` | `/api/v1/groups/{group_id}/leave` | 그룹 탈퇴 |
| `GET`, `POST` | `/api/v1/groups/{group_id}/roles` | 태그 목록·생성 |
| `PATCH`, `DELETE` | `/api/v1/groups/{group_id}/roles/{role_id}` | 태그 수정·삭제 |
| `POST`, `DELETE` | `/api/v1/groups/{group_id}/roles/{role_id}/assign/{target_user_id}` | 태그 부여·해제 |
| `GET`, `POST` | `/api/v1/groups/{group_id}/rooms` | 모집방 목록·생성 |
| `GET`, `PATCH`, `DELETE` | `/api/v1/groups/{group_id}/rooms/{room_id}` | 모집방 상세·수정·삭제 |
| `POST` | `/api/v1/groups/{group_id}/rooms/{room_id}/join` | 모집방 참가 |
| `POST` | `/api/v1/groups/{group_id}/rooms/{room_id}/leave` | 모집방 참가 취소 |

## 테스트

```bash
PYTHONPATH=backend pytest -q
```
