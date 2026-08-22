import pytest
from fastapi import BackgroundTasks, HTTPException

import models
import schemas
from routers.roles import assign_role, unassign_role
from routers.rooms import create_room, join_room


def _user(user_id: str, name: str) -> models.User:
    return models.User(
        id=user_id,
        email=f"{user_id}@example.com",
        name=name,
        preferred_games=[],
    )


def test_member_can_have_multiple_tags_and_remove_one(session_factory) -> None:
    with session_factory() as db:
        host = _user("user-1", "방장")
        member = _user("user-2", "멤버")
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.extend([host, member])
        healer = models.Role(id=11, group=group, name="힐러", color="#008bfe")
        caller = models.Role(id=12, group=group, name="오더", color="#ef7f1a")
        db.add_all([group, healer, caller])
        db.commit()

        assign_role(group.id, healer.id, member.id, current_user_id=host.id, db=db)
        assign_role(group.id, caller.id, member.id, current_user_id=host.id, db=db)
        db.refresh(member)
        assert {tag.name for tag in member.roles} == {"힐러", "오더"}
        assert schemas.RoleResponse.model_validate(caller).user_ids == [member.id]

        unassign_role(group.id, healer.id, member.id, current_user_id=host.id, db=db)
        db.refresh(member)
        assert [tag.name for tag in member.roles] == ["오더"]


def test_room_tags_are_saved_and_only_matching_members_can_join(session_factory) -> None:
    with session_factory() as db:
        host = _user("user-1", "방장")
        matching_member = _user("user-2", "힐러 유저")
        other_member = _user("user-3", "태그 없는 유저")
        group = models.Group(id=1, name="테스트 그룹", is_public=True)
        group.members.extend([host, matching_member, other_member])
        healer = models.Role(id=11, group=group, name="힐러", color="#008bfe")
        matching_member.roles.append(healer)
        db.add(group)
        db.commit()

        room = create_room(
            group_id=group.id,
            room_in=schemas.RoomCreate(game_name="Overwatch 2", target_count=3, tag_ids=[str(healer.id)]),
            background_tasks=BackgroundTasks(),
            current_user_id=host.id,
            db=db,
        )
        assert [tag.name for tag in room.tags] == ["힐러"]

        join_room(
            group_id=group.id,
            room_id=room.id,
            background_tasks=BackgroundTasks(),
            current_user_id=matching_member.id,
            db=db,
        )
        assert matching_member in room.participants

        with pytest.raises(HTTPException) as exc_info:
            join_room(
                group_id=group.id,
                room_id=room.id,
                background_tasks=BackgroundTasks(),
                current_user_id=other_member.id,
                db=db,
            )
        assert exc_info.value.status_code == 400
        assert "찾는 태그" in exc_info.value.detail


def test_room_rejects_tags_from_another_group(session_factory) -> None:
    with session_factory() as db:
        host = _user("user-1", "방장")
        group = models.Group(id=1, name="첫 그룹", is_public=True)
        group.members.append(host)
        other_group = models.Group(id=2, name="다른 그룹", is_public=True)
        foreign_tag = models.Role(id=21, group=other_group, name="탱커", color="#555555")
        db.add_all([group, other_group, foreign_tag])
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            create_room(
                group_id=group.id,
                room_in=schemas.RoomCreate(game_name="Valorant", target_count=5, tag_ids=[str(foreign_tag.id)]),
                background_tasks=BackgroundTasks(),
                current_user_id=host.id,
                db=db,
            )
        assert exc_info.value.status_code == 400
