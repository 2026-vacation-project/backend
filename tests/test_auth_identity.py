import asyncio

import models
import schemas
from routers import auth


def test_same_email_creates_separate_google_and_discord_users(monkeypatch, session_factory) -> None:
    async def discord_user_info(_provider: str, _code: str) -> dict[str, str | None]:
        return {
            "email": "shared@example.com",
            "name": "Discord user",
            "profile_image": None,
        }

    monkeypatch.setattr(auth.utils, "fetch_oauth_user_info", discord_user_info)
    monkeypatch.setattr(auth.utils, "generate_custom_id", lambda _provider: "D-200")

    with session_factory() as db:
        db.add(
            models.User(
                id="G-100",
                email="shared@example.com",
                name="Google user",
            )
        )
        db.commit()

        response = asyncio.run(
            auth.login_or_register(
                "discord",
                schemas.OAuthLoginRequest(code="discord-code"),
                db,
            )
        )

        users = db.query(models.User).order_by(models.User.id).all()

    assert [user.id for user in users] == ["D-200", "G-100"]
    assert response["user"].id == "D-200"


def test_login_reuses_only_the_user_from_the_same_provider(monkeypatch, session_factory) -> None:
    async def discord_user_info(_provider: str, _code: str) -> dict[str, str | None]:
        return {
            "email": "shared@example.com",
            "name": "Updated Discord user",
            "profile_image": None,
        }

    monkeypatch.setattr(auth.utils, "fetch_oauth_user_info", discord_user_info)
    monkeypatch.setattr(
        auth.utils,
        "generate_custom_id",
        lambda _provider: (_ for _ in ()).throw(AssertionError("A new user must not be created")),
    )

    with session_factory() as db:
        db.add_all(
            [
                models.User(id="G-100", email="shared@example.com", name="Google user"),
                models.User(id="D-200", email="shared@example.com", name="Discord user"),
            ]
        )
        db.commit()

        response = asyncio.run(
            auth.login_or_register(
                "discord",
                schemas.OAuthLoginRequest(code="discord-code"),
                db,
            )
        )

        users = db.query(models.User).order_by(models.User.id).all()

    assert len(users) == 2
    assert response["user"].id == "D-200"
    assert response["user"].name == "Updated Discord user"
