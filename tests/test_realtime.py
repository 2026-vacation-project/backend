import asyncio

import models
from realtime import RoomRealtimeManager
from routers import realtime as realtime_router


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.closed: tuple[int, str] | None = None

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)


def test_room_changes_only_reach_subscribed_sockets() -> None:
    async def scenario() -> tuple[FakeWebSocket, FakeWebSocket]:
        manager = RoomRealtimeManager()
        subscribed = FakeWebSocket()
        other_group = FakeWebSocket()
        await manager.connect(subscribed, "user-1")
        await manager.connect(other_group, "user-2")
        await manager.set_subscriptions(subscribed, {10})
        await manager.set_subscriptions(other_group, {20})

        await manager.broadcast_room_change(10, 100, "participants")
        return subscribed, other_group

    subscribed, other_group = asyncio.run(scenario())

    assert subscribed.messages == [
        {
            "type": "room.changed",
            "group_id": "10",
            "room_id": "100",
            "change": "participants",
        }
    ]
    assert other_group.messages == []


def test_global_logout_disconnects_only_that_users_sockets() -> None:
    async def scenario() -> tuple[FakeWebSocket, FakeWebSocket]:
        manager = RoomRealtimeManager()
        first_device = FakeWebSocket()
        other_user = FakeWebSocket()
        await manager.connect(first_device, "user-1")
        await manager.connect(other_user, "user-2")

        await manager.disconnect_user("user-1")
        return first_device, other_user

    first_device, other_user = asyncio.run(scenario())

    assert first_device.closed == (4001, "로그인 세션이 종료됐습니다.")
    assert other_user.closed is None


def test_socket_subscriptions_only_allow_visible_groups(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(realtime_router.database, "SessionLocal", session_factory)

    with session_factory() as db:
        user = models.User(id="user-1", email="user@example.com", name="사용자")
        public_group = models.Group(id=10, name="공개 그룹", is_public=True)
        private_group = models.Group(id=20, name="비공개 그룹", is_public=False)
        db.add_all([user, public_group, private_group])
        db.commit()

    assert realtime_router._allowed_group_ids(user.id, {10, 20}) == {10}
