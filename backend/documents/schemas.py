from datetime import date as dt_date, datetime as dt_datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator
from db.models.document import CheckInDocType, CheckInDocStatus


class DocumentReviewSchema(BaseModel):
    status: CheckInDocStatus = Field(
        ..., description="Review outcome: approved or rejected"
    )
    rejection_reason: Optional[str] = Field(
        None, max_length=1000, description="Mandatory reason if rejected"
    )
    new_date: Optional[dt_date] = Field(
        None, description="Change or set the deadline / new date"
    )

    @model_validator(mode="after")
    def check_rejection_reason(self):
        if self.status == CheckInDocStatus.REJECTED:
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection_reason is required when rejecting a document")
        return self


class DocumentUpdateSchema(BaseModel):
    new_date: Optional[dt_date] = Field(None, description="New deadline date")
    requested_date: Optional[dt_date] = Field(None, description="Requested extension date")
    previous_date: Optional[dt_date] = Field(None, description="Previous date override (optional)")
    check_in_date: Optional[dt_date] = Field(None, description="Check-in visit date")
    frequency_days: Optional[int] = Field(None, ge=1, le=365, description="Frequency days override")
    frequency_day: Optional[int] = Field(None, ge=1, le=365, description="Alias for frequency_days")
    description: Optional[str] = Field(None, max_length=1000, description="Remarks or inspection notes")
    notes: Optional[str] = Field(None, max_length=1000, description="Alias for description")


class DocumentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    person_id: int
    person_name: str
    category_id: int
    category_name: str
    mahalla_id: int
    mahalla_name: Optional[str] = None
    submitted_by_id: int
    submitted_by_name: str
    is_from_prokuror: bool = False
    doc_type: CheckInDocType
    photo_url: str
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    check_in_date: dt_date
    due_date: Optional[dt_date] = None
    previous_date: Optional[dt_date] = None
    requested_date: Optional[dt_date] = None
    new_date: Optional[dt_date] = None
    frequency_days: Optional[int] = None
    days_remaining: Optional[int] = None
    status: CheckInDocStatus
    rejection_reason: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[dt_datetime] = None
    seen_at: Optional[dt_datetime] = None
    seen_by_id: Optional[int] = None
    seen_by_name: Optional[str] = None
    is_seen: bool = False
    created_at: dt_datetime


class PaginatedDocumentSchema(BaseModel):
    items: List[DocumentResponseSchema]
    total: int
    page: int
    page_size: int
    total_pages: int
