import asyncio

import httpx

from integrations.igdb.client import IGDBClient


def test_client_reuses_token_and_retries_rate_limit() -> None:
    token_requests = 0
    game_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests, game_requests
        if request.url.host == "id.twitch.tv":
            token_requests += 1
            assert request.url.params["client_id"] == "client-id"
            assert request.url.params["client_secret"] == "client-secret"
            assert request.url.params["grant_type"] == "client_credentials"
            return httpx.Response(
                200,
                json={"access_token": "access-token", "expires_in": 3600},
            )

        game_requests += 1
        assert request.headers["Client-ID"] == "client-id"
        assert request.headers["Authorization"] == "Bearer access-token"
        if game_requests == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[])

    async def run() -> None:
        async with IGDBClient(
            "client-id",
            "client-secret",
            transport=httpx.MockTransport(handler),
        ) as client:
            assert await client.query("games", "fields id; limit 1;") == []
            assert await client.query("games", "fields id; limit 1;") == []

    asyncio.run(run())

    assert token_requests == 1
    assert game_requests == 3
