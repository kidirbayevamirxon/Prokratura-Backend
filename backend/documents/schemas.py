from datetime import date, datetime
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

    @model_validator(mode="after")
    def check_rejection_reason(self):
        if self.status == CheckInDocStatus.REJECTED:
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection_reason is required when rejecting a document")
        return self


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
    doc_type: CheckInDocType
    photo_url: str
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None
    check_in_date: date
    due_date: Optional[date] = None
    days_remaining: Optional[int] = None
    status: CheckInDocStatus
    rejection_reason: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    seen_at: Optional[datetime] = None
    seen_by_id: Optional[int] = None
    seen_by_name: Optional[str] = None
    is_seen: bool = False
    created_at: datetime


class PaginatedDocumentSchema(BaseModel):
    items: List[DocumentResponseSchema]
    total: int
    page: int
    page_size: int
    total_pages: int

