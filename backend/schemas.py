from pydantic import BaseModel
from typing import Optional, List
from models import UnitType, RoomStatus

# User & Auth
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    profile_image: Optional[str]
    fcm_token: Optional[str]
    preferred_games: List[str]

    class Config:
        from_attributes = True

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
    name: str

class GroupResponse(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True

# Role
class RoleCreate(BaseModel):
    name: str
    color: str

class RoleResponse(BaseModel):
    id: int
    group_id: int
    name: str
    color: str

    class Config:
        from_attributes = True

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

class RoomResponse(BaseModel):
    id: int
    group_id: int
    host_id: str
    game_name: str
    target_count: int
    target_role: Optional[str]
    unit_type: UnitType
    status: RoomStatus

    class Config:
        from_attributes = True