import math
from datetime import date, timedelta
from typing import Optional, List, Sequence
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
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
    def _is_user_connected(
        assignment: PersonCategoryAssignment,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> bool:
        if caller_role is None:
            return False

        role_val = (
            caller_role.value
            if hasattr(caller_role, "value")
            else str(caller_role)
        )

        # Prokuror and Admin have universal authority over all assignments
        if role_val in [UserRole.ADMIN.value, UserRole.PROKUROR.value, "admin", "prokuror"]:
            return True

        # Mahalla-level users can only be connected within their own mahalla
        if caller_mahalla_id is not None and assignment.mahalla_id != caller_mahalla_id:
            return False

        # Mahalla raisi oversees all assignments in their own mahalla
        if role_val in [UserRole.MAHALLA_RAISI.value, "mahalla_raisi"]:
            return True

        # Mahalla specialized staff (6 roles): connected if their role is in assigned_roles
        assigned_roles = assignment.assigned_roles
        if not assigned_roles and assignment.category:
            assigned_roles = assignment.category.assigned_roles or []

        return bool(role_val and assigned_roles and role_val in assigned_roles)

    @classmethod
    def _format_assignment(
        cls,
        assignment: PersonCategoryAssignment,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> AssignmentResponseSchema:
        today = date.today()
        is_overdue = False
        days_remaining = None
        if assignment.next_check_in_due:
            is_overdue = (
                assignment.status == AssignmentStatus.ACTIVE
                and assignment.next_check_in_due < today
            )
            days_remaining = (assignment.next_check_in_due - today).days

        assigned_roles = assignment.assigned_roles
        if not assigned_roles and assignment.category:
            assigned_roles = assignment.category.assigned_roles or []

        is_connected = cls._is_user_connected(
            assignment,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

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
            am_i_connected=is_connected,
            ami_i_conntected=is_connected,
            ami_i_connected=is_connected,
            created_at=assignment.created_at,
        )

    @classmethod
    def _format_person(
        cls,
        person: Person,
        assignments: Optional[Sequence[PersonCategoryAssignment]] = None,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> PersonResponseSchema:
        ass_list = (
            assignments if assignments is not None else (person.assignments or [])
        )
        assignments_formatted = [
            cls._format_assignment(
                a,
                caller_role=caller_role,
                caller_mahalla_id=caller_mahalla_id,
            )
            for a in ass_list
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
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
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

        if data.frequency_days is not None:
            next_due = date.today() + timedelta(days=data.frequency_days)
        else:
            next_due = None

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
        return cls._format_assignment(
            assignment,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

    @classmethod
    async def update_assignment(
        cls,
        assignment_id: int,
        data: AssignmentUpdateSchema,
        editor_id: int,
        db: AsyncSession,
        person_id: Optional[int] = None,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
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
        return cls._format_assignment(
            assignment,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

    @classmethod
    async def update_person_category_assignment(
        cls,
        person_id: int,
        data: AssignmentUpdateSchema,
        editor_id: int,
        db: AsyncSession,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
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
        return cls._format_assignment(
            assignment,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

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

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(Person.mahalla_id == mahalla_id)
                count_query = count_query.where(Person.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            query = query.where(Person.mahalla_id == caller_mahalla_id)
            count_query = count_query.where(Person.mahalla_id == caller_mahalla_id)
        elif caller_role in MAHALLA_SEVEN_ROLES:
            query = query.where(Person.mahalla_id == caller_mahalla_id)
            count_query = count_query.where(Person.mahalla_id == caller_mahalla_id)

        if search:
            pattern = f"%{search}%"
            query = query.where(Person.full_name.ilike(pattern))
            count_query = count_query.where(Person.full_name.ilike(pattern))

        if category_id:
            query = query.join(Person.assignments).where(
                PersonCategoryAssignment.category_id == category_id
            )
            count_query = count_query.join(Person.assignments).where(
                PersonCategoryAssignment.category_id == category_id
            )

        actual_remaining_days = (
            remaining_days if remaining_days is not None else days_remaining
        )
        if actual_remaining_days is not None:
            today = date.today()
            target_due = today + timedelta(days=actual_remaining_days)
            if not category_id:
                query = query.join(Person.assignments)
                count_query = count_query.join(Person.assignments)
            
            if actual_remaining_days < 0:
                query = query.where(
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    PersonCategoryAssignment.next_check_in_due < today,
                )
                count_query = count_query.where(
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    PersonCategoryAssignment.next_check_in_due < today,
                )
            else:
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
            for a in all_assignments:
                assignments_map[a.person_id].append(a)

        items = [
            cls._format_person(
                p,
                assignments=assignments_map.get(p.id, []),
                caller_role=caller_role,
                caller_mahalla_id=caller_mahalla_id,
            )
            for p in persons
        ]

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
        query = (
            select(Person)
            .where(Person.id == person_id)
            .options(selectinload(Person.mahalla))
        )
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

        return cls._format_person(
            person,
            assignments=assignments,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

    @classmethod
    async def update_person(
        cls,
        person_id: int,
        data: PersonUpdateSchema,
        db: AsyncSession,
        caller_role: Optional[UserRole | str] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> PersonResponseSchema:
        person = (
            await db.execute(
                select(Person)
                .where(Person.id == person_id)
                .options(selectinload(Person.mahalla))
            )
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
            mahalla = await db.scalar(
                select(Mahalla).where(Mahalla.id == data.mahalla_id)
            )
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
        return cls._format_person(
            person,
            assignments=assignments,
            caller_role=caller_role,
            caller_mahalla_id=caller_mahalla_id,
        )

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
            query = query.where(
                PersonCategoryAssignment.mahalla_id == caller_mahalla_id
            )
        elif caller_role in MAHALLA_SEVEN_ROLES:
            query = query.where(
                PersonCategoryAssignment.mahalla_id == caller_mahalla_id
            )

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
            if days_remaining < 0:
                query = query.where(
                    PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
                    PersonCategoryAssignment.next_check_in_due < today,
                )
            else:
                target_due = today + timedelta(days=days_remaining)
                query = query.where(
                    PersonCategoryAssignment.next_check_in_due == target_due
                )

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
                roles = a.assigned_roles or (
                    a.category.assigned_roles if a.category else []
                )
                if role_val in roles:
                    filtered.append(a)
            assignments = filtered

        return [
            cls._format_assignment(
                a,
                caller_role=caller_role,
                caller_mahalla_id=caller_mahalla_id,
            )
            for a in assignments
        ]

    @classmethod
    async def get_remaining_days_stats(
        cls,
        max_days: int,
        mahalla_id: Optional[int],
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> RemainingDaysStatsSchema:
        query = (
            select(PersonCategoryAssignment)
            .options(selectinload(PersonCategoryAssignment.category))
            .where(PersonCategoryAssignment.status == AssignmentStatus.ACTIVE)
        )

        # RBAC Filtering
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            if mahalla_id is not None:
                query = query.where(PersonCategoryAssignment.mahalla_id == mahalla_id)
        elif caller_role == UserRole.MAHALLA_RAISI:
            query = query.where(
                PersonCategoryAssignment.mahalla_id == caller_mahalla_id
            )
        elif caller_role in MAHALLA_SEVEN_ROLES:
            query = query.where(
                PersonCategoryAssignment.mahalla_id == caller_mahalla_id
            )

        assignments = (await db.execute(query)).scalars().all()

        # If Mahalla 7 worker, filter by role
        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            role_val = caller_role.value
            assignments = [
                a
                for a in assignments
                if role_val
                in (
                    a.assigned_roles
                    or (a.category.assigned_roles if a.category else [])
                )
            ]

        today = date.today()
        overdue_count = 0
        today_count = 0
        by_day = {d: 0 for d in range(0, max_days + 1)}
        later_count = 0

        for a in assignments:
            if not a.next_check_in_due:
                continue
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
            selectinload(CheckInDocument.assignment).selectinload(
                PersonCategoryAssignment.category
            )
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
                d
                for d in docs
                if d.assignment
                and role_val
                in (
                    d.assignment.assigned_roles
                    or (
                        d.assignment.category.assigned_roles
                        if d.assignment.category
                        else []
                    )
                )
            ]

        jami_hujjatlar = len(docs)
        kiruvchi_hujjatlar = len(
            [d for d in docs if d.status == CheckInDocStatus.PENDING]
        )
        bajarilgan_hujjatlar = len(
            [d for d in docs if d.status == CheckInDocStatus.APPROVED]
        )
        rad_etilgan_hujjatlar = len(
            [d for d in docs if d.status == CheckInDocStatus.REJECTED]
        )

        # Muddati buzilib bajarilgan: approved check-ins completed after the deadline
        muddati_buzilib_bajarilgan = len(
            [
                d
                for d in docs
                if d.status == CheckInDocStatus.APPROVED
                and (
                    (d.due_date and d.check_in_date > d.due_date)
                    or (
                        d.due_date
                        and d.reviewed_at
                        and d.reviewed_at.date() > d.due_date
                    )
                )
            ]
        )

        # Kech qabul qilingan: documents submitted or accepted after deadline
        kech_qabul_qilingan = len(
            [
                d
                for d in docs
                if (d.due_date and d.check_in_date > d.due_date)
                or (d.due_date and d.created_at and d.created_at.date() > d.due_date)
            ]
        )

        # Documents whose deadline has passed (Overdue pending check-ins)
        pending_overdue_docs = len(
            [
                d
                for d in docs
                if d.status == CheckInDocStatus.PENDING
                and d.due_date
                and d.due_date < today
            ]
        )
        hujjatlar_muddati_buzilgan = pending_overdue_docs
        odamlar_muddati_buzilgan = overdue_count

        # Today's task metrics
        bugun_bajarilgan = len(
            [
                d
                for d in docs
                if d.status == CheckInDocStatus.APPROVED
                and (
                    (d.reviewed_at and d.reviewed_at.date() == today)
                    or (d.check_in_date == today)
                )
            ]
        )
        bugun_bajarilmagan = today_count

        # Pending documents breakdown by remaining days (0 to max_days)
        docs_by_day = {d: 0 for d in range(0, max_days + 1)}
        for d in docs:
            if d.status == CheckInDocStatus.PENDING:
                eff_due = d.due_date or (d.assignment.next_check_in_due if d.assignment else None)
                if eff_due:
                    d_diff = (eff_due - today).days
                    if 0 <= d_diff <= max_days:
                        docs_by_day[d_diff] += 1

        return RemainingDaysStatsSchema(
            jami_hujjatlar=jami_hujjatlar,
            kiruvchi_hujjatlar=kiruvchi_hujjatlar,
            bajarilgan_hujjatlar=bajarilgan_hujjatlar,
            rad_etilgan_hujjatlar=rad_etilgan_hujjatlar,
            muddati_buzilib_bajarilgan=muddati_buzilib_bajarilgan,
            kechikib_bajarilgan=muddati_buzilib_bajarilgan,
            kech_qabul_qilingan=kech_qabul_qilingan,
            muddati_buzilgan_hujjatlar=hujjatlar_muddati_buzilgan,
            hujjatlar_muddati_buzilgan=hujjatlar_muddati_buzilgan,
            documents_muddati_buzilgan=hujjatlar_muddati_buzilgan,
            odamlar_muddati_buzilgan=odamlar_muddati_buzilgan,
            muddati_buzilgan_odamlar=odamlar_muddati_buzilgan,
            muddati_buzilgan_shaxslar=odamlar_muddati_buzilgan,
            muddati_buzilgan=odamlar_muddati_buzilgan,
            total_documents=jami_hujjatlar,
            pending_documents=kiruvchi_hujjatlar,
            completed_documents=bajarilgan_hujjatlar,
            rejected_documents=rad_etilgan_hujjatlar,
            completed_overdue=muddati_buzilib_bajarilgan,
            late_accepted=kech_qabul_qilingan,
            overdue_documents=hujjatlar_muddati_buzilgan,
            overdue_persons=odamlar_muddati_buzilgan,
            overdue=overdue_count,
            today=today_count,
            bugun=today_count,
            ertaga=by_day.get(1, 0),
            indinga=by_day.get(2, 0),
            by_day=by_day,
            docs_by_day=docs_by_day,
            pending_docs_by_day=docs_by_day,
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
