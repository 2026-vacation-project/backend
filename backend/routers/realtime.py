import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

import database
import models
import realtime as room_realtime
import utils


router = APIRouter(tags=["Realtime"])
AUTHENTICATION_TIMEOUT_SECONDS = 5
MAX_GROUP_SUBSCRIPTIONS = 100


def _allowed_group_ids(user_id: str, requested_ids: set[int]) -> set[int]:
    if not requested_ids:
        return set()
    with database.SessionLocal() as db:
        rows = (
            db.query(models.Group.id)
            .filter(
                models.Group.id.in_(requested_ids),
                models.Group.is_public.is_(True) | models.Group.members.any(models.User.id == user_id),
            )
            .all()
        )
    return {int(row[0]) for row in rows}


def _authenticate(token: str) -> str:
    with database.SessionLocal() as db:
        return utils.resolve_access_token(token, db)


@router.websocket("/api/v1/ws/rooms")
async def rooms_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connected = False
    try:
        try:
            message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=AUTHENTICATION_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            await websocket.close(code=1008, reason="인증 시간이 초과됐습니다.")
            return

        token = message.get("token") if isinstance(message, dict) and message.get("type") == "authenticate" else None
        if not isinstance(token, str) or not token:
            await websocket.close(code=1008, reason="로그인이 필요합니다.")
            return

        try:
            user_id = await asyncio.to_thread(_authenticate, token)
        except HTTPException:
            await websocket.close(code=1008, reason="로그인이 유효하지 않습니다.")
            return

        await room_realtime.room_realtime.connect(websocket, user_id)
        connected = True
        await websocket.send_json({"type": "ready"})

        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                continue

            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message_type != "subscribe":
                continue

            raw_group_ids = message.get("group_ids")
            if not isinstance(raw_group_ids, list) or len(raw_group_ids) > MAX_GROUP_SUBSCRIPTIONS:
                await websocket.send_json({"type": "error", "message": "그룹 구독 정보를 확인해 주세요."})
                continue
            try:
                requested_ids = {int(group_id) for group_id in raw_group_ids}
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "message": "그룹 구독 정보를 확인해 주세요."})
                continue

            allowed_ids = await asyncio.to_thread(_allowed_group_ids, user_id, requested_ids)
            await room_realtime.room_realtime.set_subscriptions(websocket, allowed_ids)
            await websocket.send_json(
                {"type": "subscribed", "group_ids": [str(group_id) for group_id in sorted(allowed_ids)]}
            )
    except WebSocketDisconnect:
        pass
    finally:
        if connected:
            await room_realtime.room_realtime.disconnect(websocket)
