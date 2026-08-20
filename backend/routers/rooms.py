from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups/{group_id}/rooms", tags=["Rooms"])


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


def _get_room_or_404(group_id: int, room_id: int, db: Session) -> models.Room:
    room = (
        db.query(models.Room)
        .options(selectinload(models.Room.participants))
        .filter(models.Room.id == room_id, models.Room.group_id == group_id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    return room


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


@router.get("", response_model=list[schemas.RoomResponse])
def list_rooms(
    group_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _get_group_or_404(group_id, db)
    return (
        db.query(models.Room)
        .options(selectinload(models.Room.participants))
        .filter(models.Room.group_id == group_id)
        .order_by(models.Room.created_at.desc(), models.Room.id.desc())
        .all()
    )


@router.get("/{room_id}", response_model=schemas.RoomResponse)
def get_room(
    group_id: int,
    room_id: int,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    return _get_room_or_404(group_id, room_id, db)


@router.post("", response_model=schemas.RoomResponse)
def create_room(
    group_id: int,
    room_in: schemas.RoomCreate,
    background_tasks: BackgroundTasks,
    host_id: str | None = None,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(host_id, current_user_id)
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    host = _get_current_user_or_404(current_user_id, db)

    room = models.Room(
        id=utils.snowflake.generate_id(),
        group_id=group_id,
        host_id=current_user_id,
        game_name=room_in.game_name.strip(),
        target_count=room_in.target_count,
        target_role=room_in.target_role.strip() if room_in.target_role else None,
        unit_type=room_in.unit_type,
    )
    room.participants.append(host)
    db.add(room)
    db.commit()
    db.refresh(room)

    tokens = [u.fcm_token for u in group.members if u.fcm_token and u.id != current_user_id]
    title = "팀 모집 시작!"
    body = f"{host.name}님이 <{room.game_name}> 팀을 구하고 있어요"
    background_tasks.add_task(utils.send_fcm_notification, tokens, title, body)

    return room

@router.patch("/{room_id}", response_model=schemas.RoomResponse)
def update_room(
    group_id: int,
    room_id: int,
    room_update: schemas.RoomUpdate,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    room = _get_room_or_404(group_id, room_id, db)
    if room.host_id != current_user_id:
        raise HTTPException(status_code=403, detail="방장만 모집방을 수정할 수 있습니다.")

    update_data = room_update.model_dump(exclude_unset=True)
    if "game_name" in update_data and update_data["game_name"] is not None:
        update_data["game_name"] = update_data["game_name"].strip()
    if "target_role" in update_data and update_data["target_role"] is not None:
        update_data["target_role"] = update_data["target_role"].strip() or None
    for key, value in update_data.items():
        setattr(room, key, value)

    if "status" not in update_data and room.status != models.RoomStatus.CANCELLED:
        room.status = (
            models.RoomStatus.COMPLETED
            if len(room.participants) >= room.target_count
            else models.RoomStatus.RECRUITING
        )

    db.commit()
    db.refresh(room)
    return room

@router.delete("/{room_id}")
def delete_room(
    group_id: int, 
    room_id: int, 
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    room = _get_room_or_404(group_id, room_id, db)
    if room.host_id != current_user_id:
        raise HTTPException(status_code=403, detail="방장만 모집방을 삭제할 수 있습니다.")
    db.delete(room)
    db.commit()
    return {"message": "방이 삭제되었습니다."}

@router.post("/{room_id}/join")
def join_room(
    group_id: int,
    room_id: int,
    background_tasks: BackgroundTasks,
    user_id: str | None = None,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    group = _get_group_or_404(group_id, db)
    _require_group_member(group, current_user_id)
    room = _get_room_or_404(group_id, room_id, db)
    user = _get_current_user_or_404(current_user_id, db)

    if any(participant.id == current_user_id for participant in room.participants):
        raise HTTPException(status_code=400, detail="이미 참가한 방입니다.")
    if room.status != models.RoomStatus.RECRUITING:
        raise HTTPException(status_code=400, detail="현재 참가할 수 없는 방입니다.")
    if len(room.participants) >= room.target_count:
        raise HTTPException(status_code=400, detail="모집 인원이 이미 가득 찼습니다.")

    room.participants.append(user)
    
    if len(room.participants) >= room.target_count:
        room.status = models.RoomStatus.COMPLETED
        host = db.query(models.User).filter(models.User.id == room.host_id).first()
        if host and host.fcm_token:
            title = "모집 완료!"
            body = f"<{room.game_name}> 팀에 인원이 다 찼어요"
            background_tasks.add_task(utils.send_fcm_notification, [host.fcm_token], title, body)

    db.commit()
    return {"message": "방에 성공적으로 참가했습니다."}


@router.post("/{room_id}/leave")
def leave_room(
    group_id: int,
    room_id: int,
    user_id: str | None = None,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    _require_same_user(user_id, current_user_id)
    room = _get_room_or_404(group_id, room_id, db)
    user = _get_current_user_or_404(current_user_id, db)

    if not any(participant.id == current_user_id for participant in room.participants):
        raise HTTPException(status_code=400, detail="참가하지 않은 방입니다.")

    room.participants.remove(user)
    if room.status == models.RoomStatus.COMPLETED and len(room.participants) < room.target_count:
        room.status = models.RoomStatus.RECRUITING

    db.commit()
    return {"message": "방 참가를 취소했습니다."}
