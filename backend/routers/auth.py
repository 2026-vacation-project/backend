from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

@router.post("/login/{provider}", response_model=schemas.UserResponse)
def login_or_register(provider: str, user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if provider.lower() not in ["google", "discord"]:
        raise HTTPException(status_code=400, detail="유효하지 않은 로그인 제공자입니다.")
    
    user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if not user:
        custom_id = utils.generate_custom_id(provider)
        user = models.User(
            id=custom_id,
            email=user_in.email,
            name=user_in.name,
            profile_image=user_in.profile_image,
            preferred_games=[]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        updated = False
        if user_in.name and user.name != user_in.name:
            user.name = user_in.name
            updated = True
        if user_in.profile_image and user.profile_image != user_in.profile_image:
            user.profile_image = user_in.profile_image
            updated = True
        if updated:
            db.commit()
            db.refresh(user)

    if user.preferred_games is None:
        user.preferred_games = []

    return user