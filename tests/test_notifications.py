from types import SimpleNamespace

from fastapi import BackgroundTasks

import models
import schemas
import utils
import discord_notifications
from routers.rooms import _queue_notifications, join_room
from routers.users import update_user_fcm_token


def _user(user_id: str, name: str, installation_id: str | None) -> models.User:
    return models.User(
        id=user_id,
        email=f"{user_id}@example.com",
        name=name,
        fcm_token=installation_id,
        notifications_enabled=True,
        preferred_games=[],
    )


def test_send_fcm_notification_uses_fids_and_room_link(monkeypatch) -> None:
    captured = []

    def fake_send(message, *, app):
        captured.append((message, app))
        return SimpleNamespace(
            success_count=len(message.fids),
            responses=[SimpleNamespace(success=True, exception=None) for _ in message.fids],
        )

    monkeypatch.setattr(utils, "_get_firebase_app", lambda: "firebase-app")
    monkeypatch.setattr(utils.messaging, "send_each_for_multicast", fake_send)

    success_count = utils.send_fcm_notification(
        ["fid-1", "fid-1", "fid-2"],
        "모집이 완료됐어요",
        "두 명이 모두 모였어요",
        "https://teammoa.example/rooms/10?group=1",
    )

    assert success_count == 2
    assert len(captured) == 1
    message, app = captured[0]
    assert app == "firebase-app"
    assert message.fids == ["fid-1", "fid-2"]
    assert message.tokens is None
    assert message.notification.title == "모집이 완료됐어요"
    assert message.webpush.fcm_options.link == "https://teammoa.example/rooms/10?group=1"


def test_http_link_does_not_block_local_notification(monkeypatch) -> None:
    captured = []

    def fake_send(message, *, app):
        captured.append((message, app))
        return SimpleNamespace(
            success_count=1,
            responses=[SimpleNamespace(success=True, exception=None)],
        )

    monkeypatch.setattr(utils, "_get_firebase_app", lambda: "firebase-app")
    monkeypatch.setattr(utils.messaging, "send_each_for_multicast", fake_send)

    success_count = utils.send_fcm_notification(
        ["fid-1"],
        "모집이 완료됐어요",
        "두 명이 모두 모였어요",
        "http://localhost:3000/rooms/10?group=1",
    )

    assert success_count == 1
    assert captured[0][0].webpush.fcm_options is None
    assert captured[0][0].data == {"url": "http://localhost:3000/rooms/10?group=1"}


def test_completed_room_notifies_every_participant(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(utils, "FRONTEND_BASE_URL", "https://teammoa.example")

    with session_factory() as db:
        host = _user("host", "방장", "fid-host")
        guest = _user("guest", "참가자", "fid-guest")
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.extend([host, guest])
        room = models.Room(
            id=10,
            group=group,
            host_id=host.id,
            game_name="Minecraft",
            target_count=2,
        )
        room.participants.append(host)
        db.add_all([group, room])
        db.commit()

        background_tasks = BackgroundTasks()
        join_room(
            group_id=group.id,
            room_id=room.id,
            background_tasks=background_tasks,
            user_id=guest.id,
            current_user_id=guest.id,
            db=db,
        )

        db.refresh(room)

    assert room.status == models.RoomStatus.COMPLETED
    assert len(background_tasks.tasks) == 1
    task = background_tasks.tasks[0]
    assert task.func is utils.send_fcm_notification
    assert task.args[0] == ["fid-host", "fid-guest"]
    assert task.args[1] == "모집이 완료됐어요"
    assert task.args[3] == "https://teammoa.example/rooms/10?group=1"


def test_installation_id_moves_to_the_current_user(session_factory) -> None:
    with session_factory() as db:
        previous_user = _user("previous", "이전 사용자", "shared-fid")
        current_user = _user("current", "현재 사용자", None)
        db.add_all([previous_user, current_user])
        db.commit()

        update_user_fcm_token(
            user_id=current_user.id,
            data=schemas.FCMTokenUpdate(fcm_token="shared-fid"),
            current_user_id=current_user.id,
            db=db,
        )
        db.expire_all()

        assert db.get(models.User, previous_user.id).fcm_token is None
        assert db.get(models.User, current_user.id).fcm_token == "shared-fid"


def test_notification_routing_prefers_fcm_and_uses_discord_only_without_fcm() -> None:
    fcm_user = _user("fcm", "FCM 사용자", "fid-fcm")
    fcm_user.discord_user_id = "discord-fcm"
    discord_user = _user("discord", "Discord 사용자", None)
    discord_user.discord_user_id = "discord-only"
    disabled_user = _user("disabled", "꺼진 사용자", None)
    disabled_user.discord_user_id = "discord-disabled"
    disabled_user.notifications_enabled = False
    background_tasks = BackgroundTasks()

    _queue_notifications(
        background_tasks,
        [fcm_user, discord_user, disabled_user],
        "새 모집",
        "모집 내용",
        "https://teammoa.example/rooms/10?group=1",
    )

    assert len(background_tasks.tasks) == 2
    fcm_task, discord_task = background_tasks.tasks
    assert fcm_task.func is utils.send_fcm_notification
    assert fcm_task.args[0] == ["fid-fcm"]
    assert discord_task.func is discord_notifications.send_discord_notifications
    assert discord_task.args[0] == ["discord-only"]
