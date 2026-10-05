import math
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func, or_, and_, String, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.files.service import FileService
from backend.documents.schemas import (
    DocumentReviewSchema,
    DocumentUpdateSchema,
    DocumentResponseSchema,
    PaginatedDocumentSchema,
)
from db.models.document import CheckInDocument, CheckInDocType, CheckInDocStatus
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.category import Category
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
        seen_by_name = (
            f"{doc.seen_by.first_name} {doc.seen_by.last_name}"
            if doc.seen_by
            else None
        )

        today = date.today()
        days_remaining = None
        effective_due = doc.new_date if (doc.new_date and doc.status == CheckInDocStatus.APPROVED) else doc.due_date
        if effective_due:
            days_remaining = (effective_due - today).days
        elif getattr(doc, "assignment", None) and doc.assignment and doc.assignment.next_check_in_due:
            days_remaining = (doc.assignment.next_check_in_due - today).days

        submitter_is_prokuror = bool(
            doc.submitted_by and doc.submitted_by.role in [UserRole.PROKUROR, UserRole.ADMIN]
        )

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
            is_from_prokuror=submitter_is_prokuror,
            doc_type=doc.doc_type,
            photo_url=doc.photo_url,
            pdf_url=doc.pdf_url,
            notes=doc.notes,
            description=doc.notes,
            check_in_date=doc.check_in_date,
            due_date=doc.due_date,
            previous_date=doc.previous_date,
            requested_date=doc.requested_date,
            new_date=doc.new_date,
            frequency_days=doc.frequency_days,
            days_remaining=days_remaining,
            status=doc.status,
            rejection_reason=doc.rejection_reason,
            reviewed_by_id=doc.reviewed_by_id,
            reviewed_by_name=reviewer_name,
            reviewed_at=doc.reviewed_at,
            seen_at=doc.seen_at,
            seen_by_id=doc.seen_by_id,
            seen_by_name=seen_by_name,
            is_seen=doc.seen_at is not None,
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
        new_date: Optional[date] = None,
        requested_date: Optional[date] = None,
        previous_date: Optional[date] = None,
        frequency_days: Optional[int] = None,
        frequency_day: Optional[int] = None,
        document_id: Optional[int] = None,
    ) -> DocumentResponseSchema:
        if document_id:
            existing_doc = await db.scalar(
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
            if not existing_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Referenced document not found",
                )
            target_ext_date = requested_date or new_date
            if target_ext_date:
                existing_doc.requested_date = target_ext_date
                existing_doc.doc_type = CheckInDocType.REQUEST_EXTENSION
                if not existing_doc.previous_date:
                    existing_doc.previous_date = existing_doc.due_date
            if notes:
                existing_doc.notes = f"{existing_doc.notes}\n\n[Extension Request]: {notes}" if existing_doc.notes else notes
            await db.commit()
            await db.refresh(existing_doc)
            return await cls.get_document_by_id(
                existing_doc.id,
                caller_role=UserRole.ADMIN,
                caller_mahalla_id=None,
                db=db,
            )

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

        if not notes or not notes.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Description is required",
            )

        is_prokuror = caller_role in [UserRole.ADMIN, UserRole.PROKUROR]
        effective_freq = frequency_days or frequency_day

        if not assignment.frequency_days and not effective_freq and not new_date and not requested_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ushbu shaxsning kategoriyasi uchun dastlabki tekshiruv chastotasi belgilanmagan. Iltimos, hujjat yaratishdan oldin chastota (frequency_days) ni kiriting.",
            )

        if is_prokuror:
            # Prokuror sends docs for employers: outside regular frequency with optional frequency day
            if effective_freq:
                doc_due_date = check_in_date + timedelta(days=effective_freq)
            elif new_date or requested_date:
                doc_due_date = new_date or requested_date
            else:
                doc_due_date = assignment.next_check_in_due
            doc_frequency_days = effective_freq
            doc_new_date = new_date or (doc_due_date if effective_freq else None)
            doc_requested_date = requested_date
            # Update assignment's current due date to match this new task's deadline
            if assignment:
                if not assignment.frequency_days and effective_freq:
                    assignment.frequency_days = effective_freq
                assignment.next_check_in_due = doc_due_date
        else:
            # Employers docs are in frequency decided by prokuror
            doc_frequency_days = None
            doc_due_date = assignment.next_check_in_due
            doc_new_date = new_date if doc_type != CheckInDocType.REQUEST_EXTENSION else None
            doc_requested_date = requested_date or (new_date if doc_type == CheckInDocType.REQUEST_EXTENSION else None)

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
            due_date=doc_due_date,
            frequency_days=doc_frequency_days,
            previous_date=previous_date or assignment.next_check_in_due,
            requested_date=doc_requested_date,
            new_date=doc_new_date,
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

        effective_new_date = data.new_date
        if effective_new_date:
            if not doc.previous_date and doc.assignment:
                doc.previous_date = doc.assignment.next_check_in_due
            doc.new_date = effective_new_date

        if data.status == CheckInDocStatus.APPROVED:
            doc.rejection_reason = None
            is_prokuror_doc = bool(
                doc.submitted_by and doc.submitted_by.role in [UserRole.PROKUROR, UserRole.ADMIN]
            )
            if is_prokuror_doc:
                # Prokuror-sent document is outside regular frequency:
                # Update document's deadline without altering assignment's regular schedule
                final_date = (
                    effective_new_date
                    or (doc.requested_date if doc.doc_type == CheckInDocType.REQUEST_EXTENSION else doc.new_date)
                    or doc.requested_date
                    or doc.new_date
                )
                if final_date:
                    doc.due_date = final_date
                    doc.new_date = final_date
            else:
                # Employers docs: follow frequency decided by prokuror or requested extension
                if doc.assignment:
                    if doc.doc_type == CheckInDocType.REMOVAL_REQUEST:
                        # Final check in approved: remove category & frequency from person
                        doc.assignment.status = AssignmentStatus.REMOVED
                    elif effective_new_date:
                        # Explicit new date provided by reviewer
                        doc.assignment.next_check_in_due = effective_new_date
                        doc.due_date = effective_new_date
                        doc.new_date = effective_new_date
                    elif doc.requested_date or doc.new_date:
                        # Requested date from submission approved
                        target = (
                            doc.requested_date
                            if doc.doc_type == CheckInDocType.REQUEST_EXTENSION
                            else (doc.new_date or doc.requested_date)
                        )
                        doc.assignment.next_check_in_due = target
                        doc.due_date = target
                        doc.new_date = target
                    else:
                        # Regular check in approved: calculate next check-in deadline by prokuror's decided frequency
                        if doc.assignment.frequency_days is not None:
                            doc.assignment.next_check_in_due = doc.check_in_date + timedelta(
                                days=doc.assignment.frequency_days
                            )
                            doc.new_date = doc.assignment.next_check_in_due
                            doc.due_date = doc.assignment.next_check_in_due
                        else:
                            # One-time assignment completed
                            doc.assignment.status = AssignmentStatus.COMPLETED
                            doc.assignment.next_check_in_due = None
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
    async def update_document(
        cls,
        document_id: int,
        data: DocumentUpdateSchema,
        editor_id: int,
        db: AsyncSession,
        caller_role: UserRole = UserRole.ADMIN,
        caller_mahalla_id: Optional[int] = None,
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
                selectinload(CheckInDocument.reviewed_by),
                selectinload(CheckInDocument.seen_by),
            )
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in document not found",
            )

        is_prokuror = caller_role in [UserRole.ADMIN, UserRole.PROKUROR]
        if not is_prokuror:
            if doc.mahalla_id != caller_mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot modify document from another mahalla",
                )
            if caller_role != UserRole.MAHALLA_RAISI:
                assigned_roles = (
                    doc.assignment.assigned_roles if doc.assignment and doc.assignment.assigned_roles
                    else (doc.category.assigned_roles if doc.category else [])
                )
                if caller_role.value not in assigned_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to modify this document",
                    )
            if (
                data.new_date is not None
                or data.previous_date is not None
                or data.frequency_days is not None
                or data.frequency_day is not None
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Employers can only request an extension (requested_date), not set new_date directly",
                )

        if data.previous_date is not None:
            doc.previous_date = data.previous_date

        if data.requested_date is not None:
            if not doc.previous_date:
                doc.previous_date = doc.due_date or (doc.assignment.next_check_in_due if doc.assignment else None)
            doc.requested_date = data.requested_date
            doc.doc_type = CheckInDocType.REQUEST_EXTENSION

        effective_freq = data.frequency_days or data.frequency_day
        if effective_freq is not None:
            doc.frequency_days = effective_freq
            calc_date = doc.check_in_date + timedelta(days=effective_freq)
            doc.due_date = calc_date
            doc.new_date = calc_date

        effective_new_date = data.new_date
        if effective_new_date is not None:
            if doc.previous_date is None:
                if doc.assignment:
                    doc.previous_date = doc.assignment.next_check_in_due
                elif doc.due_date:
                    doc.previous_date = doc.due_date
            doc.new_date = effective_new_date
            doc.due_date = effective_new_date
            is_prokuror_doc = bool(
                doc.submitted_by and doc.submitted_by.role in [UserRole.PROKUROR, UserRole.ADMIN]
            )
            if doc.assignment:
                doc.assignment.next_check_in_due = effective_new_date

        if data.check_in_date is not None:
            doc.check_in_date = data.check_in_date

        new_notes = (data.description or "").strip() or (data.notes or "").strip()
        if new_notes:
            doc.notes = new_notes

        await db.commit()
        await db.refresh(doc)

        return await cls.get_document_by_id(
            doc.id,
            caller_role=UserRole.ADMIN,
            caller_mahalla_id=None,
            db=db,
        )

    @classmethod
    async def request_document_extension(
        cls,
        document_id: int,
        requested_date: date,
        description: Optional[str],
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
        photo_file: Optional[UploadFile] = None,
        pdf_file: Optional[UploadFile] = None,
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
                selectinload(CheckInDocument.reviewed_by),
                selectinload(CheckInDocument.seen_by),
            )
        )
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Check-in document not found",
            )

        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if doc.mahalla_id != caller_mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot request extension for document of another mahalla",
                )
            if caller_role != UserRole.MAHALLA_RAISI:
                assigned_roles = (
                    doc.assignment.assigned_roles if doc.assignment and doc.assignment.assigned_roles
                    else (doc.category.assigned_roles if doc.category else [])
                )
                if caller_role.value not in assigned_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized to request extension for this document",
                    )

        if not doc.previous_date:
            doc.previous_date = doc.due_date or (doc.assignment.next_check_in_due if doc.assignment else None)

        doc.requested_date = requested_date
        doc.doc_type = CheckInDocType.REQUEST_EXTENSION

        if description:
            doc.notes = f"{doc.notes}\n\n[Extension Request]: {description}" if doc.notes else description

        if photo_file and photo_file.filename:
            doc.photo_url = await FileService.save_uploaded_photo(photo_file)
        if pdf_file and pdf_file.filename:
            doc.pdf_url = await FileService.save_uploaded_pdf(pdf_file)

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
        latest_only: Optional[bool] = None,
        caller_role: UserRole = UserRole.ADMIN,
        caller_mahalla_id: Optional[int] = None,
        caller_id: Optional[int] = None,
    ) -> PaginatedDocumentSchema:
        query = select(CheckInDocument).options(
            selectinload(CheckInDocument.assignment),
            selectinload(CheckInDocument.person),
            selectinload(CheckInDocument.category),
            selectinload(CheckInDocument.mahalla),
            selectinload(CheckInDocument.submitted_by),
            selectinload(CheckInDocument.reviewed_by),
            selectinload(CheckInDocument.seen_by),
        )
        count_query = select(func.count(CheckInDocument.id))

        has_assignment_joined = False
        has_category_joined = False

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
            # Mahalla 7 member sees ONLY their own documents in their own mahalla
            role_val = caller_role.value if hasattr(caller_role, "value") else str(caller_role)
            if not has_assignment_joined:
                query = query.outerjoin(
                    PersonCategoryAssignment,
                    CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                )
                count_query = count_query.outerjoin(
                    PersonCategoryAssignment,
                    CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                )
                has_assignment_joined = True

            if not has_category_joined:
                query = query.join(
                    Category,
                    CheckInDocument.category_id == Category.id,
                )
                count_query = count_query.join(
                    Category,
                    CheckInDocument.category_id == Category.id,
                )
                has_category_joined = True

            role_condition = or_(
                and_(
                    PersonCategoryAssignment.assigned_roles.isnot(None),
                    PersonCategoryAssignment.assigned_roles.cast(String).like(f'%"{role_val}"%'),
                ),
                and_(
                    or_(
                        PersonCategoryAssignment.assigned_roles.is_(None),
                        PersonCategoryAssignment.assigned_roles.cast(String) == "[]",
                    ),
                    Category.assigned_roles.cast(String).like(f'%"{role_val}"%'),
                ),
            )
            if caller_id is not None:
                role_condition = or_(
                    CheckInDocument.submitted_by_id == caller_id,
                    role_condition,
                )

            query = query.where(
                CheckInDocument.mahalla_id == caller_mahalla_id,
                role_condition,
            )
            count_query = count_query.where(
                CheckInDocument.mahalla_id == caller_mahalla_id,
                role_condition,
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
        target_due = None
        if actual_remaining_days is not None:
            today = date.today()
            target_due = today + timedelta(days=actual_remaining_days)
            if not has_assignment_joined:
                query = query.outerjoin(
                    PersonCategoryAssignment,
                    CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                )
                count_query = count_query.outerjoin(
                    PersonCategoryAssignment,
                    CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                )
                has_assignment_joined = True
            doc_effective_due = func.coalesce(
                case(
                    (
                        and_(
                            CheckInDocument.status == CheckInDocStatus.APPROVED,
                            CheckInDocument.new_date.isnot(None),
                        ),
                        CheckInDocument.new_date,
                    ),
                    else_=CheckInDocument.due_date,
                ),
                PersonCategoryAssignment.next_check_in_due,
            )
            if actual_remaining_days < 0:
                query = query.where(doc_effective_due < today)
                count_query = count_query.where(doc_effective_due < today)
            else:
                query = query.where(doc_effective_due == target_due)
                count_query = count_query.where(doc_effective_due == target_due)

        # When filtering by remaining_days, default to latest document per assignment to prevent duplicate person entries
        is_latest_only = latest_only if latest_only is not None else (actual_remaining_days is not None)
        if is_latest_only:
            latest_subq = select(func.max(CheckInDocument.id))
            if status:
                latest_subq = latest_subq.where(CheckInDocument.status == status)
            if target_due is not None:
                doc_effective_due_sub = func.coalesce(
                    case(
                        (
                            and_(
                                CheckInDocument.status == CheckInDocStatus.APPROVED,
                                CheckInDocument.new_date.isnot(None),
                            ),
                            CheckInDocument.new_date,
                        ),
                        else_=CheckInDocument.due_date,
                    ),
                    PersonCategoryAssignment.next_check_in_due,
                )
                if actual_remaining_days < 0:
                    latest_subq = latest_subq.outerjoin(
                        PersonCategoryAssignment,
                        CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                    ).where(doc_effective_due_sub < date.today())
                else:
                    latest_subq = latest_subq.outerjoin(
                        PersonCategoryAssignment,
                        CheckInDocument.assignment_id == PersonCategoryAssignment.id,
                    ).where(doc_effective_due_sub == target_due)
            latest_subq = latest_subq.group_by(CheckInDocument.assignment_id).scalar_subquery()

            query = query.where(CheckInDocument.id.in_(latest_subq))
            count_query = count_query.where(CheckInDocument.id.in_(latest_subq))

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
        caller_id: Optional[int] = None,
    ) -> DocumentResponseSchema:
        query = (
            select(CheckInDocument)
            .where(CheckInDocument.id == document_id)
            .options(
                selectinload(CheckInDocument.assignment),
                selectinload(CheckInDocument.assignment).selectinload(PersonCategoryAssignment.category),
                selectinload(CheckInDocument.person),
                selectinload(CheckInDocument.category),
                selectinload(CheckInDocument.mahalla),
                selectinload(CheckInDocument.submitted_by),
                selectinload(CheckInDocument.reviewed_by),
                selectinload(CheckInDocument.seen_by),
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

        # If Mahalla official views document created by Prokuror / Admin:
        # Mark seen_at and seen_by_id, and mark completed (approved)
        # Determine assigned roles for this document/assignment
        assigned_roles = []
        if doc.assignment and doc.assignment.assigned_roles:
            assigned_roles = doc.assignment.assigned_roles
        elif doc.assignment and doc.assignment.category and doc.assignment.category.assigned_roles:
            assigned_roles = doc.assignment.category.assigned_roles
        elif doc.category and doc.category.assigned_roles:
            assigned_roles = doc.category.assigned_roles

        assigned_role_values = {
            r.value if hasattr(r, "value") else str(r)
            for r in assigned_roles
        }
        caller_role_value = caller_role.value if hasattr(caller_role, "value") else str(caller_role)

        # When the employee assigned to this role views a document sent by Prokuror / Admin:
        # Mark as seen (seen_at, seen_by_id), but DO NOT mark completed (status remains pending).
        if (
            caller_role_value in assigned_role_values
            and doc.mahalla_id == caller_mahalla_id
            and doc.submitted_by
            and doc.submitted_by.role in [UserRole.PROKUROR, UserRole.ADMIN]
        ):
            if doc.seen_at is None:
                doc.seen_at = datetime.now()
                doc.seen_by_id = caller_id
                seen_user = None
                if caller_id:
                    seen_user = await db.get(User, caller_id)
                    doc.seen_by = seen_user
                await db.commit()
                if seen_user:
                    doc.seen_by = seen_user

        return cls._format_document(doc)

    @classmethod
    async def mark_document_seen(
        cls,
        document_id: int,
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> DocumentResponseSchema:
        return await cls.get_document_by_id(
            document_id=document_id,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
            db=db,
            caller_id=caller_id,
        )

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
