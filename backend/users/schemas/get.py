import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from db.models.user import UserRole


class UserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    created_at: datetime.datetime
    updated_at: datetime.datetime


class PaginatedUserSchema(BaseModel):
    items: List[UserResponseSchema]
    total: int
    page: int
    page_size: int

