import logging
import os
from typing import Any

import httpx

import database
import models


DISCORD_API_BASE_URL = "https://discord.com/api/v10"
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
NOTIFICATION_TOGGLE_CUSTOM_ID = "teammoa:notifications:toggle"
TEAMMOA_BLUE = 0x165DCC

logger = logging.getLogger(__name__)


def settings_message_payload(enabled: bool, *, connected: bool = True) -> dict[str, Any]:
    if connected:
        state = "켜짐" if enabled else "꺼짐"
        description = (
            f"현재 알림은 **{state}** 상태예요.\n"
            "아래 버튼으로 팀모아의 새 모집과 모집 완료 알림을 켜거나 끌 수 있어요."
        )
        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 2 if enabled else 3,
                        "label": "알림 끄기" if enabled else "알림 켜기",
                        "custom_id": NOTIFICATION_TOGGLE_CUSTOM_ID,
                    }
                ],
            }
        ]
    else:
        description = "팀모아와 Discord 연결이 해제되어 이 메시지에서 알림을 변경할 수 없어요."
        components = []

    return {
        "embeds": [
            {
                "title": "팀모아 알림 설정",
                "description": description,
                "color": TEAMMOA_BLUE,
                "fields": [
                    {
                        "name": "전송 방식",
                        "value": "웹 푸시가 설정되어 있으면 FCM으로만, 설정되어 있지 않으면 Discord DM으로 보내요.",
                    }
                ],
                "footer": {"text": "이 설정은 팀모아 웹의 알림 설정과 함께 적용돼요."},
            }
        ],
        "components": components,
        "allowed_mentions": {"parse": []},
    }


def notification_message_payload(title: str, body: str, link: str | None = None) -> dict[str, Any]:
    embed: dict[str, Any] = {
        "title": title[:256],
        "description": body[:4096],
        "color": TEAMMOA_BLUE,
        "footer": {"text": "팀모아 알림"},
    }
    if link:
        embed["url"] = link
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _request(client: httpx.Client, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = client.request(method, f"{DISCORD_API_BASE_URL}{path}", json=payload)
    response.raise_for_status()
    return response.json()


def _open_dm(client: httpx.Client, discord_user_id: str) -> str:
    channel = _request(client, "POST", "/users/@me/channels", {"recipient_id": discord_user_id})
    return str(channel["id"])


def sync_settings_message(user_id: str) -> None:
    """Create or update one durable settings DM without surfacing Discord failures."""
    if not DISCORD_BOT_TOKEN:
        logger.info("Discord 설정 메시지를 건너뜁니다: DISCORD_BOT_TOKEN이 없습니다.")
        return

    try:
        with database.SessionLocal() as db:
            user = db.get(models.User, user_id)
            if not user or not user.discord_user_id:
                return

            headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
            payload = settings_message_payload(user.notifications_enabled)
            with httpx.Client(headers=headers, timeout=10.0) as client:
                if user.discord_notification_channel_id and user.discord_notification_message_id:
                    try:
                        _request(
                            client,
                            "PATCH",
                            (
                                f"/channels/{user.discord_notification_channel_id}"
                                f"/messages/{user.discord_notification_message_id}"
                            ),
                            payload,
                        )
                        return
                    except httpx.HTTPStatusError as error:
                        if error.response.status_code != 404:
                            raise

                channel_id = user.discord_notification_channel_id or _open_dm(client, user.discord_user_id)
                message = _request(client, "POST", f"/channels/{channel_id}/messages", payload)
                user.discord_notification_channel_id = channel_id
                user.discord_notification_message_id = str(message["id"])
                db.commit()
    except Exception:
        logger.exception("Discord 알림 설정 DM을 만들거나 수정하지 못했습니다: user_id=%s", user_id)


def disable_settings_message(channel_id: str | None, message_id: str | None) -> None:
    if not DISCORD_BOT_TOKEN or not channel_id or not message_id:
        return
    try:
        with httpx.Client(
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            timeout=10.0,
        ) as client:
            _request(
                client,
                "PATCH",
                f"/channels/{channel_id}/messages/{message_id}",
                settings_message_payload(False, connected=False),
            )
    except Exception:
        logger.exception("연결 해제된 Discord 알림 설정 DM을 수정하지 못했습니다.")


def send_discord_notifications(
    discord_user_ids: list[str],
    title: str,
    body: str,
    link: str | None = None,
) -> int:
    targets = list(dict.fromkeys(target.strip() for target in discord_user_ids if target.strip()))
    if not targets or not DISCORD_BOT_TOKEN:
        return 0

    success_count = 0
    payload = notification_message_payload(title, body, link)
    try:
        with httpx.Client(
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            timeout=10.0,
        ) as client:
            for discord_user_id in targets:
                try:
                    channel_id = _open_dm(client, discord_user_id)
                    _request(client, "POST", f"/channels/{channel_id}/messages", payload)
                    success_count += 1
                except Exception:
                    logger.exception("Discord DM 알림 전송 실패: discord_user_id=%s", discord_user_id)
    except Exception:
        logger.exception("Discord DM 알림 처리를 시작하지 못했습니다.")

    logger.info("Discord DM 알림 전송 완료: success=%d total=%d", success_count, len(targets))
    return success_count
