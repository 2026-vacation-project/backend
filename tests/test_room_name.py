from fastapi import BackgroundTasks

import models
import schemas
from routers.rooms import create_room, update_room


def _host() -> models.User:
    return models.User(
        id="host-1",
        email="host@example.com",
        name="방장",
        preferred_games=[],
    )


def test_room_name_is_optional_and_trimmed(session_factory) -> None:
    with session_factory() as db:
        host = _host()
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.append(host)
        db.add(group)
        db.commit()

        named_room = create_room(
            group_id=group.id,
            room_in=schemas.RoomCreate(
                name="  오늘 저녁 경쟁전  ",
                game_name="Overwatch 2",
                target_count=3,
            ),
            background_tasks=BackgroundTasks(),
            current_user_id=host.id,
            db=db,
        )
        unnamed_room = create_room(
            group_id=group.id,
            room_in=schemas.RoomCreate(
                name="   ",
                game_name="Valorant",
                target_count=5,
            ),
            background_tasks=BackgroundTasks(),
            current_user_id=host.id,
            db=db,
        )

        assert named_room.name == "오늘 저녁 경쟁전"
        assert unnamed_room.name is None

        updated_room = update_room(
            group_id=group.id,
            room_id=named_room.id,
            room_update=schemas.RoomUpdate(name=""),
            current_user_id=host.id,
            db=db,
        )
        assert updated_room.name is None
