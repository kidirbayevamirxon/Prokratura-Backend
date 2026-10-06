from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.service import (
    all_guard,
    prokuror_or_admin_guard,
    UserAuth,
)
from backend.documents.schemas import (
    DocumentReviewSchema,
    DocumentUpdateSchema,
    DocumentResponseSchema,
    PaginatedDocumentSchema,
    MessageCreateSchema,
    MessageResponseSchema,
    ExtendDeadlineSchema,
    RejectExtensionSchema,
)
from backend.documents.service import DocumentService
from db.connection import get_async_db
from db.models.document import CheckInDocType, CheckInDocStatus

router = APIRouter(prefix="/documents", tags=["Check-In Documents"])


@router.post(
    "",
    response_model=DocumentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a check-in document with photo and optional PDF (Assigned Mahalla Worker, Rais, or Prokuror)",
)
async def upload_document(
    assignment_id: int = Form(..., description="Assignment ID"),
    check_in_date: date = Form(default_factory=date.today, description="Date of check-in/visit"),
    doc_type: CheckInDocType = Form(
        CheckInDocType.REGULAR,
        description="regular, removal_request, or request_extension",
    ),
    requested_date: Optional[date] = Form(None, description="Requested extension date"),
    new_date: Optional[date] = Form(None, description="New deadline date"),
    previous_date: Optional[date] = Form(None, description="Previous deadline date (optional, defaults to assignment next_check_in_due)"),
    frequency_days: Optional[int] = Form(None, ge=1, le=365, description="Optional frequency days (for Prokuror doc outside regular frequency)"),
    frequency_day: Optional[int] = Form(None, ge=1, le=365, description="Alias for frequency_days"),
    document_id: Optional[int] = Form(None, description="Optional document ID if requesting extension on an existing document"),
    description: Optional[str] = Form(None, description="Description / remarks of the inspection (Required)"),
    notes: Optional[str] = Form(None, description="Remarks / inspection notes (alias for description)"),
    photo: UploadFile = File(..., description="Photo proof (max 5 MB)"),
    pdf: Optional[UploadFile] = File(None, description="PDF legal document (max 10 MB)"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    doc_notes = (description or "").strip() or (notes or "").strip()
    asked_date = new_date or requested_date
    return await DocumentService.create_document(
        assignment_id=assignment_id,
        check_in_date=check_in_date,
        doc_type=doc_type,
        notes=doc_notes,
        photo_file=photo,
        pdf_file=pdf,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
        new_date=asked_date,
        requested_date=requested_date,
        previous_date=previous_date,
        frequency_days=frequency_days,
        frequency_day=frequency_day,
        document_id=document_id,
    )


@router.patch(
    "/{document_id}/review",
    response_model=DocumentResponseSchema,
    summary="Review check-in document (Approve or Reject with reason) - Prokuror or Admin only",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def review_document(
    document_id: int,
    data: DocumentReviewSchema,
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.review_document(
        document_id=document_id,
        data=data,
        reviewer_id=current_user["id"],
        db=db,
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponseSchema,
    summary="Update check-in document date or details (Prokuror/Admin or Employer asking for extension)",
)
async def update_document(
    document_id: int,
    data: DocumentUpdateSchema,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.update_document(
        document_id=document_id,
        data=data,
        editor_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.post(
    "/{document_id}/request-extension",
    response_model=DocumentResponseSchema,
    summary="Request extension for a check-in document (Employer / Assigned Mahalla Worker, Rais, or Prokuror)",
)
async def request_document_extension(
    document_id: int,
    requested_date: date = Form(..., description="Requested extension date"),
    description: Optional[str] = Form(None, description="Reason / remarks for asking extension"),
    notes: Optional[str] = Form(None, description="Alias for description"),
    photo: Optional[UploadFile] = File(None, description="Optional photo proof"),
    pdf: Optional[UploadFile] = File(None, description="Optional PDF supporting document"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    doc_notes = (description or "").strip() or (notes or "").strip()
    return await DocumentService.request_document_extension(
        document_id=document_id,
        requested_date=requested_date,
        description=doc_notes,
        photo_file=photo,
        pdf_file=pdf,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.get(
    "/{document_id}/messages",
    response_model=List[MessageResponseSchema],
    summary="Get discussion messages for a check-in document",
)
async def get_document_messages(
    document_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.get_document_messages(
        document_id=document_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.post(
    "/{document_id}/messages",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Post a message or send extension request in document chat",
)
async def create_document_message(
    document_id: int,
    data: MessageCreateSchema,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.create_document_message(
        document_id=document_id,
        data=data,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.post(
    "/{document_id}/extend-deadline",
    response_model=DocumentResponseSchema,
    summary="Directly extend check-in deadline (Prokuror/Admin) without approving the document",
)
async def extend_document_deadline(
    document_id: int,
    data: ExtendDeadlineSchema,
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.extend_document_deadline(
        document_id=document_id,
        data=data,
        prosecutor_id=current_user["id"],
        db=db,
    )


@router.post(
    "/{document_id}/reject-extension",
    response_model=DocumentResponseSchema,
    summary="Reject deadline extension request (Prokuror/Admin)",
)
async def reject_document_extension(
    document_id: int,
    data: RejectExtensionSchema,
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.reject_document_extension(
        document_id=document_id,
        data=data,
        prosecutor_id=current_user["id"],
        db=db,
    )



@router.get(
    "",
    response_model=PaginatedDocumentSchema,
    summary="Get paginated history of check-in documents (Role-filtered)",
)
async def get_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    status: Optional[CheckInDocStatus] = Query(None, description="Filter by pending/approved/rejected"),
    doc_type: Optional[CheckInDocType] = Query(None, description="Filter by regular, removal_request, or request_extension"),
    mahalla_id: Optional[int] = Query(None, description="Filter by Mahalla (Admin/Prokuror only)"),
    category_id: Optional[int] = Query(None, description="Filter by Category ID"),
    person_id: Optional[int] = Query(None, description="Filter by Person ID"),
    assignment_id: Optional[int] = Query(None, description="Filter by Assignment ID"),
    remaining_days: Optional[int] = Query(None, description="Filter by exact remaining days (e.g. 5 for 5 days left, 0 for today, negative for overdue)"),
    days_remaining: Optional[int] = Query(None, description="Alias for remaining_days"),
    latest_only: Optional[bool] = Query(None, description="Return only the latest document per assignment (default: True when remaining_days is given)"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.get_documents(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        doc_type=doc_type,
        mahalla_id=mahalla_id,
        category_id=category_id,
        person_id=person_id,
        assignment_id=assignment_id,
        remaining_days=remaining_days,
        days_remaining=days_remaining,
        latest_only=latest_only,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        caller_id=current_user["id"],
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponseSchema,
    summary="Get detailed check-in document by ID",
)
async def get_document_by_id(
    document_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.get_document_by_id(
        document_id=document_id,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.post(
    "/{document_id}/seen",
    response_model=DocumentResponseSchema,
    summary="Mark check-in document as seen by Mahalla official (Mahalla Raisi or Mahalla Yettiligi)",
)
async def mark_document_seen(
    document_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await DocumentService.mark_document_seen(
        document_id=document_id,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete check-in document and remove physical files (Admin, Prokuror, or Mahalla Raisi)",
)
async def delete_document(
    document_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    await DocumentService.delete_document(
        document_id=document_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )
    return {"detail": "Check-in document and associated files deleted successfully"}
