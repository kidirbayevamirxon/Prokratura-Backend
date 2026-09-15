from typing import Optional
from pydantic import BaseModel
from db.models.user import UserRole


class TokenRes(BaseModel):
    access_token: str
    refresh_token: str
    role: UserRole
    user_id: int
    mahalla_id: Optional[int] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str


class MeResponseSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone: str
    login: Optional[str] = None
    role: UserRole
    mahalla_id: Optional[int] = None
    photo_url: Optional[str] = None
    birth_date_text: Optional[str] = None
    appointed_date_text: Optional[str] = None
    specialization: Optional[str] = None
    previous_workplace: Optional[str] = None
    is_active: bool


