import asyncio
import logging
import os
import sys

import discord

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

import database
import discord_notifications
import models


logger = logging.getLogger(__name__)


def _toggle_notification_preference(
    discord_user_id: str,
    channel_id: str | None,
    message_id: str | None,
) -> tuple[str, bool] | None:
    """Toggle by the authenticated Discord actor, never by component data."""
    with database.SessionLocal() as db:
        user = (
            db.query(models.User)
            .filter(models.User.discord_user_id == discord_user_id)
            .first()
        )
        if not user:
            return None

        user.notifications_enabled = not user.notifications_enabled
        if channel_id and message_id:
            user.discord_notification_channel_id = channel_id
            user.discord_notification_message_id = message_id
        db.commit()
        return user.id, user.notifications_enabled


def _settings_embed(enabled: bool) -> discord.Embed:
    payload = discord_notifications.settings_message_payload(enabled)
    return discord.Embed.from_dict(payload["embeds"][0])


async def _acknowledge_without_message(interaction: discord.Interaction) -> None:
    if interaction.response.is_done():
        return
    try:
        await interaction.response.defer()
    except discord.HTTPException:
        logger.exception("Discord Interaction acknowledge에 실패했습니다.")


class NotificationSettingsView(discord.ui.View):
    def __init__(self, enabled: bool = False) -> None:
        super().__init__(timeout=None)
        button = discord.ui.Button(
            label="알림 끄기" if enabled else "알림 켜기",
            style=discord.ButtonStyle.secondary if enabled else discord.ButtonStyle.success,
            custom_id=discord_notifications.NOTIFICATION_TOGGLE_CUSTOM_ID,
        )
        button.callback = self.toggle_notifications
        self.add_item(button)

    async def toggle_notifications(self, interaction: discord.Interaction) -> None:
        message = interaction.message
        channel_id = str(message.channel.id) if message else None
        message_id = str(message.id) if message else None

        try:
            result = await asyncio.to_thread(
                _toggle_notification_preference,
                str(interaction.user.id),
                channel_id,
                message_id,
            )
            if not result:
                await _acknowledge_without_message(interaction)
                return

            user_id, enabled = result
            try:
                await interaction.response.edit_message(
                    embed=_settings_embed(enabled),
                    view=NotificationSettingsView(enabled),
                )
            except discord.HTTPException:
                await _acknowledge_without_message(interaction)
                await asyncio.to_thread(discord_notifications.sync_settings_message, user_id)
        except Exception:
            logger.exception("Discord 알림 설정 버튼 처리에 실패했습니다.")
            await _acknowledge_without_message(interaction)


class TeammoaDiscordClient(discord.Client):
    async def setup_hook(self) -> None:
        self.add_view(NotificationSettingsView())

    async def on_ready(self) -> None:
        logger.info("Discord Gateway 연결 완료: bot=%s", self.user)


def main() -> None:
    token = discord_notifications.DISCORD_BOT_TOKEN
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN이 설정되어 있지 않습니다.")

    logging.basicConfig(level=logging.INFO)
    client = TeammoaDiscordClient(intents=discord.Intents.default())
    client.run(token)


if __name__ == "__main__":
    main()
