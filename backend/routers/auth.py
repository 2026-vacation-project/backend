from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
import database, discord_notifications, models, schemas, utils
from room_lifecycle import remove_room_participant

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


def _provider_id_prefix(provider: str) -> str:
    normalized_provider = provider.lower()
    if normalized_provider == "google":
        return "G-"
    if normalized_provider == "discord":
        return "D-"
    raise HTTPException(status_code=400, detail="지원하지 않는 로그인 제공자입니다.")

@router.post("/login/{provider}", response_model=schemas.TokenResponse)
async def login_or_register(
    provider: str,
    req: schemas.OAuthLoginRequest,
    db: Session = Depends(database.get_db),
    background_tasks: BackgroundTasks = None,
):
    provider_prefix = _provider_id_prefix(provider)
    user_info = await utils.fetch_oauth_user_info(provider, req.code)
    discord_user_id = user_info.get("provider_user_id") if provider.lower() == "discord" else None

    user = None
    if discord_user_id:
        user = db.query(models.User).filter(models.User.discord_user_id == discord_user_id).first()
    if not user:
        user = (
            db.query(models.User)
            .filter(
                models.User.email == user_info["email"],
                models.User.id.like(f"{provider_prefix}%"),
            )
            .first()
        )
    if not user:
        custom_id = utils.generate_custom_id(provider)
        user = models.User(
            id=custom_id,
            email=user_info["email"],
            name=user_info["name"],
            display_name=user_info.get("display_name") or user_info["name"],
            profile_image=user_info["profile_image"],
            discord_user_id=discord_user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.name = user_info["name"]
        user.display_name = user_info.get("display_name") or user_info["name"]
        user.profile_image = user_info["profile_image"]
        if discord_user_id and user.discord_user_id != discord_user_id:
            user.discord_notification_channel_id = None
            user.discord_notification_message_id = None
            user.discord_user_id = discord_user_id
        db.commit()

    if discord_user_id:
        if background_tasks is not None:
            background_tasks.add_task(discord_notifications.sync_settings_message, user.id)
        else:
            discord_notifications.sync_settings_message(user.id)

    access_token = utils.create_access_token(data={"sub": user.id, "ver": user.auth_version})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/discord/link", response_model=schemas.UserResponse)
async def link_discord(
    req: schemas.OAuthLoginRequest,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    user_info = await utils.fetch_oauth_user_info("discord", req.code)
    discord_user_id = user_info.get("provider_user_id")
    if not discord_user_id:
        raise HTTPException(status_code=400, detail="Discord 계정 정보를 확인하지 못했습니다.")

    owner = (
        db.query(models.User)
        .filter(
            models.User.discord_user_id == discord_user_id,
            models.User.id != current_user_id,
        )
        .first()
    )
    if owner:
        raise HTTPException(status_code=409, detail="이미 다른 팀모아 계정에 연결된 Discord 계정입니다.")

    user = db.get(models.User, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    previous_channel_id = None
    previous_message_id = None
    if user.discord_user_id != discord_user_id:
        previous_channel_id = user.discord_notification_channel_id
        previous_message_id = user.discord_notification_message_id
        user.discord_notification_channel_id = None
        user.discord_notification_message_id = None
    user.discord_user_id = str(discord_user_id)
    db.commit()
    db.refresh(user)

    if previous_channel_id and previous_message_id:
        background_tasks.add_task(
            discord_notifications.disable_settings_message,
            previous_channel_id,
            previous_message_id,
        )
    background_tasks.add_task(discord_notifications.sync_settings_message, user.id)
    return user


@router.delete("/discord/link", response_model=schemas.UserResponse)
def unlink_discord(
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    user = db.get(models.User, current_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    channel_id = user.discord_notification_channel_id
    message_id = user.discord_notification_message_id
    user.discord_user_id = None
    user.discord_notification_channel_id = None
    user.discord_notification_message_id = None
    user.notifications_enabled = False
    db.commit()
    db.refresh(user)
    background_tasks.add_task(discord_notifications.disable_settings_message, channel_id, message_id)
    return user


@router.post("/logout-all", response_model=schemas.LogoutAllResponse)
def logout_all(
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    rooms = (
        db.query(models.Room)
        .join(
            models.room_participants,
            models.room_participants.c.room_id == models.Room.id,
        )
        .options(selectinload(models.Room.participants))
        .filter(models.room_participants.c.user_id == current_user_id)
        .order_by(models.Room.id)
        .with_for_update()
        .all()
    )

    deleted_room_count = 0
    for room in rooms:
        if remove_room_participant(db, room, user):
            deleted_room_count += 1

    user.auth_version += 1
    user.fcm_token = None
    db.commit()

    return {
        "message": "모든 기기에서 로그아웃했습니다.",
        "left_room_count": len(rooms),
        "deleted_room_count": deleted_room_count,
    }
