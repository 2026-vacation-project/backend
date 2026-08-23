import asyncio
from types import SimpleNamespace

import discord
from fastapi import BackgroundTasks

import discord_notifications
import discord_gateway
from discord_gateway import NotificationSettingsView, _toggle_notification_preference
import models
import schemas
from routers import auth


def test_settings_message_is_an_embed_with_a_gateway_button() -> None:
    payload = discord_notifications.settings_message_payload(False)

    assert payload["embeds"][0]["title"] == "팀모아 알림 설정"
    assert payload["components"][0]["components"][0]["custom_id"] == (
        discord_notifications.NOTIFICATION_TOGGLE_CUSTOM_ID
    )
    assert "user" not in payload["components"][0]["components"][0]["custom_id"]

    view = NotificationSettingsView(False)
    assert view.is_persistent()
    assert isinstance(view.children[0], discord.ui.Button)
    assert view.children[0].custom_id == discord_notifications.NOTIFICATION_TOGGLE_CUSTOM_ID


def test_gateway_toggle_uses_the_interaction_discord_user(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(discord_gateway.database, "SessionLocal", session_factory)
    with session_factory() as db:
        expected_user = models.User(
            id="G-1",
            email="expected@example.com",
            name="Expected",
            notifications_enabled=False,
            discord_user_id="discord-expected",
        )
        other_user = models.User(
            id="G-2",
            email="other@example.com",
            name="Other",
            notifications_enabled=False,
            discord_user_id="discord-other",
        )
        db.add_all([expected_user, other_user])
        db.commit()

    result = _toggle_notification_preference("discord-expected", "channel-1", "message-1")

    assert result == ("G-1", True)
    with session_factory() as db:
        expected_user = db.get(models.User, "G-1")
        other_user = db.get(models.User, "G-2")
        assert expected_user.notifications_enabled is True
        assert expected_user.discord_notification_channel_id == "channel-1"
        assert expected_user.discord_notification_message_id == "message-1"
        assert other_user.notifications_enabled is False


def test_gateway_toggle_ignores_unlinked_discord_user(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(discord_gateway.database, "SessionLocal", session_factory)
    assert _toggle_notification_preference("discord-unknown", "channel-1", "message-1") is None


def test_link_and_unlink_reset_discord_notification_state(session_factory, monkeypatch) -> None:
    async def discord_user_info(_provider: str, _code: str) -> dict[str, str | None]:
        return {
            "email": "discord@example.com",
            "name": "Discord user",
            "display_name": "Discord user",
            "profile_image": None,
            "provider_user_id": "discord-user-id",
        }

    monkeypatch.setattr(auth.utils, "fetch_oauth_user_info", discord_user_info)

    with session_factory() as db:
        user = models.User(id="G-1", email="user@example.com", name="사용자")
        db.add(user)
        db.commit()

        link_tasks = BackgroundTasks()
        asyncio.run(
            auth.link_discord(
                schemas.OAuthLoginRequest(code="discord-code"),
                link_tasks,
                current_user_id=user.id,
                db=db,
            )
        )
        db.refresh(user)

        assert user.discord_user_id == "discord-user-id"
        assert link_tasks.tasks[-1].func is discord_notifications.sync_settings_message

        user.notifications_enabled = True
        user.discord_notification_channel_id = "dm-channel"
        user.discord_notification_message_id = "settings-message"
        db.commit()

        unlink_tasks = BackgroundTasks()
        auth.unlink_discord(unlink_tasks, current_user_id=user.id, db=db)
        db.refresh(user)

        assert user.discord_user_id is None
        assert user.notifications_enabled is False
        assert user.discord_notification_channel_id is None
        assert user.discord_notification_message_id is None
        assert unlink_tasks.tasks[0].func is discord_notifications.disable_settings_message


def test_settings_sync_edits_the_stored_message(session_factory, monkeypatch) -> None:
    requests = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def request(self, method, url, json):
            requests.append((method, url, json))
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "settings-message"})

    with session_factory() as db:
        db.add(
            models.User(
                id="G-1",
                email="user@example.com",
                name="사용자",
                notifications_enabled=True,
                discord_user_id="discord-user",
                discord_notification_channel_id="dm-channel",
                discord_notification_message_id="settings-message",
            )
        )
        db.commit()

    monkeypatch.setattr(discord_notifications, "DISCORD_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(discord_notifications.database, "SessionLocal", session_factory)
    monkeypatch.setattr(discord_notifications.httpx, "Client", FakeClient)

    discord_notifications.sync_settings_message("G-1")

    assert len(requests) == 1
    method, url, payload = requests[0]
    assert method == "PATCH"
    assert url.endswith("/channels/dm-channel/messages/settings-message")
    assert payload["components"][0]["components"][0]["label"] == "알림 끄기"
