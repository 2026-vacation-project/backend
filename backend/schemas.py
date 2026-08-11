from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from models import UnitType, RoomStatus

# User
class UserCreate(BaseModel):
    email: str
    name: str
    profile_image: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    profile_image: Optional[str] = None
    fcm_token: Optional[str] = None
    preferred_games: List[str] = []

    model_config = ConfigDict(from_attributes=True)

class FCMTokenUpdate(BaseModel):
    fcm_token: str

class PreferencesUpdate(BaseModel):
    preferred_games: List[str]

# Group
class GroupCreate(BaseModel):
    name: str

class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime] = None
    members: List[UserResponse] = []

    model_config = ConfigDict(from_attributes=True)

# Role
class RoleCreate(BaseModel):
    name: str
    color: str

class RoleResponse(BaseModel):
    id: int
    group_id: int
    name: str
    color: str

    model_config = ConfigDict(from_attributes=True)

# Room
class RoomCreate(BaseModel):
    game_name: str
    target_count: int
    target_role: Optional[str] = None
    unit_type: UnitType = UnitType.INDIVIDUAL

class RoomUpdate(BaseModel):
    game_name: Optional[str] = None
    target_count: Optional[int] = None
    target_role: Optional[str] = None
    unit_type: Optional[UnitType] = None
    status: Optional[RoomStatus] = None

class RoomResponse(BaseModel):
    id: int
    group_id: int
    host_id: str
    game_name: str
    target_count: int
    target_role: Optional[str] = None
    unit_type: UnitType
    status: RoomStatus
    created_at: Optional[datetime] = None
    participants: List[UserResponse] = []

    model_config = ConfigDict(from_attributes=True)