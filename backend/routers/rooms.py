from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import models, schemas, database, utils

router = APIRouter(prefix="/api/v1/groups/{group_id}/rooms", tags=["Rooms"])

# 0. 방 목록 조회 및 특정 방 조회
@router.get("", response_model=List[schemas.RoomResponse])
def get_rooms(group_id: int, db: Session = Depends(database.get_db)):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")
    return db.query(models.Room).filter(models.Room.group_id == group_id).all()

@router.get("/{room_id}", response_model=schemas.RoomResponse)
def get_room(group_id: int, room_id: int, db: Session = Depends(database.get_db)):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    return room

# 1. 방 생성 (생성 시 그룹 멤버들에게 FCM 알림 발송)
@router.post("", response_model=schemas.RoomResponse)
def create_room(
    group_id: int,
    host_id: str,
    room_in: schemas.RoomCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="그룹을 찾을 수 없습니다.")

    host = db.query(models.User).filter(models.User.id == host_id).first()
    if not host:
        raise HTTPException(status_code=404, detail="방장을 찾을 수 없습니다.")

    if host not in group.members:
        group.members.append(host)

    room = models.Room(
        group_id=group_id,
        host_id=host_id,
        game_name=room_in.game_name,
        target_count=room_in.target_count,
        target_role=room_in.target_role,
        unit_type=room_in.unit_type
    )
    room.participants.append(host)
    db.add(room)
    db.commit()
    db.refresh(room)

    # 알림 1: <닉네임>이(가) <게임 이름> 팀을 구하고 있어요
    tokens = [u.fcm_token for u in group.members if u.fcm_token and u.id != host_id]
    if tokens:
        title = "팀 모집 시작!"
        body = f"{host.name}님이 <{room.game_name}> 팀을 구하고 있어요"
        background_tasks.add_task(utils.send_fcm_notification, tokens, title, body)

    return room

# 2. 방 정보 수정 (PATCH)
@router.patch("/{room_id}", response_model=schemas.RoomResponse)
def update_room(
    group_id: int,
    room_id: int,
    room_update: schemas.RoomUpdate,
    db: Session = Depends(database.get_db)
):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    
    update_data = room_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(room, key, value)

    if len(room.participants) >= room.target_count:
        room.status = models.RoomStatus.COMPLETED

    db.commit()
    db.refresh(room)
    return room

# 3. 방 삭제 (DELETE)
@router.delete("/{room_id}")
def delete_room(group_id: int, room_id: int, db: Session = Depends(database.get_db)):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="방을 찾을 수 없습니다.")
    db.delete(room)
    db.commit()
    return {"message": "방이 삭제되었습니다."}

# 4. 방 참가 (인원 충족 시 방장에게 FCM 알림 발송)
@router.post("/{room_id}/join")
def join_room(
    group_id: int,
    room_id: int,
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not room or not user:
        raise HTTPException(status_code=404, detail="방 또는 유저를 찾을 수 없습니다.")

    if room.status != models.RoomStatus.RECRUITING:
        raise HTTPException(status_code=400, detail="모집 중인 방이 아닙니다.")

    if user in room.participants:
        raise HTTPException(status_code=400, detail="이미 참가한 방입니다.")

    room.participants.append(user)
    
    # 인원이 다 차면 COMPLETED 상태 변경 및 방장에게 알림 전송
    if len(room.participants) >= room.target_count:
        room.status = models.RoomStatus.COMPLETED
        host = db.query(models.User).filter(models.User.id == room.host_id).first()
        if host and host.fcm_token:
            title = "모집 완료!"
            body = f"<{room.game_name}> 팀에 인원이 다 찼어요"
            background_tasks.add_task(utils.send_fcm_notification, [host.fcm_token], title, body)

    db.commit()
    return {"message": "방에 성공적으로 참가했습니다."}

# 5. 방 퇴장
@router.post("/{room_id}/leave")
def leave_room(
    group_id: int,
    room_id: int,
    user_id: str,
    db: Session = Depends(database.get_db)
):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.group_id == group_id).first()
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not room or not user:
        raise HTTPException(status_code=404, detail="방 또는 유저를 찾을 수 없습니다.")

    if user not in room.participants:
        raise HTTPException(status_code=400, detail="참가하지 않은 방입니다.")

    room.participants.remove(user)
    if len(room.participants) < room.target_count and room.status == models.RoomStatus.COMPLETED:
        room.status = models.RoomStatus.RECRUITING

    db.commit()
    return {"message": "방에서 퇴장했습니다."}