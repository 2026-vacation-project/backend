# RoomMaker
Sunrin vacation project 2nd team. Room maker for people

## 실행

```bash
python -m uvicorn main:app --reload
```

## 게임 검색 API

```http
GET /api/v1/games/search?query=Minecraft&limit=10
Authorization: Bearer <access_token>
```

- `query`: 검색할 게임 이름 (1~100자, 필수)
- `limit`: 최대 결과 수 (1~20, 기본값 10)
- 응답 필드: `id`, `name`, `slug`, `cover_url`, `first_release_date`, `rating`, `platforms`

IGDB 인증에는 `.env`의 `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`을 사용합니다.

## 프론트엔드 API

아래 경로는 로그인 응답을 제외하고 JWT `Authorization: Bearer <access_token>` 헤더가 필요합니다.
그룹·역할·모집방 ID는 JavaScript 정밀도 손실을 방지하기 위해 JSON 문자열로 반환합니다.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login/{provider}` | OAuth 로그인 |
| `GET` | `/api/v1/users` | 사용자 목록 |
| `GET` | `/api/v1/users/{user_id}` | 사용자 상세 |
| `PATCH` | `/api/v1/users/{user_id}/fcm-token` | FCM 토큰 수정 |
| `PATCH` | `/api/v1/users/{user_id}/preferences` | 선호 게임 수정 |
| `GET`, `POST` | `/api/v1/groups` | 그룹 목록·생성 |
| `GET`, `DELETE` | `/api/v1/groups/{group_id}` | 그룹 상세·삭제 |
| `POST` | `/api/v1/groups/{group_id}/join` | 그룹 참여 |
| `POST` | `/api/v1/groups/{group_id}/leave` | 그룹 탈퇴 |
| `GET`, `POST` | `/api/v1/groups/{group_id}/roles` | 역할 목록·생성 |
| `PATCH`, `DELETE` | `/api/v1/groups/{group_id}/roles/{role_id}` | 역할 수정·삭제 |
| `POST` | `/api/v1/groups/{group_id}/roles/{role_id}/assign/{target_user_id}` | 역할 부여 |
| `GET`, `POST` | `/api/v1/groups/{group_id}/rooms` | 모집방 목록·생성 |
| `GET`, `PATCH`, `DELETE` | `/api/v1/groups/{group_id}/rooms/{room_id}` | 모집방 상세·수정·삭제 |
| `POST` | `/api/v1/groups/{group_id}/rooms/{room_id}/join` | 모집방 참가 |
| `POST` | `/api/v1/groups/{group_id}/rooms/{room_id}/leave` | 모집방 참가 취소 |

## 테스트

```bash
python -m unittest discover -s tests -v
```
