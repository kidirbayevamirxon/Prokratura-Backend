import math
from datetime import date, timedelta
from typing import Optional, List, Sequence
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_, and_, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.persons.schemas import (
    PersonCreateSchema,
    PersonUpdateSchema,
    AssignmentCreateSchema,
    AssignmentUpdateSchema,
    AssignmentResponseSchema,
    RemainingDaysStatsSchema,
    PersonResponseSchema,
    PaginatedPersonSchema,
)
from db.models.person import Person
from db.models.category import Category
from db.models.mahalla import Mahalla
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.document import CheckInDocument, CheckInDocStatus
from db.models.user import UserRole, MAHALLA_SEVEN_ROLES


class PersonService:
    @staticmethod
    def _format_assignment(assignment: PersonCategoryAssignment) -> AssignmentResponseSchema:
        today = date.today()
        is_overdue = (
            assignment.status == AssignmentStatus.ACTIVE
            and assignment.next_check_in_due < today
        )
        assigned_roles = assignment.assigned_roles
        if not assigned_roles and assignment.category:
            assigned_roles = assignment.category.assigned_roles or []

        days_remaining = (assignment.next_check_in_due - today).days

        return AssignmentResponseSchema(
            id=assignment.id,
            person_id=assignment.person_id,
            category_id=assignment.category_id,
            category_name=assignment.category.name if assignment.category else "",
            mahalla_id=assignment.mahalla_id,
            frequency_days=assignment.frequency_days,
            assigned_roles=assigned_roles or [],
            next_check_in_due=assignment.next_check_in_due,
            days_remaining=days_remaining,
            is_overdue=is_overdue,
            status=assignment.status,
            created_at=assignment.created_at,
        )

    @classmethod
    def _format_person(
        cls, person: Person, assignments: Optional[Sequence[PersonCategoryAssignment]] = None
    ) -> PersonResponseSchema:
        ass_list = assignments if assignments is not None else (person.assignments or [])
        assignments_formatted = [
            cls._format_assignment(a) for a in ass_list
        ]
        return PersonResponseSchema(
            id=person.id,
            full_name=person.full_name,
            birth_date=person.birth_date,
            mahalla_id=person.mahalla_id,
            mahalla_name=person.mahalla.name if person.mahalla else None,
            is_active=person.is_active,
            assignments=assignments_formatted,
            created_at=person.created_at,
            updated_at=person.updated_at,
        )

    @classmethod
    async def create_person(
        cls, data: PersonCreateSchema, db: AsyncSession
    ) -> PersonResponseSchema:
        mahalla_res = await db.execute(
            select(Mahalla).where(Mahalla.id == data.mahalla_id)
        )
        mahalla = mahalla_res.scalar_one_or_none()
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {data.mahalla_id} not found",
            )

        new_person = Person(
            full_name=data.full_name.strip(),
            birth_date=data.birth_date,
            mahalla_id=data.mahalla_id,
            is_active=True,
        )
        db.add(new_person)
        await db.commit()
        await db.refresh(new_person)

        new_person.mahalla = mahalla
        return cls._format_person(new_person, assignments=[])

    @classmethod
    async def assign_category(
        cls,
        person_id: int,
        data: AssignmentCreateSchema,
        created_by_id: int,
        db: AsyncSession,
    ) -> AssignmentResponseSchema:
        person = await db.scalar(select(Person).where(Person.id == person_id))
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        category = await db.scalar(
            select(Category).where(Category.id == data.category_id)
        )
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )

        # Check existing active assignment directly in DB
        existing_assignment = await db.scalar(
            select(PersonCategoryAssignment.id).where(
                PersonCategoryAssignment.person_id == person_id,
                PersonCategoryAssignment.category_id == data.category_id,
                PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        if existing_assignment:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Person is already actively assigned to category '{category.name}'",
            )

        # Inherit assigned roles directly from category
        assigned_roles = category.assigned_roles or []

        next_due = date.today() + timedelta(days=data.frequency_days)

        assignment = PersonCategoryAssignment(
            person_id=person.id,
            category_id=category.id,
            mahalla_id=person.mahalla_id,
            frequency_days=data.frequency_days,
            assigned_roles=assigned_roles,
            next_check_in_due=next_due,
            status=AssignmentStatus.ACTIVE,
            created_by_id=created_by_id,
        )
        db.add(assignment)
        await db.commit()
        await db.refresh(assignment)

        assignment.category = category
        return cls._format_assignment(assignment)

    @classmethod
    async def update_assignment(
        cls,
        assignment_id: int,
        data: AssignmentUpdateSchema,
        editor_id: int,
        db: AsyncSession,
        person_id: Optional[int] = None,
    ) -> AssignmentResponseSchema:
        query = (
            select(PersonCategoryAssignment)
            .where(PersonCategoryAssignment.id == assignment_id)
            .options(selectinload(PersonCategoryAssignment.category))
        )
        if person_id is not None:
            query = query.where(PersonCategoryAssignment.person_id == person_id)

        assignment = await db.scalar(query)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found",
            )

        if data.frequency_days is not None:
            assignment.frequency_days = data.frequency_days

        if data.next_check_in_due is not None:
            assignment.next_check_in_due = data.next_check_in_due

        await db.commit()
        await db.refresh(assignment)
        return cls._format_assignment(assignment)

    @classmethod
    async def update_person_category_assignment(
        cls,
        person_id: int,
        data: AssignmentUpdateSchema,
        editor_id: int,
        db: AsyncSession,
    ) -> AssignmentResponseSchema:
        if data.category_id:
            assignment = await db.scalar(
                select(PersonCategoryAssignment)
                .where(
                    PersonCategoryAssignment.person_id == person_id,
                    PersonCategoryAssignment.category_id == data.category_id,
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                )
                .options(selectinload(PersonCategoryAssignment.category))
            )
            if not assignment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Active assignment for category {data.category_id} not found for person {person_id}",
                )
        else:
            active_assignments = (
                await db.scalars(
                    select(PersonCategoryAssignment)
                    .where(
                        PersonCategoryAssignment.person_id == person_id,
                        PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    )
                    .options(selectinload(PersonCategoryAssignment.category))
                )
            ).all()
            if not active_assignments:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active category assignment found for this person",
                )
            if len(active_assignments) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Person has multiple active assignments; please specify 'category_id'",
                )
            assignment = active_assignments[0]

        if data.frequency_days is not None:
            assignment.frequency_days = data.frequency_days

        if data.next_check_in_due is not None:
            assignment.next_check_in_due = data.next_check_in_due

        await db.commit()
        await db.refresh(assignment)
        return cls._format_assignment(assignment)


    @classmethod
    async def get_persons(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        mahalla_id: Optional[int] = None,
        category_id: Optional[int] = None,
        remaining_days: Optional[int] = None,
        days_remaining: Optional[int] = None,
        caller_role: UserRole = UserRole.ADMIN,
        caller_mahalla_id: Optional[int] = None,
    ) -> PaginatedPersonSchema:
        query = select(Person).options(selectinload(Person.mahalla))
        count_query = select(func.count(func.distinct(Person.id)))

        actual_remaining_days = remaining_days if remaining_days is not None else days_remaining

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(Person.mahalla_id == mahalla_id)
                count_query = count_query.where(Person.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            if caller_mahalla_id is None:
                return PaginatedPersonSchema(
                    items=[], total=0, page=page, page_size=page_size, total_pages=1
                )
            query = query.where(Person.mahalla_id == caller_mahalla_id)
            count_query = count_query.where(Person.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            if caller_mahalla_id is None:
                return PaginatedPersonSchema(
                    items=[], total=0, page=page, page_size=page_size, total_pages=1
                )
            role_val = caller_role.value if hasattr(caller_role, "value") else str(caller_role)
            role_condition = or_(
                and_(
                    PersonCategoryAssignment.assigned_roles.isnot(None),
                    PersonCategoryAssignment.assigned_roles.cast(String).like(f"%\"{role_val}\"%"),
                ),
                and_(
                    or_(
                        PersonCategoryAssignment.assigned_roles.is_(None),
                        PersonCategoryAssignment.assigned_roles.cast(String) == "[]",
                    ),
                    Category.assigned_roles.cast(String).like(f"%\"{role_val}\"%"),
                ),
            )
            own_conditions = [
                PersonCategoryAssignment.person_id == Person.id,
                PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                role_condition,
            ]
            if category_id:
                own_conditions.append(PersonCategoryAssignment.category_id == category_id)
            if actual_remaining_days is not None:
                today = date.today()
                target_due = today + timedelta(days=actual_remaining_days)
                own_conditions.append(PersonCategoryAssignment.next_check_in_due == target_due)

            has_own_assignment = (
                select(1)
                .select_from(PersonCategoryAssignment)
                .join(Category, PersonCategoryAssignment.category_id == Category.id)
                .where(*own_conditions)
                .exists()
            )
            query = query.where(
                Person.mahalla_id == caller_mahalla_id,
                has_own_assignment,
            )
            count_query = count_query.where(
                Person.mahalla_id == caller_mahalla_id,
                has_own_assignment,
            )

        if search:
            pattern = f"%{search}%"
            query = query.where(Person.full_name.ilike(pattern))
            count_query = count_query.where(Person.full_name.ilike(pattern))

        # Category and remaining_days filters for non-seven-member callers (Admin, Prokuror, Rais)
        if caller_role not in MAHALLA_SEVEN_ROLES or caller_role == UserRole.MAHALLA_RAISI:
            if category_id:
                query = query.join(Person.assignments).where(
                    PersonCategoryAssignment.category_id == category_id
                )
                count_query = count_query.join(Person.assignments).where(
                    PersonCategoryAssignment.category_id == category_id
                )

            if actual_remaining_days is not None:
                today = date.today()
                target_due = today + timedelta(days=actual_remaining_days)
                if not category_id:
                    query = query.join(Person.assignments)
                    count_query = count_query.join(Person.assignments)
                query = query.where(
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    PersonCategoryAssignment.next_check_in_due == target_due,
                )
                count_query = count_query.where(
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    PersonCategoryAssignment.next_check_in_due == target_due,
                )

        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(Person.id.desc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        persons = result.scalars().unique().all()

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        person_ids = [p.id for p in persons]
        assignments_map = {pid: [] for pid in person_ids}
        if person_ids:
            all_assignments = (
                await db.scalars(
                    select(PersonCategoryAssignment)
                    .where(PersonCategoryAssignment.person_id.in_(person_ids))
                    .options(selectinload(PersonCategoryAssignment.category))
                    .order_by(PersonCategoryAssignment.created_at.desc())
                )
            ).all()
            if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
                role_val = caller_role.value if hasattr(caller_role, "value") else str(caller_role)
                for a in all_assignments:
                    roles = a.assigned_roles or (a.category.assigned_roles if a.category else [])
                    if role_val in roles:
                        assignments_map[a.person_id].append(a)
            else:
                for a in all_assignments:
                    assignments_map[a.person_id].append(a)

        items = [cls._format_person(p, assignments=assignments_map.get(p.id, [])) for p in persons]

        return PaginatedPersonSchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    async def get_person_by_id(
        cls,
        person_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> PersonResponseSchema:
        query = select(Person).where(Person.id == person_id).options(selectinload(Person.mahalla))
        person = (await db.execute(query)).scalar_one_or_none()
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        # RBAC Check
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if person.mahalla_id != caller_mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot view persons from other mahallas",
                )

        assignments = (
            await db.scalars(
                select(PersonCategoryAssignment)
                .where(PersonCategoryAssignment.person_id == person.id)
                .options(selectinload(PersonCategoryAssignment.category))
                .order_by(PersonCategoryAssignment.created_at.desc())
            )
        ).all()

        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            role_val = caller_role.value if hasattr(caller_role, "value") else str(caller_role)
            has_active_own = any(
                a.status == AssignmentStatus.ACTIVE
                and role_val in (a.assigned_roles or (a.category.assigned_roles if a.category else []))
                for a in assignments
            )
            if not has_active_own:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this person",
                )
            assignments = [
                a for a in assignments
                if role_val in (a.assigned_roles or (a.category.assigned_roles if a.category else []))
            ]

        return cls._format_person(person, assignments=assignments)

    @classmethod
    async def update_person(
        cls,
        person_id: int,
        data: PersonUpdateSchema,
        db: AsyncSession,
    ) -> PersonResponseSchema:
        person = (
            await db.execute(select(Person).where(Person.id == person_id).options(selectinload(Person.mahalla)))
        ).scalar_one_or_none()
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found",
            )

        if data.full_name is not None:
            person.full_name = data.full_name.strip()
        if data.birth_date is not None:
            person.birth_date = data.birth_date
        if data.mahalla_id is not None:
            mahalla = await db.scalar(select(Mahalla).where(Mahalla.id == data.mahalla_id))
            if not mahalla:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mahalla with id {data.mahalla_id} not found",
                )
            person.mahalla_id = data.mahalla_id
            person.mahalla = mahalla
        if data.is_active is not None:
            person.is_active = data.is_active

        await db.commit()
        await db.refresh(person)

        assignments = (
            await db.scalars(
                select(PersonCategoryAssignment)
                .where(PersonCategoryAssignment.person_id == person.id)
                .options(selectinload(PersonCategoryAssignment.category))
            )
        ).all()
        return cls._format_person(person, assignments=assignments)

    @classmethod
    async def get_assignments(
        cls,
        db: AsyncSession,
        mahalla_id: Optional[int] = None,
        category_id: Optional[int] = None,
        status_filter: Optional[AssignmentStatus] = None,
        overdue_only: bool = False,
        days_remaining: Optional[int] = None,
        min_days_remaining: Optional[int] = None,
        max_days_remaining: Optional[int] = None,
        caller_role: UserRole = UserRole.ADMIN,
        caller_mahalla_id: Optional[int] = None,
    ) -> List[AssignmentResponseSchema]:
        query = select(PersonCategoryAssignment).options(
            selectinload(PersonCategoryAssignment.category)
        )

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(PersonCategoryAssignment.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            query = query.where(PersonCategoryAssignment.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            query = query.where(PersonCategoryAssignment.mahalla_id == caller_mahalla_id)

        if category_id:
            query = query.where(PersonCategoryAssignment.category_id == category_id)

        if status_filter:
            query = query.where(PersonCategoryAssignment.status == status_filter)

        today = date.today()
        if overdue_only:
            query = query.where(
                PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                PersonCategoryAssignment.next_check_in_due < today,
            )

        if days_remaining is not None:
            target_due = today + timedelta(days=days_remaining)
            query = query.where(PersonCategoryAssignment.next_check_in_due == target_due)

        if min_days_remaining is not None:
            min_due = today + timedelta(days=min_days_remaining)
            query = query.where(PersonCategoryAssignment.next_check_in_due >= min_due)

        if max_days_remaining is not None:
            max_due = today + timedelta(days=max_days_remaining)
            query = query.where(PersonCategoryAssignment.next_check_in_due <= max_due)

        query = query.order_by(PersonCategoryAssignment.next_check_in_due.asc())
        assignments = (await db.execute(query)).scalars().all()

        # If Mahalla 7 worker, only return those assignments matching their role
        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            role_val = caller_role.value
            filtered = []
            for a in assignments:
                roles = a.assigned_roles or (a.category.assigned_roles if a.category else [])
                if role_val in roles:
                    filtered.append(a)
            assignments = filtered

        return [cls._format_assignment(a) for a in assignments]

    @classmethod
    async def get_remaining_days_stats(
        cls,
        max_days: int,
        mahalla_id: Optional[int],
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> RemainingDaysStatsSchema:
        query = select(PersonCategoryAssignment).options(
            selectinload(PersonCategoryAssignment.category)
        ).where(PersonCategoryAssignment.status == AssignmentStatus.ACTIVE)

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(PersonCategoryAssignment.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            query = query.where(PersonCategoryAssignment.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            query = query.where(PersonCategoryAssignment.mahalla_id == caller_mahalla_id)

        assignments = (await db.execute(query)).scalars().all()

        # If Mahalla 7 worker, filter by role
        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            role_val = caller_role.value
            assignments = [
                a for a in assignments
                if role_val in (a.assigned_roles or (a.category.assigned_roles if a.category else []))
            ]

        today = date.today()
        overdue_count = 0
        today_count = 0
        by_day = {d: 0 for d in range(0, max_days + 1)}
        later_count = 0

        for a in assignments:
            diff = (a.next_check_in_due - today).days
            if diff < 0:
                overdue_count += 1
            elif diff == 0:
                today_count += 1
                by_day[0] += 1
            elif 1 <= diff <= max_days:
                by_day[diff] += 1
            else:
                later_count += 1

        # 2. Query CheckInDocument for the 6 top KPI cards (Image red circle)
        doc_query = select(CheckInDocument).options(
            selectinload(CheckInDocument.assignment).selectinload(PersonCategoryAssignment.category)
        )
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                doc_query = doc_query.where(CheckInDocument.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            doc_query = doc_query.where(CheckInDocument.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            doc_query = doc_query.where(CheckInDocument.mahalla_id == caller_mahalla_id)

        docs = (await db.execute(doc_query)).scalars().all()

        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            role_val = caller_role.value
            docs = [
                d for d in docs
                if d.assignment and role_val in (
                    d.assignment.assigned_roles or (d.assignment.category.assigned_roles if d.assignment.category else [])
                )
            ]

        jami_hujjatlar = len(docs)
        kiruvchi_hujjatlar = len([d for d in docs if d.status == CheckInDocStatus.PENDING])
        bajarilgan_hujjatlar = len([d for d in docs if d.status == CheckInDocStatus.APPROVED])
        rad_etilgan_hujjatlar = len([d for d in docs if d.status == CheckInDocStatus.REJECTED])

        # Muddati buzilib bajarilgan: approved check-ins completed after the deadline
        muddati_buzilib_bajarilgan = len([
            d for d in docs
            if d.status == CheckInDocStatus.APPROVED and (
                (d.due_date and d.check_in_date > d.due_date)
                or (d.due_date and d.reviewed_at and d.reviewed_at.date() > d.due_date)
            )
        ])

        # Kech qabul qilingan: documents submitted or accepted after deadline
        kech_qabul_qilingan = len([
            d for d in docs
            if (d.due_date and d.check_in_date > d.due_date)
            or (d.due_date and d.created_at and d.created_at.date() > d.due_date)
        ])

        # Muddati buzilgan hujjatlar: overdue active assignments / overdue pending check-ins
        pending_overdue_docs = len([
            d for d in docs
            if d.status == CheckInDocStatus.PENDING and d.due_date and d.due_date < today
        ])
        muddati_buzilgan_hujjatlar = max(overdue_count, pending_overdue_docs)

        # Today's task metrics
        bugun_bajarilgan = len([
            d for d in docs
            if d.status == CheckInDocStatus.APPROVED and (
                (d.reviewed_at and d.reviewed_at.date() == today)
                or (d.check_in_date == today)
            )
        ])
        bugun_bajarilmagan = today_count

        return RemainingDaysStatsSchema(
            jami_hujjatlar=jami_hujjatlar,
            kiruvchi_hujjatlar=kiruvchi_hujjatlar,
            bajarilgan_hujjatlar=bajarilgan_hujjatlar,
            rad_etilgan_hujjatlar=rad_etilgan_hujjatlar,
            muddati_buzilib_bajarilgan=muddati_buzilib_bajarilgan,
            kechikib_bajarilgan=muddati_buzilib_bajarilgan,
            kech_qabul_qilingan=kech_qabul_qilingan,
            muddati_buzilgan_hujjatlar=muddati_buzilgan_hujjatlar,
            total_documents=jami_hujjatlar,
            pending_documents=kiruvchi_hujjatlar,
            completed_documents=bajarilgan_hujjatlar,
            rejected_documents=rad_etilgan_hujjatlar,
            completed_overdue=muddati_buzilib_bajarilgan,
            late_accepted=kech_qabul_qilingan,
            overdue_documents=muddati_buzilgan_hujjatlar,
            overdue=overdue_count,
            today=today_count,
            bugun=today_count,
            ertaga=by_day.get(1, 0),
            indinga=by_day.get(2, 0),
            by_day=by_day,
            total_active=len(assignments),
            after_max_days=later_count,
            kelgusida=later_count,
            later=later_count,
            jami_vazifalar=len(assignments),
            total_tasks=len(assignments),
            bajarilgan_vazifalar=bajarilgan_hujjatlar,
            completed_tasks=bajarilgan_hujjatlar,
            bugun_bajarilgan=bugun_bajarilgan,
            completed_today=bugun_bajarilgan,
            bugun_bajarilmagan=bugun_bajarilmagan,
            pending_today=bugun_bajarilmagan,
        )

