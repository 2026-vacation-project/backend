from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
import database, discord_notifications, models, schemas, utils

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


def _get_user_or_404(user_id: str, db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return user


def _require_same_user(user_id: str, current_user_id: str) -> None:
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="본인의 정보만 수정할 수 있습니다.")


@router.get("", response_model=list[schemas.UserResponse])
def list_users(
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return db.query(models.User).order_by(models.User.name, models.User.id).all()


@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(
    user_id: str,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return _get_user_or_404(user_id, db)


@router.patch("/{user_id}/fcm-token")
def update_user_fcm_token(
    user_id: str,
    data: schemas.FCMTokenUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    installation_id = data.fcm_token.strip() or None
    if installation_id:
        (
            db.query(models.User)
            .filter(
                models.User.id != user_id,
                models.User.fcm_token == installation_id,
            )
            .update({models.User.fcm_token: None}, synchronize_session=False)
        )
    user.fcm_token = installation_id
    db.commit()
    return {"message": "FCM 토큰이 저장되었습니다."}


@router.patch("/{user_id}/notification-preference", response_model=schemas.UserResponse)
def update_notification_preference(
    user_id: str,
    data: schemas.NotificationPreferenceUpdate,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    user.notifications_enabled = data.enabled
    db.commit()
    db.refresh(user)
    if user.discord_user_id:
        background_tasks.add_task(discord_notifications.sync_settings_message, user.id)
    return user


@router.patch("/{user_id}/preferences")
def update_user_preferences(
    user_id: str,
    data: schemas.PreferencesUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    user = _get_user_or_404(user_id, db)
    user.preferred_games = data.preferred_games
    db.commit()
    return {"message": "선호 게임 정보가 업데이트되었습니다."}


# 기존 클라이언트와의 하위 호환용 경로
@router.patch("/fcm-token", include_in_schema=False)
def update_current_user_fcm_token(
    data: schemas.FCMTokenUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return update_user_fcm_token(current_user_id, data, current_user_id, db)


@router.patch("/preferences", include_in_schema=False)
def update_current_user_preferences(
    data: schemas.PreferencesUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return update_user_preferences(current_user_id, data, current_user_id, db)
