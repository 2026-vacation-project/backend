import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"
IGDB_COVER_URL = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"


class IGDBClientError(Exception):
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class IGDBClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.client_id = client_id if client_id is not None else os.getenv("TWITCH_CLIENT_ID", "")
        self.client_secret = (
            client_secret if client_secret is not None else os.getenv("TWITCH_CLIENT_SECRET", "")
        )
        self.transport = transport
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    def _check_configuration(self) -> None:
        if not self.client_id or not self.client_secret:
            raise IGDBClientError(
                "IGDB 설정(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)이 구성되지 않았습니다.",
                status_code=503,
            )

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        self._check_configuration()

        if not force_refresh and self._is_token_valid():
            return self._access_token  # type: ignore[return-value]

        async with self._token_lock:
            if not force_refresh and self._is_token_valid():
                return self._access_token  # type: ignore[return-value]

            try:
                async with self._http_client() as client:
                    response = await client.post(
                        TWITCH_TOKEN_URL,
                        data={
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "grant_type": "client_credentials",
                        },
                    )
            except httpx.RequestError as exc:
                raise IGDBClientError("Twitch 인증 서버에 연결할 수 없습니다.") from exc

            if response.status_code != 200:
                raise IGDBClientError("IGDB 인증 토큰을 발급받지 못했습니다.")

            try:
                payload = response.json()
                access_token = payload["access_token"]
                expires_in = int(payload["expires_in"])
            except (KeyError, TypeError, ValueError) as exc:
                raise IGDBClientError("Twitch 인증 서버가 올바르지 않은 응답을 반환했습니다.") from exc

            if not isinstance(access_token, str) or not access_token:
                raise IGDBClientError("Twitch 인증 서버가 올바르지 않은 응답을 반환했습니다.")

            self._access_token = access_token
            self._token_expires_at = time.monotonic() + max(expires_in - 60, 0)
            return access_token

    def _is_token_valid(self) -> bool:
        return bool(self._access_token) and time.monotonic() < self._token_expires_at

    async def search_games(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        escaped_query = query.replace("\\", "\\\\").replace('"', '\\"')
        request_body = (
            f'search "{escaped_query}"; '
            "fields name,slug,cover.image_id,first_release_date,rating,platforms.name; "
            "where version_parent = null; "
            f"limit {limit};"
        )

        access_token = await self._get_access_token()
        response = await self._request_games(request_body, access_token)

        if response.status_code == 401:
            access_token = await self._get_access_token(force_refresh=True)
            response = await self._request_games(request_body, access_token)

        if response.status_code == 429:
            raise IGDBClientError(
                "IGDB 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.",
                status_code=503,
            )
        if response.status_code != 200:
            raise IGDBClientError("IGDB에서 게임 정보를 조회하지 못했습니다.")

        try:
            games = response.json()
        except ValueError as exc:
            raise IGDBClientError("IGDB가 올바르지 않은 응답을 반환했습니다.") from exc

        if not isinstance(games, list):
            raise IGDBClientError("IGDB가 올바르지 않은 응답을 반환했습니다.")

        return [self._normalize_game(game) for game in games if isinstance(game, dict)]

    async def _request_games(self, request_body: str, access_token: str) -> httpx.Response:
        try:
            async with self._http_client() as client:
                return await client.post(
                    IGDB_GAMES_URL,
                    headers={
                        "Accept": "application/json",
                        "Authorization": f"Bearer {access_token}",
                        "Client-ID": self.client_id,
                    },
                    content=request_body,
                )
        except httpx.RequestError as exc:
            raise IGDBClientError("IGDB 서버에 연결할 수 없습니다.") from exc

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            transport=self.transport,
        )

    @staticmethod
    def _normalize_game(game: dict[str, Any]) -> dict[str, Any]:
        cover = game.get("cover")
        image_id = cover.get("image_id") if isinstance(cover, dict) else None

        platforms = game.get("platforms")
        platform_names = []
        if isinstance(platforms, list):
            platform_names = [
                platform["name"]
                for platform in platforms
                if isinstance(platform, dict) and isinstance(platform.get("name"), str)
            ]

        release_date = None
        first_release_date = game.get("first_release_date")
        if isinstance(first_release_date, (int, float)):
            try:
                release_date = datetime.fromtimestamp(first_release_date, tz=timezone.utc).date()
            except (OSError, OverflowError, ValueError):
                pass

        rating = game.get("rating")
        if not isinstance(rating, (int, float)):
            rating = None

        return {
            "id": game.get("id"),
            "name": game.get("name"),
            "slug": game.get("slug"),
            "cover_url": IGDB_COVER_URL.format(image_id=image_id) if image_id else None,
            "first_release_date": release_date,
            "rating": rating,
            "platforms": platform_names,
        }


igdb_client = IGDBClient()


def get_igdb_client() -> IGDBClient:
    return igdb_client
