from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups", tags=["Groups"])

@router.post("", response_model=schemas.GroupResponse)
def create_group(
    group_in: schemas.GroupCreate, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    group = models.Group(name=group_in.name)
    group.members.append(user)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group

@router.delete("/{group_id}")
def delete_group(
    group_id: int, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    db.delete(group)
    db.commit()
    return {"message": "그룹이 삭제되었습니다."}

@router.post("/{group_id}/join")
def join_group(
    group_id: int, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not group or not user:
        raise HTTPException(status_code=404, detail="그룹 또는 유저를 찾을 수 없습니다.")
    
    if user not in group.members:
        group.members.append(user)
        db.commit()
    return {"message": "그룹에 참여했습니다."}