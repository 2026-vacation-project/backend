from datetime import datetime

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from typing import Annotated, Optional, List
from models import UnitType, RoomStatus


def stringify_id(value: object) -> str:
    return str(value)


EntityId = Annotated[str, BeforeValidator(stringify_id)]

# User & Auth
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    profile_image: Optional[str]
    fcm_token: Optional[str]
    preferred_games: List[str]

class OAuthLoginRequest(BaseModel):
    code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

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

# Room
class RoomCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    game_name: str = Field(min_length=1, max_length=60)
    target_count: int = Field(ge=2, le=100)
    unit_type: UnitType = UnitType.INDIVIDUAL

class RoomUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    game_name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    target_count: Optional[int] = Field(default=None, ge=2, le=100)
    unit_type: Optional[UnitType] = None
    status: Optional[RoomStatus] = None

class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: EntityId
    group_id: EntityId
    host_id: str
    game_name: str
    target_count: int
    unit_type: UnitType
    status: RoomStatus
    created_at: Optional[datetime] = None
    participants: List[UserResponse] = Field(default_factory=list)
