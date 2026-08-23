from datetime import datetime

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator
from typing import Annotated, Optional, List
from models import RoomStatus


def stringify_id(value: object) -> str:
    return str(value)


EntityId = Annotated[str, BeforeValidator(stringify_id)]

# User & Auth
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    display_name: Optional[str] = None
    profile_image: Optional[str]
    fcm_token: Optional[str]
    preferred_games: List[str]

class OAuthLoginRequest(BaseModel):
    code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class LogoutAllResponse(BaseModel):
    message: str
    left_room_count: int
    deleted_room_count: int

class FCMTokenUpdate(BaseModel):
    fcm_token: str

class PreferencesUpdate(BaseModel):
    preferred_games: List[str]

# Group
class GroupCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=40)
    is_public: bool = True


class GroupVisibilityUpdate(BaseModel):
    is_public: bool


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    name: str
    is_public: bool
    created_at: Optional[datetime] = None
    members: List[UserResponse] = Field(default_factory=list)

# Role
class RoleCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=30)
    color: str = Field(min_length=1, max_length=30)

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    group_id: EntityId
    name: str
    color: str
    user_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def collect_user_ids(cls, value: object) -> object:
        if isinstance(value, dict):
            return value
        return {
            "id": getattr(value, "id"),
            "group_id": getattr(value, "group_id"),
            "name": getattr(value, "name"),
            "color": getattr(value, "color"),
            "user_ids": [user.id for user in getattr(value, "users", [])],
        }


class TagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    group_id: EntityId
    name: str
    color: str

# Room
class RoomCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, max_length=60)
    game_name: str = Field(min_length=1, max_length=60)
    target_count: int = Field(ge=2, le=100)
    tag_ids: List[EntityId] = Field(default_factory=list, max_length=20)

class RoomUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, max_length=60)
    game_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    target_count: Optional[int] = Field(default=None, ge=2, le=100)
    status: Optional[RoomStatus] = None
    tag_ids: Optional[List[EntityId]] = Field(default=None, max_length=20)

class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    group_id: EntityId
    host_id: str
    name: Optional[str] = None
    game_name: str
    game_cover_url: Optional[str] = None
    target_count: int
    status: RoomStatus
    created_at: Optional[datetime] = None
    participants: List[UserResponse] = Field(default_factory=list)
    tags: List[TagResponse] = Field(default_factory=list)
