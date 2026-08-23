import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket


@dataclass
class RoomConnection:
    user_id: str
    subscriptions: set[int] = field(default_factory=set)


class RoomRealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[WebSocket, RoomConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        async with self._lock:
            self._connections[websocket] = RoomConnection(user_id=user_id)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.pop(websocket, None)

    async def set_subscriptions(self, websocket: WebSocket, group_ids: set[int]) -> None:
        async with self._lock:
            connection = self._connections.get(websocket)
            if connection:
                connection.subscriptions = group_ids

    async def broadcast_room_change(
        self,
        group_id: int,
        room_id: int | None,
        change: str,
        allowed_user_ids: set[str] | None = None,
    ) -> None:
        async with self._lock:
            targets = [
                websocket
                for websocket, connection in self._connections.items()
                if group_id in connection.subscriptions
                and (allowed_user_ids is None or connection.user_id in allowed_user_ids)
            ]

        if not targets:
            return

        payload = {
            "type": "room.changed",
            "group_id": str(group_id),
            "room_id": str(room_id) if room_id is not None else None,
            "change": change,
        }
        results = await asyncio.gather(
            *(websocket.send_json(payload) for websocket in targets),
            return_exceptions=True,
        )
        stale = [websocket for websocket, result in zip(targets, results, strict=True) if isinstance(result, Exception)]
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.pop(websocket, None)

    async def disconnect_user(self, user_id: str) -> None:
        async with self._lock:
            targets = [
                websocket
                for websocket, connection in self._connections.items()
                if connection.user_id == user_id
            ]
            for websocket in targets:
                self._connections.pop(websocket, None)

        await asyncio.gather(
            *(websocket.close(code=4001, reason="로그인 세션이 종료됐습니다.") for websocket in targets),
            return_exceptions=True,
        )


room_realtime = RoomRealtimeManager()


def _allowed_realtime_user_ids(group_id: int) -> set[str] | None:
    import database
    import models

    with database.SessionLocal() as db:
        group = db.get(models.Group, group_id)
        if not group or group.is_public:
            return None
        rows = db.query(models.group_members.c.user_id).filter(models.group_members.c.group_id == group_id).all()
    return {str(row[0]) for row in rows}


async def broadcast_room_change(group_id: int, room_id: int | None, change: str) -> None:
    allowed_user_ids = await asyncio.to_thread(_allowed_realtime_user_ids, group_id)
    await room_realtime.broadcast_room_change(group_id, room_id, change, allowed_user_ids)


async def disconnect_user(user_id: str) -> None:
    await room_realtime.disconnect_user(user_id)
