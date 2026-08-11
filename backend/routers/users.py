from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas, database

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

@router.get("", response_model=List[schemas.UserResponse])
def get_users(db: Session = Depends(database.get_db)):
    users = db.query(models.User).all()
    for u in users:
        if u.preferred_games is None:
            u.preferred_games = []
    return users

@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: str, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    if user.preferred_games is None:
        user.preferred_games = []
    return user

@router.patch("/{user_id}/fcm-token")
def update_fcm_token(user_id: str, data: schemas.FCMTokenUpdate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    user.fcm_token = data.fcm_token
    db.commit()
    return {"message": "FCM 토큰이 저장되었습니다."}

@router.patch("/{user_id}/preferences")
def update_preferences(user_id: str, data: schemas.PreferencesUpdate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    user.preferred_games = data.preferred_games
    db.commit()
    return {"message": "선호 게임 정보가 업데이트되었습니다."}