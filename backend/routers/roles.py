from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas, database

router = APIRouter(prefix="/api/v1/groups/{group_id}/roles", tags=["Roles"])

@router.get("", response_model=List[schemas.RoleResponse])
def get_roles(group_id: int, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    return db.query(models.Role).filter(models.Role.group_id == group_id).all()

@router.post("", response_model=schemas.RoleResponse)
def create_role(group_id: int, role_in: schemas.RoleCreate, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    role = models.Role(group_id=group_id, name=role_in.name, color=role_in.color)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.patch("/{role_id}", response_model=schemas.RoleResponse)
def update_role(group_id: int, role_id: int, role_in: schemas.RoleCreate, db: Session = Depends(database.get_db)):
    role = db.query(models.Role).filter(models.Role.id == role_id, models.Role.group_id == group_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="역할을 찾을 수 없습니다.")
    role.name = role_in.name
    role.color = role_in.color
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}")
def delete_role(group_id: int, role_id: int, db: Session = Depends(database.get_db)):
    role = db.query(models.Role).filter(models.Role.id == role_id, models.Role.group_id == group_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="역할을 찾을 수 없습니다.")
    db.delete(role)
    db.commit()
    return {"message": "역할이 삭제되었습니다."}

@router.post("/{role_id}/assign/{user_id}")
def assign_role(group_id: int, role_id: int, user_id: str, db: Session = Depends(database.get_db)):
    role = db.query(models.Role).filter(models.Role.id == role_id, models.Role.group_id == group_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not role or not user:
        raise HTTPException(status_code=404, detail="역할 또는 유저를 찾을 수 없습니다.")
    
    if role not in user.roles:
        user.roles.append(role)
        db.commit()
    return {"message": "유저에게 역할이 부여되었습니다."}