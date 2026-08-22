import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import models
import utils
from routers.auth import logout_all
from routers.rooms import leave_room


def _user(user_id: str, name: str, *, fcm_token: str | None = None) -> models.User:
    return models.User(
        id=user_id,
        email=f"{user_id}@example.com",
        name=name,
        fcm_token=fcm_token,
        preferred_games=[],
    )


def test_last_participant_leaving_deletes_room(session_factory) -> None:
    with session_factory() as db:
        user = _user("user-1", "방장")
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.append(user)
        room = models.Room(
            id=101,
            group=group,
            host_id=user.id,
            game_name="Minecraft",
            target_count=2,
        )
        room.participants.append(user)
        db.add_all([group, room])
        db.commit()

        response = leave_room(
            group_id=group.id,
            room_id=room.id,
            current_user_id=user.id,
            db=db,
        )

        assert "빈 모집방을 삭제" in response["message"]
        assert db.get(models.Room, room.id) is None


def test_logout_all_leaves_rooms_deletes_empty_rooms_and_revokes_tokens(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(utils, "SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

    with session_factory() as db:
        user = _user("user-1", "방장", fcm_token="device-token")
        other = _user("user-2", "참가자")
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.extend([user, other])

        solo_room = models.Room(
            id=101,
            group=group,
            host_id=user.id,
            game_name="Minecraft",
            target_count=2,
        )
        solo_room.participants.append(user)

        shared_room = models.Room(
            id=102,
            group=group,
            host_id=user.id,
            game_name="Elden Ring",
            target_count=2,
            status=models.RoomStatus.COMPLETED,
        )
        shared_room.participants.extend([user, other])
        db.add_all([group, solo_room, shared_room])
        db.commit()

        old_token = utils.create_access_token({"sub": user.id, "ver": user.auth_version})
        response = logout_all(current_user_id=user.id, db=db)
        db.expire_all()

        assert response["left_room_count"] == 2
        assert response["deleted_room_count"] == 1
        assert db.get(models.Room, solo_room.id) is None

        remaining_room = db.get(models.Room, shared_room.id)
        assert remaining_room is not None
        assert [participant.id for participant in remaining_room.participants] == [other.id]
        assert remaining_room.host_id == other.id
        assert remaining_room.status == models.RoomStatus.RECRUITING

        logged_out_user = db.get(models.User, user.id)
        assert logged_out_user is not None
        assert logged_out_user.auth_version == 1
        assert logged_out_user.fcm_token is None

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=old_token)
        with pytest.raises(HTTPException) as exc_info:
            utils.get_current_user_id(credentials=credentials, db=db)
        assert exc_info.value.status_code == 401
