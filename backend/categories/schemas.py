from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from db.models.user import UserRole


class CategoryCreateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Category name (e.g. Prof hisob ro'yxati)")
    description: Optional[str] = Field(None, max_length=1000)
    assigned_roles: List[UserRole] = Field(
        default_factory=list,
        description="Assigned mahalla roles responsible for this category",
    )
    default_frequency_days: int = Field(7, ge=1, le=365, description="Default check-in frequency in days")


class CategoryUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    assigned_roles: Optional[List[UserRole]] = None
    default_frequency_days: Optional[int] = Field(None, ge=1, le=365)
    is_active: Optional[bool] = None


class CategoryResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon_url: Optional[str] = None
    description: Optional[str]
    assigned_roles: List[str]
    default_frequency_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CategoryStatsSchema(BaseModel):
    id: int
    name: str
    icon_url: Optional[str] = None
    description: Optional[str] = None
    assigned_roles: List[str] = []
    default_frequency_days: int
    persons_count: int
    active_assignments_count: int
    overdue_assignments_count: int


class PaginatedCategorySchema(BaseModel):
    items: List[CategoryResponseSchema]
    total: int
    page: int
    page_size: int
    total_pages: int

