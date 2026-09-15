from typing import Optional
from pydantic import BaseModel, Field
from db.models.user import UserRole


class UserUpdateSchema(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    login: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=6)
    role: Optional[UserRole] = None
    mahalla_id: Optional[int] = None
    photo_url: Optional[str] = None
    birth_date_text: Optional[str] = None
    appointed_date_text: Optional[str] = None
    specialization: Optional[str] = None
    previous_workplace: Optional[str] = None
    is_active: Optional[bool] = None

