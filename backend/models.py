import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, BigInteger, Integer, ForeignKey, DateTime, Enum, JSON, Table
from sqlalchemy.orm import relationship
from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class UnitType(str, enum.Enum):
    INDIVIDUAL = "명"
    TEAM = "팀"

class RoomStatus(str, enum.Enum):
    RECRUITING = "RECRUITING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

group_members = Table(
    'group_members', Base.metadata,
    Column('group_id', BigInteger, ForeignKey('groups.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True)
)

user_roles = Table(
    'user_roles', Base.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('role_id', BigInteger, ForeignKey('roles.id'), primary_key=True)
)

room_participants = Table(
    'room_participants', Base.metadata,
    Column('room_id', BigInteger, ForeignKey('rooms.id'), primary_key=True),
    Column('user_id', String, ForeignKey('users.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    profile_image = Column(String, nullable=True)
    fcm_token = Column(String, nullable=True)
    preferred_games = Column(JSON, default=list)

    groups = relationship("Group", secondary=group_members, back_populates="members")
    roles = relationship("Role", secondary=user_roles, back_populates="users")

class Group(Base):
    __tablename__ = "groups"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    members = relationship("User", secondary=group_members, back_populates="groups")
    roles = relationship("Role", back_populates="group", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="group", cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)

    group = relationship("Group", back_populates="roles")
    users = relationship("User", secondary=user_roles, back_populates="roles")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_id = Column(BigInteger, ForeignKey("groups.id"), nullable=False)
    host_id = Column(String, ForeignKey("users.id"), nullable=False)
    game_name = Column(String, nullable=False)
    target_count = Column(Integer, nullable=False)
    target_role = Column(String, nullable=True)
    unit_type = Column(Enum(UnitType), default=UnitType.INDIVIDUAL)
    status = Column(Enum(RoomStatus), default=RoomStatus.RECRUITING)
    created_at = Column(DateTime, default=utc_now)

    group = relationship("Group", back_populates="rooms")
    participants = relationship("User", secondary=room_participants)
