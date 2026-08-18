from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.patch("/fcm-token")
def update_fcm_token(
    data: schemas.FCMTokenUpdate, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    user.fcm_token = data.fcm_token
    db.commit()
    return {"message": "FCM 토큰이 저장되었습니다."}

@router.patch("/preferences")
def update_preferences(
    data: schemas.PreferencesUpdate, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    user.preferred_games = data.preferred_games
    db.commit()
    return {"message": "선호 게임 정보가 업데이트되었습니다."}