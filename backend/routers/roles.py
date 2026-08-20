from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups/{group_id}/roles", tags=["Roles"])


def _get_group_or_404(group_id: int, db: Session) -> models.Group:
    group = (
        db.query(models.Group)
        .options(selectinload(models.Group.members))
        .filter(models.Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    return group


def _require_group_member(group: models.Group, current_user_id: str) -> None:
    if not any(member.id == current_user_id for member in group.members):
        raise HTTPException(status_code=403, detail="그룹 멤버만 수행할 수 있습니다.")


def _get_role_or_404(group_id: int, role_id: int, db: Session) -> models.Role:
    role = db.query(models.Role).filter(models.Role.id == role_id, models.Role.group_id == group_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="역할을 찾을 수 없습니다.")
    return role


@router.get("", response_model=list[schemas.RoleResponse])
def list_roles(
    group_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _get_group_or_404(group_id, db)
    return db.query(models.Role).filter(models.Role.group_id == group_id).order_by(models.Role.id).all()


@router.post("", response_model=schemas.RoleResponse)
def create_role(
    group_id: int,
    role_in: schemas.RoleCreate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    role = models.Role(
        id=utils.snowflake.generate_id(),
        group_id=group_id,
        name=role_in.name.strip(),
        color=role_in.color.strip(),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role

@router.patch("/{role_id}", response_model=schemas.RoleResponse)
def update_role(
    group_id: int,
    role_id: int,
    role_in: schemas.RoleCreate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    role = _get_role_or_404(group_id, role_id, db)
    role.name = role_in.name.strip()
    role.color = role_in.color.strip()
    db.commit()
    db.refresh(role)
    return role

@router.delete("/{role_id}")
def delete_role(
    group_id: int,
    role_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    role = _get_role_or_404(group_id, role_id, db)
    db.delete(role)
    db.commit()
    return {"message": "역할이 삭제되었습니다."}

@router.post("/{role_id}/assign/{target_user_id}")
def assign_role(
    group_id: int,
    role_id: int,
    target_user_id: str,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    role = _get_role_or_404(group_id, role_id, db)
    user = db.query(models.User).filter(models.User.id == target_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    if not any(member.id == target_user_id for member in group.members):
        raise HTTPException(status_code=400, detail="그룹 멤버에게만 역할을 부여할 수 있습니다.")

    if role not in user.roles:
        user.roles.append(role)
        db.commit()
    return {"message": "유저에게 역할이 부여되었습니다."}
