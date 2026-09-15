import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from db.models.user import UserRole


class MahallaMemberSimpleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    phone: str
    login: Optional[str] = None
    role: UserRole
    is_active: bool


class MahallaDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime
    members: List[MahallaMemberSimpleSchema] = []


class PaginatedMahallaSchema(BaseModel):
    items: List[MahallaDetailSchema]
    total: int
    page: int
    page_size: int

