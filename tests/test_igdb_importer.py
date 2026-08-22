import asyncio

from sqlalchemy import func, select

from games.models import Game, GameName, SyncState
from jobs.sync_games import sync_games_from_igdb


class FakeIGDBClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.bodies = []

    async def query(self, endpoint: str, body: str):
        assert endpoint == "games"
        assert "limit 500" in body
        self.calls += 1
        self.bodies.append(body)
        return [self.payload] if self.calls == 1 else []


class FailingAfterFirstBatchClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    async def query(self, endpoint: str, body: str):
        assert endpoint == "games"
        self.calls += 1
        if self.calls == 1:
            return [self.payload]
        raise RuntimeError("temporary IGDB failure")


class EmptyIGDBClient:
    def __init__(self):
        self.bodies = []

    async def query(self, endpoint: str, body: str):
        assert endpoint == "games"
        self.bodies.append(body)
        return []


def test_importer_is_idempotent_and_resumable(session_factory, elden_ring_payload) -> None:
    first_client = FakeIGDBClient(elden_ring_payload)
    assert (
        asyncio.run(
            sync_games_from_igdb(
                first_client,
                session_factory=session_factory,
                full=True,
            )
        )
        == 1
    )

    second_client = FakeIGDBClient(elden_ring_payload)
    assert (
        asyncio.run(
            sync_games_from_igdb(
                second_client,
                session_factory=session_factory,
                full=True,
            )
        )
        == 1
    )

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Game)) == 1
        names = db.scalar(select(func.count()).select_from(GameName))
        assert names == 5
        state = db.scalar(select(SyncState).where(SyncState.source == "IGDB"))
        assert state is not None
        assert state.last_processed_id == elden_ring_payload["id"]
        assert state.last_sync_at is not None


def test_importer_can_start_after_an_explicit_igdb_id(session_factory, elden_ring_payload) -> None:
    client = FakeIGDBClient(elden_ring_payload)

    imported = asyncio.run(
        sync_games_from_igdb(
            client,
            session_factory=session_factory,
            after_id=100_000,
        )
    )

    assert imported == 1
    assert "where id > 100000; sort id asc" in client.bodies[0]
    assert "version_parent" not in client.bodies[0]
    assert "offset" not in client.bodies[0]

    with session_factory() as db:
        state = db.scalar(select(SyncState).where(SyncState.source == "IGDB"))
        assert state is not None
        assert state.last_processed_id == elden_ring_payload["id"]


def test_importer_rejects_conflicting_start_options(session_factory, elden_ring_payload) -> None:
    client = FakeIGDBClient(elden_ring_payload)

    try:
        asyncio.run(
            sync_games_from_igdb(
                client,
                session_factory=session_factory,
                full=True,
                after_id=100_000,
            )
        )
    except ValueError as exc:
        assert "함께 사용할 수 없습니다" in str(exc)
    else:
        raise AssertionError("full과 after_id를 함께 사용하면 실패해야 합니다.")


def test_importer_keeps_last_committed_batch_after_failure(
    session_factory,
    elden_ring_payload,
) -> None:
    failing_client = FailingAfterFirstBatchClient(elden_ring_payload)

    try:
        asyncio.run(
            sync_games_from_igdb(
                failing_client,
                session_factory=session_factory,
                full=True,
            )
        )
    except RuntimeError as exc:
        assert "temporary IGDB failure" in str(exc)
    else:
        raise AssertionError("두 번째 IGDB 요청은 실패해야 합니다.")

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Game)) == 1
        state = db.scalar(select(SyncState).where(SyncState.source == "IGDB"))
        assert state is not None
        assert state.last_processed_id == elden_ring_payload["id"]

    resume_client = EmptyIGDBClient()
    assert (
        asyncio.run(
            sync_games_from_igdb(
                resume_client,
                session_factory=session_factory,
            )
        )
        == 0
    )
    assert f"where id > {elden_ring_payload['id']};" in resume_client.bodies[0]
