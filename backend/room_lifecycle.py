from sqlalchemy.orm import Session

import models


def remove_room_participant(
    db: Session,
    room: models.Room,
    user: models.User,
) -> bool:
    """Remove a participant and return whether the now-empty room was deleted."""
    room.participants.remove(user)

    if not room.participants:
        db.delete(room)
        return True

    if room.host_id == user.id:
        room.host_id = min(room.participants, key=lambda participant: participant.id).id

    if room.status == models.RoomStatus.COMPLETED and len(room.participants) < room.target_count:
        room.status = models.RoomStatus.RECRUITING

    return False
