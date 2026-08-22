import asyncio
import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_API_URL = "https://api.igdb.com/v4"


class IGDBClientError(Exception):
    pass


class IGDBClient:
    """Rate-limited IGDB client used only by offline synchronization jobs."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        *,
        max_concurrency: int = 4,
        requests_per_second: float = 4.0,
        max_retries: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.client_id = client_id if client_id is not None else os.getenv("TWITCH_CLIENT_ID", "")
        self.client_secret = (
            client_secret if client_secret is not None else os.getenv("TWITCH_CLIENT_SECRET", "")
        )
        self.max_retries = max_retries
        self._request_interval = 1 / requests_per_second
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._rate_lock = asyncio.Lock()
        self._token_lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
        )

    async def __aenter__(self) -> "IGDBClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _check_configuration(self) -> None:
        if not self.client_id or not self.client_secret:
            raise IGDBClientError("TWITCH_CLIENT_ID와 TWITCH_CLIENT_SECRET을 설정해 주세요.")

    async def _get_access_token(self, force_refresh: bool = False) -> str:
        self._check_configuration()
        if not force_refresh and self._token_is_valid():
            return self._access_token  # type: ignore[return-value]

        async with self._token_lock:
            if not force_refresh and self._token_is_valid():
                return self._access_token  # type: ignore[return-value]
            try:
                response = await self._client.post(
                    TWITCH_TOKEN_URL,
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "client_credentials",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                access_token = payload["access_token"]
                if not isinstance(access_token, str) or not access_token:
                    raise ValueError("empty access token")
                self._access_token = access_token
                self._token_expires_at = time.monotonic() + max(int(payload["expires_in"]) - 60, 0)
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                raise IGDBClientError("IGDB 인증 토큰을 발급받지 못했습니다.") from exc
            return self._access_token

    def _token_is_valid(self) -> bool:
        return bool(self._access_token) and time.monotonic() < self._token_expires_at

    async def _wait_for_rate_limit(self) -> None:
        async with self._rate_lock:
            delay = self._last_request_at + self._request_interval - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request_at = time.monotonic()

    async def query(self, endpoint: str, body: str) -> list[dict[str, Any]]:
        access_token = await self._get_access_token()
        refreshed_token = False

        for attempt in range(self.max_retries + 1):
            await self._wait_for_rate_limit()
            try:
                async with self._semaphore:
                    response = await self._client.post(
                        f"{IGDB_API_URL}/{endpoint}",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer {access_token}",
                            "Client-ID": self.client_id,
                        },
                        content=body,
                    )
            except httpx.RequestError as exc:
                if attempt == self.max_retries:
                    raise IGDBClientError("IGDB에 연결하지 못했습니다.") from exc
                await self._backoff(attempt)
                continue

            if response.status_code == 401 and not refreshed_token:
                access_token = await self._get_access_token(force_refresh=True)
                refreshed_token = True
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == self.max_retries:
                    raise IGDBClientError(f"IGDB 동기화 요청이 실패했습니다. ({response.status_code})")
                retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                await self._backoff(attempt, retry_after)
                continue
            if response.status_code != 200:
                raise IGDBClientError(f"IGDB 동기화 요청이 실패했습니다. ({response.status_code})")

            try:
                payload = response.json()
            except ValueError as exc:
                raise IGDBClientError("IGDB가 올바르지 않은 응답을 반환했습니다.") from exc
            if not isinstance(payload, list):
                raise IGDBClientError("IGDB가 올바르지 않은 응답을 반환했습니다.")
            return [item for item in payload if isinstance(item, dict)]

        raise IGDBClientError("IGDB 동기화 요청이 실패했습니다.")

    @staticmethod
    async def _backoff(attempt: int, retry_after: float | None = None) -> None:
        delay = retry_after if retry_after is not None else min(2**attempt, 30) + random.uniform(0, 0.25)
        await asyncio.sleep(max(delay, 0))

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(float(value), 0)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0)
