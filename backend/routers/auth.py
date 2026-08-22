from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
import models, schemas, database, utils
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
async def login_or_register(provider: str, req: schemas.OAuthLoginRequest, db: Session = Depends(database.get_db)):
    provider_prefix = _provider_id_prefix(provider)
    user_info = await utils.fetch_oauth_user_info(provider, req.code)

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
            profile_image=user_info["profile_image"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.name = user_info["name"]
        user.profile_image = user_info["profile_image"]
        db.commit()

    access_token = utils.create_access_token(data={"sub": user.id, "ver": user.auth_version})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }


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
