import math
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.files.service import FileService
from backend.documents.schemas import (
    DocumentReviewSchema,
    DocumentResponseSchema,
    PaginatedDocumentSchema,
)
from db.models.document import CheckInDocument, CheckInDocType, CheckInDocStatus
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES


class DocumentService:
    @staticmethod
    def _format_document(doc: CheckInDocument) -> DocumentResponseSchema:
        submitter_name = (
            f"{doc.submitted_by.first_name} {doc.submitted_by.last_name}"
            if doc.submitted_by
            else "Noma'lum"
        )
        reviewer_name = (
            f"{doc.reviewed_by.first_name} {doc.reviewed_by.last_name}"
            if doc.reviewed_by
            else None
        )

        today = date.today()
        days_remaining = None
        if doc.due_date:
            days_remaining = (doc.due_date - today).days
        elif getattr(doc, "assignment", None) and doc.assignment and doc.assignment.next_check_in_due:
            days_remaining = (doc.assignment.next_check_in_due - today).days

        return DocumentResponseSchema(
            id=doc.id,
            assignment_id=doc.assignment_id,
            person_id=doc.person_id,
            person_name=doc.person.full_name if doc.person else "",
            category_id=doc.category_id,
            category_name=doc.category.name if doc.category else "",
            mahalla_id=doc.mahalla_id,
            mahalla_name=doc.mahalla.name if doc.mahalla else None,
            submitted_by_id=doc.submitted_by_id,
            submitted_by_name=submitter_name,
            doc_type=doc.doc_type,
            photo_url=doc.photo_url,
            pdf_url=doc.pdf_url,
            notes=doc.notes,
            check_in_date=doc.check_in_date,
            due_date=doc.due_date,
            days_remaining=days_remaining,
            status=doc.status,
            rejection_reason=doc.rejection_reason,
            reviewed_by_id=doc.reviewed_by_id,
            reviewed_by_name=reviewer_name,
            reviewed_at=doc.reviewed_at,
            created_at=doc.created_at,
        )

    @classmethod
    async def create_document(
        cls,
        assignment_id: int,
        check_in_date: date,
        doc_type: CheckInDocType,
        notes: Optional[str],
        photo_file: UploadFile,
        pdf_file: Optional[UploadFile],
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> DocumentResponseSchema:
        assignment = await db.scalar(
            select(PersonCategoryAssignment)
            .where(PersonCategoryAssignment.id == assignment_id)
            .options(
                selectinload(PersonCategoryAssignment.category),
                selectinload(PersonCategoryAssignment.person),
                selectinload(PersonCategoryAssignment.mahalla),
            )
        )
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person category assignment not found",
            )

        if assignment.status != AssignmentStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit check-in for an inactive assignment (current status: {assignment.status})",
            )

        # RBAC Check:
        # Admin / Prokuror: allowed
        # Rais: allowed if assignment belongs to their mahalla
        # Mahalla 7 worker: allowed if assignment belongs to their mahalla AND their role is responsible
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if assignment.mahalla_id != caller_mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot submit check-in documents for another mahalla",
                )

            if caller_role != UserRole.MAHALLA_RAISI:
                assigned_roles = assignment.assigned_roles or (
                    assignment.category.assigned_roles if assignment.category else []
                )
                if caller_role.value not in assigned_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role '{caller_role.value}' is not assigned to handle category '{assignment.category.name}'",
                    )

        # Upload files
        photo_url = await FileService.save_uploaded_photo(photo_file)
        pdf_url = None
        if pdf_file and pdf_file.filename:
            pdf_url = await FileService.save_uploaded_pdf(pdf_file)

        doc = CheckInDocument(
            assignment_id=assignment.id,
            person_id=assignment.person_id,
            category_id=assignment.category_id,
            mahalla_id=assignment.mahalla_id,
            submitted_by_id=caller_id,
            doc_type=doc_type,
            photo_url=photo_url,
            pdf_url=pdf_url,
            notes=notes,
            check_in_date=check_in_date,
            due_date=assignment.next_check_in_due,
            status=CheckInDocStatus.PENDING,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Fetch with relationships for response
        return await cls.get_document_by_id(
            doc.id,
            caller_role=UserRole.ADMIN,
            caller_mahalla_id=None,
            db=db,
        )

    @classmethod
    async def review_document(
        cls,
        document_id: int,
        data: DocumentReviewSchema,
        reviewer_id: int,
        db: AsyncSession,
    ) -> DocumentResponseSchema:
        doc = await db.scalar(
            select(CheckInDocument)
            .where(CheckInDocument.id == document_id)
            .options(
                selectinload(CheckInDocument.assignment),
                selectinload(CheckInDocument.person),
                selectinload(CheckInDocument.category),
                selectinload(CheckInDocument.mahalla),
                selectinload(CheckInDocument.submitted_by),
            )
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in document not found",
            )

        if doc.status != CheckInDocStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document has already been reviewed (current status: {doc.status})",
            )

        now = datetime.now()
        doc.status = data.status
        doc.reviewed_by_id = reviewer_id
        doc.reviewed_at = now

        if data.status == CheckInDocStatus.APPROVED:
            doc.rejection_reason = None
            if doc.assignment:
                if doc.doc_type == CheckInDocType.REMOVAL_REQUEST:
                    # Final check in approved: remove category & frequency from person
                    doc.assignment.status = AssignmentStatus.REMOVED
                else:
                    # Regular check in approved: calculate next check-in deadline
                    doc.assignment.next_check_in_due = doc.check_in_date + timedelta(
                        days=doc.assignment.frequency_days
                    )
        elif data.status == CheckInDocStatus.REJECTED:
            doc.rejection_reason = data.rejection_reason

        await db.commit()
        await db.refresh(doc)

        return await cls.get_document_by_id(
            doc.id,
            caller_role=UserRole.ADMIN,
            caller_mahalla_id=None,
            db=db,
        )

    @classmethod
    async def get_documents(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        status: Optional[CheckInDocStatus] = None,
        doc_type: Optional[CheckInDocType] = None,
        mahalla_id: Optional[int] = None,
        category_id: Optional[int] = None,
        person_id: Optional[int] = None,
        assignment_id: Optional[int] = None,
        remaining_days: Optional[int] = None,
        days_remaining: Optional[int] = None,
        caller_role: UserRole = UserRole.ADMIN,
        caller_mahalla_id: Optional[int] = None,
    ) -> PaginatedDocumentSchema:
        query = select(CheckInDocument).options(
            selectinload(CheckInDocument.assignment),
            selectinload(CheckInDocument.person),
            selectinload(CheckInDocument.category),
            selectinload(CheckInDocument.mahalla),
            selectinload(CheckInDocument.submitted_by),
            selectinload(CheckInDocument.reviewed_by),
        )
        count_query = select(func.count(CheckInDocument.id))

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(CheckInDocument.mahalla_id == mahalla_id)
                count_query = count_query.where(CheckInDocument.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            # Rais sees all docs in their own mahalla
            query = query.where(CheckInDocument.mahalla_id == caller_mahalla_id)
            count_query = count_query.where(CheckInDocument.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            # Mahalla 7 member sees docs in their own mahalla for their category
            query = query.join(CheckInDocument.category).where(
                CheckInDocument.mahalla_id == caller_mahalla_id
            )
            count_query = count_query.join(CheckInDocument.category).where(
                CheckInDocument.mahalla_id == caller_mahalla_id
            )

        if status:
            query = query.where(CheckInDocument.status == status)
            count_query = count_query.where(CheckInDocument.status == status)

        if doc_type:
            query = query.where(CheckInDocument.doc_type == doc_type)
            count_query = count_query.where(CheckInDocument.doc_type == doc_type)

        if category_id:
            query = query.where(CheckInDocument.category_id == category_id)
            count_query = count_query.where(CheckInDocument.category_id == category_id)

        if person_id:
            query = query.where(CheckInDocument.person_id == person_id)
            count_query = count_query.where(CheckInDocument.person_id == person_id)

        if assignment_id:
            query = query.where(CheckInDocument.assignment_id == assignment_id)
            count_query = count_query.where(CheckInDocument.assignment_id == assignment_id)

        actual_remaining_days = remaining_days if remaining_days is not None else days_remaining
        if actual_remaining_days is not None:
            today = date.today()
            target_due = today + timedelta(days=actual_remaining_days)
            query = query.outerjoin(
                PersonCategoryAssignment,
                CheckInDocument.assignment_id == PersonCategoryAssignment.id,
            ).where(
                func.coalesce(CheckInDocument.due_date, PersonCategoryAssignment.next_check_in_due) == target_due
            )
            count_query = count_query.outerjoin(
                PersonCategoryAssignment,
                CheckInDocument.assignment_id == PersonCategoryAssignment.id,
            ).where(
                func.coalesce(CheckInDocument.due_date, PersonCategoryAssignment.next_check_in_due) == target_due
            )

        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(CheckInDocument.created_at.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        docs = result.scalars().all()

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        items = [cls._format_document(d) for d in docs]

        return PaginatedDocumentSchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    async def get_document_by_id(
        cls,
        document_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> DocumentResponseSchema:
        query = (
            select(CheckInDocument)
            .where(CheckInDocument.id == document_id)
            .options(
                selectinload(CheckInDocument.person),
                selectinload(CheckInDocument.category),
                selectinload(CheckInDocument.mahalla),
                selectinload(CheckInDocument.submitted_by),
                selectinload(CheckInDocument.reviewed_by),
            )
        )
        doc = (await db.execute(query)).scalar_one_or_none()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in document not found",
            )

        # RBAC Check
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if doc.mahalla_id != caller_mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot view documents from another mahalla",
                )

        return cls._format_document(doc)

    @classmethod
    async def delete_document(
        cls,
        document_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> bool:
        doc = await db.get(CheckInDocument, document_id)
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in document not found",
            )

        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if caller_role == UserRole.MAHALLA_RAISI:
                if doc.mahalla_id != caller_mahalla_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Rais can only delete documents in their own Mahalla",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to delete document",
                )

        photo_url = doc.photo_url
        pdf_url = doc.pdf_url

        await db.delete(doc)
        await db.commit()

        # Fallback explicit deletion
        if photo_url:
            FileService.delete_file_by_url_or_path(photo_url)
        if pdf_url:
            FileService.delete_file_by_url_or_path(pdf_url)

        return True

