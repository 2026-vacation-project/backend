from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas, database

router = APIRouter(prefix="/api/v1/groups", tags=["Groups"])

@router.get("", response_model=List[schemas.GroupResponse])
def get_groups(db: Session = Depends(database.get_db)):
    return db.query(models.Group).all()

@router.get("/{group_id}", response_model=schemas.GroupResponse)
def get_group(group_id: int, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    return group

@router.post("", response_model=schemas.GroupResponse)
def create_group(group_in: schemas.GroupCreate, db: Session = Depends(database.get_db)):
    group = models.Group(name=group_in.name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    db.delete(group)
    db.commit()
    return {"message": "그룹이 삭제되었습니다."}

@router.post("/{group_id}/join")
def join_group(group_id: int, user_id: str, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not group or not user:
        raise HTTPException(status_code=404, detail="그룹 또는 유저를 찾을 수 없습니다.")
    
    if user not in group.members:
        group.members.append(user)
        db.commit()
    return {"message": "그룹에 참여했습니다."}

@router.post("/{group_id}/leave")
def leave_group(group_id: int, user_id: str, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not group or not user:
        raise HTTPException(status_code=404, detail="그룹 또는 유저를 찾을 수 없습니다.")
    
    if user in group.members:
        group.members.remove(user)
        db.commit()
    return {"message": "그룹에서 탈퇴했습니다."}