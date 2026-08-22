from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups", tags=["Groups"])


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


def _get_current_user_or_404(current_user_id: str, db: Session) -> models.User:
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return user


def _require_same_user(user_id: str | None, current_user_id: str) -> None:
    if user_id is not None and user_id != current_user_id:
        raise HTTPException(status_code=403, detail="다른 사용자를 대신해 요청할 수 없습니다.")


def _require_group_member(group: models.Group, current_user_id: str) -> None:
    if not any(member.id == current_user_id for member in group.members):
        raise HTTPException(status_code=403, detail="그룹 멤버만 수행할 수 있습니다.")


@router.get("", response_model=list[schemas.GroupResponse])
def list_groups(
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return (
        db.query(models.Group)
        .options(selectinload(models.Group.members))
        .filter(
            models.Group.is_public.is_(True)
            | models.Group.members.any(models.User.id == current_user_id)
        )
        .order_by(models.Group.created_at.desc(), models.Group.id.desc())
        .all()
    )


@router.get("/{group_id}", response_model=schemas.GroupResponse)
def get_group(
    group_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return _get_group_or_404(group_id, db)


@router.post("", response_model=schemas.GroupResponse)
def create_group(
    group_in: schemas.GroupCreate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    user = _get_current_user_or_404(current_user_id, db)
    group = models.Group(
        id=utils.snowflake.generate_id(),
        name=group_in.name.strip(),
        is_public=group_in.is_public,
    )
    group.members.append(user)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.patch("/{group_id}/visibility", response_model=schemas.GroupResponse)
def update_group_visibility(
    group_id: int,
    visibility_in: schemas.GroupVisibilityUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    group.is_public = visibility_in.is_public
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    db.delete(group)
    db.commit()
    return {"message": "그룹이 삭제되었습니다."}

@router.post("/{group_id}/join")
def join_group(
    group_id: int,
    user_id: str | None = None,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    group = _get_group_or_404(group_id, db)
    user = _get_current_user_or_404(current_user_id, db)

    if not any(member.id == current_user_id for member in group.members):
        group.members.append(user)
        db.commit()
    return {"message": "그룹에 참여했습니다."}


@router.post("/{group_id}/leave")
def leave_group(
    group_id: int,
    user_id: str | None = None,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    group = _get_group_or_404(group_id, db)
    user = _get_current_user_or_404(current_user_id, db)

    if not any(member.id == current_user_id for member in group.members):
        raise HTTPException(status_code=400, detail="참여하지 않은 그룹입니다.")

    group.members.remove(user)
    db.commit()
    return {"message": "그룹에서 나왔습니다."}
