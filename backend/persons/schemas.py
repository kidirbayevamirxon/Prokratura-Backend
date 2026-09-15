from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from db.models.user import UserRole
from db.models.assignment import AssignmentStatus


class PersonCreateSchema(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="F.I.SH (Full name)")
    birth_date: date = Field(..., description="Tug'ilgan sana (Birthday)")
    mahalla_id: int = Field(..., description="Assigned Mahalla ID")


class PersonUpdateSchema(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    birth_date: Optional[date] = None
    mahalla_id: Optional[int] = None
    is_active: Optional[bool] = None


class AssignmentCreateSchema(BaseModel):
    category_id: int = Field(..., description="Category / Docs type ID to assign")
    frequency_days: int = Field(..., ge=1, le=365, description="Frequency of check-in in days")


class AssignmentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    category_id: int
    category_name: str
    mahalla_id: int
    frequency_days: int
    assigned_roles: List[str]
    next_check_in_due: date
    days_remaining: int
    is_overdue: bool
    status: AssignmentStatus
    created_at: datetime


class RemainingDaysStatsSchema(BaseModel):
    # Top KPI Cards (Hujjatlar monitoringi - Image red circle)
    jami_hujjatlar: int = Field(0, description="Jami hujjatlar (Total documents)")
    kiruvchi_hujjatlar: int = Field(0, description="Kiruvchi hujjatlar (Incoming / in execution check-ins)")
    bajarilgan_hujjatlar: int = Field(0, description="Bajarilgan hujjatlar (Completed / approved check-ins)")
    muddati_buzilib_bajarilgan: int = Field(0, description="Muddati buzilib bajarilgan (Completed after deadline)")
    kech_qabul_qilingan: int = Field(0, description="Kech qabul qilingan (Submitted or accepted late)")
    muddati_buzilgan_hujjatlar: int = Field(0, description="Muddati buzilgan hujjatlar (Deadline violated / overdue)")

    # English aliases for developer convenience
    total_documents: int = Field(0, description="Alias for jami_hujjatlar")
    pending_documents: int = Field(0, description="Alias for kiruvchi_hujjatlar")
    completed_documents: int = Field(0, description="Alias for bajarilgan_hujjatlar")
    completed_overdue: int = Field(0, description="Alias for muddati_buzilib_bajarilgan")
    late_accepted: int = Field(0, description="Alias for kech_qabul_qilingan")
    overdue_documents: int = Field(0, description="Alias for muddati_buzilgan_hujjatlar")

    # Muddat / Days remaining breakdown
    overdue: int = Field(..., description="Count of check-ins where deadline passed (<0 days)")
    today: int = Field(..., description="Count of check-ins due today (0 days left)")
    bugun: int = Field(0, description="Bugun (Alias for today)")
    ertaga: int = Field(0, description="Ertaga (Due tomorrow, 1 day left)")
    indinga: int = Field(0, description="Indinga (Due day after tomorrow, 2 days left)")
    by_day: dict[int, int] = Field(
        ..., description="Count of check-ins broken down by remaining days (e.g. 1: count, 2: count, 3: count, 4: count, 5: count)"
    )
    total_active: int = Field(..., description="Total active assignments")


class PersonResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    birth_date: date
    mahalla_id: int
    mahalla_name: Optional[str] = None
    is_active: bool
    assignments: List[AssignmentResponseSchema] = []
    created_at: datetime
    updated_at: datetime


class PaginatedPersonSchema(BaseModel):
    items: List[PersonResponseSchema]
    total: int
    page: int
    page_size: int
    total_pages: int

