from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.service import (
    all_guard,
    prokuror_or_admin_guard,
    UserAuth,
)
from backend.persons.schemas import (
    PersonCreateSchema,
    PersonUpdateSchema,
    AssignmentCreateSchema,
    AssignmentResponseSchema,
    RemainingDaysStatsSchema,
    PersonResponseSchema,
    PaginatedPersonSchema,
)
from backend.persons.service import PersonService
from db.connection import get_async_db
from db.models.assignment import AssignmentStatus

router = APIRouter(prefix="/persons", tags=["Persons & Assignments"])


@router.post(
    "",
    response_model=PersonResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new person (Prokuror or Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def create_person(
    data: PersonCreateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.create_person(data=data, db=db)


@router.get(
    "",
    response_model=PaginatedPersonSchema,
    summary="Get paginated list of persons (Role-filtered)",
)
async def get_persons(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by F.I.SH"),
    mahalla_id: Optional[int] = Query(None, description="Filter by Mahalla ID (Admin/Prokuror only)"),
    category_id: Optional[int] = Query(None, description="Filter by Category ID"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.get_persons(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        mahalla_id=mahalla_id,
        category_id=category_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
    )


@router.get(
    "/assignments/stats/remaining-days",
    response_model=RemainingDaysStatsSchema,
    summary="Get count of check-ins broken down by remaining days (overdue, today, day-by-day 1 to N)",
)
async def get_remaining_days_stats(
    max_days: int = Query(5, ge=1, le=365, description="Number of future days to count day-by-day (e.g. 5, 7, 10, 30)"),
    mahalla_id: Optional[int] = Query(None, description="Filter by Mahalla (Admin/Prokuror only)"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.get_remaining_days_stats(
        max_days=max_days,
        mahalla_id=mahalla_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.get(
    "/assignments",
    response_model=List[AssignmentResponseSchema],
    summary="Get category assignments with due dates and flexible remaining days filters",
)
async def get_assignments(
    mahalla_id: Optional[int] = Query(None, description="Filter by Mahalla"),
    category_id: Optional[int] = Query(None, description="Filter by Category"),
    status_filter: Optional[AssignmentStatus] = Query(None, description="Filter by status"),
    overdue_only: bool = Query(False, description="Filter only overdue assignments"),
    days_remaining: Optional[int] = Query(None, description="Filter by exact remaining days (e.g. 5 for 5 days left, 4 for 4 days left, 0 for today, -1 for overdue)"),
    min_days_remaining: Optional[int] = Query(None, description="Filter by minimum remaining days"),
    max_days_remaining: Optional[int] = Query(None, description="Filter by maximum remaining days"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.get_assignments(
        db=db,
        mahalla_id=mahalla_id,
        category_id=category_id,
        status_filter=status_filter,
        overdue_only=overdue_only,
        days_remaining=days_remaining,
        min_days_remaining=min_days_remaining,
        max_days_remaining=max_days_remaining,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
    )


@router.get(
    "/{person_id}",
    response_model=PersonResponseSchema,
    summary="Get person details and active category assignments",
)
async def get_person_by_id(
    person_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.get_person_by_id(
        person_id=person_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.patch(
    "/{person_id}",
    response_model=PersonResponseSchema,
    summary="Update person details (Prokuror or Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def update_person(
    person_id: int,
    data: PersonUpdateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.update_person(
        person_id=person_id,
        data=data,
        db=db,
    )


@router.post(
    "/{person_id}/assign-category",
    response_model=AssignmentResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a person to a category with mandatory check-in frequency (Prokuror or Admin only)",
)
async def assign_category(
    person_id: int,
    data: AssignmentCreateSchema,
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await PersonService.assign_category(
        person_id=person_id,
        data=data,
        created_by_id=current_user["id"],
        db=db,
    )

