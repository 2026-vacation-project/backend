import pytest
from fastapi import HTTPException

from importers.igdb.importer import IGDBImporter
import models
from routers.rooms import get_room, list_rooms


def test_room_responses_include_the_local_game_cover(session_factory, elden_ring_payload) -> None:
    with session_factory() as db:
        IGDBImporter(db).import_batch([elden_ring_payload])

        user = models.User(
            id="user-1",
            email="user-1@example.com",
            name="방장",
            preferred_games=[],
        )
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.append(user)
        room = models.Room(
            id=101,
            group=group,
            host_id=user.id,
            game_name="엘든 링",
            target_count=2,
        )
        room.participants.append(user)
        db.add_all([group, room])
        db.commit()

        rooms = list_rooms(group_id=group.id, current_user_id=user.id, db=db)
        room_detail = get_room(
            group_id=group.id,
            room_id=room.id,
            current_user_id=user.id,
            db=db,
        )

        expected_cover = "https://images.igdb.com/igdb/image/upload/t_cover_big/co4jni.jpg"
        assert rooms[0].game_cover_url == expected_cover
        assert room_detail.game_cover_url == expected_cover


def test_non_member_can_list_rooms_but_cannot_open_room_detail(session_factory) -> None:
    with session_factory() as db:
        host = models.User(
            id="host-1",
            email="host@example.com",
            name="방장",
            preferred_games=[],
        )
        visitor = models.User(
            id="visitor-1",
            email="visitor@example.com",
            name="방문자",
            preferred_games=[],
        )
        group = models.Group(id=1, name="공개 그룹", is_public=True)
        group.members.append(host)
        room = models.Room(
            id=101,
            group=group,
            host_id=host.id,
            game_name="Overwatch 2",
            target_count=3,
        )
        room.participants.append(host)
        db.add_all([group, room, visitor])
        db.commit()

        rooms = list_rooms(group_id=group.id, current_user_id=visitor.id, db=db)
        assert [listed_room.id for listed_room in rooms] == [room.id]

        with pytest.raises(HTTPException) as exc_info:
            get_room(
                group_id=group.id,
                room_id=room.id,
                current_user_id=visitor.id,
                db=db,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "그룹에 참여해야 모집방 정보를 볼 수 있습니다."
