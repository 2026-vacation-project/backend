from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

@router.post("/login/{provider}", response_model=schemas.TokenResponse)
async def login_or_register(provider: str, req: schemas.OAuthLoginRequest, db: Session = Depends(database.get_db)):
    user_info = await utils.fetch_oauth_user_info(provider, req.code)
    
    user = db.query(models.User).filter(models.User.email == user_info["email"]).first()
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

    access_token = utils.create_access_token(data={"sub": user.id})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }