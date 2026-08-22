import asyncio

import httpx

import database
import utils
from games.service import search_games
from importers.igdb.importer import IGDBImporter
from main import app


def test_all_supported_names_find_one_game(session_factory, elden_ring_payload) -> None:
    with session_factory() as db:
        IGDBImporter(db).import_batch([elden_ring_payload])

    with session_factory() as db:
        for query in ("엘든 링", "엘든링", "Elden Ring", "eldenring"):
            results = search_games(db, query, 20)
            assert len(results) == 1
            assert results[0].id == elden_ring_payload["id"]


def test_multiple_matching_names_do_not_duplicate_game(session_factory, elden_ring_payload) -> None:
    with session_factory() as db:
        IGDBImporter(db).import_batch([elden_ring_payload])
        results = search_games(db, "eldenring", 20)
        assert [game.id for game in results] == [elden_ring_payload["id"]]


def test_runtime_endpoint_uses_database_only(monkeypatch, session_factory, elden_ring_payload) -> None:
    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Runtime search called IGDB")

    monkeypatch.setattr("integrations.igdb.client.IGDBClient.query", fail_if_called)
    with session_factory() as db:
        IGDBImporter(db).import_batch([elden_ring_payload])

    def override_database():
        with session_factory() as db:
            yield db

    app.dependency_overrides[database.get_db] = override_database
    app.dependency_overrides[utils.get_current_user_id] = lambda: "test-user"
    try:
        async def request():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.get(
                    "/api/v1/games/search",
                    params={"query": "엘든링", "limit": 20},
                )

        response = asyncio.run(request())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": elden_ring_payload["id"],
            "name": "엘든 링",
            "slug": "elden-ring",
            "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co4jni.jpg",
            "first_release_date": "2022-02-25",
            "rating": 95.0,
            "platforms": ["PC (Microsoft Windows)"],
        }
    ]
