from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups/{group_id}/rooms", tags=["Rooms"])

@router.post("", response_model=schemas.RoomResponse)
def create_room(
    group_id: int,
    room_in: schemas.RoomCreate,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    host = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="방장을 찾을 수 없습니다.")

    room = models.Room(
        group_id=group_id,
        host_id=current_user_id,
        game_name=room_in.game_name,
        target_count=room_in.target_count,
        target_role=room_in.target_role,
        unit_type=room_in.unit_type
    )
    room.participants.append(host)
    db.add(room)
    db.commit()
    db.refresh(room)

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if group:
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
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    
    update_data = room_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)

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
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    db.delete(room)
    db.commit()
    return {"message": "방이 삭제되었습니다."}

@router.post("/{room_id}/join")
def join_room(
    group_id: int,
    room_id: int,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db)
):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    user = db.query(models.User).filter(models.User.id == current_user_id).first()
    if not room or not user:
        raise HTTPException(status_code=404, detail="방 또는 유저를 찾을 수 없습니다.")

    if user in room.participants:
        raise HTTPException(status_code=400, detail="이미 참가한 방입니다.")

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