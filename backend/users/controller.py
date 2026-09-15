from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.service import (
    prokuror_or_admin_guard,
    all_guard,
    UserAuth,
)
from backend.users.schemas.create import UserCreateSchema
from backend.users.schemas.patch import UserUpdateSchema
from backend.users.schemas.get import UserResponseSchema, PaginatedUserSchema
from backend.users.service import UserService
from db.connection import get_async_db
from db.models.user import UserRole

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user/official (Admin or Prokuror)",
)
async def create_user(
    data: UserCreateSchema,
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await UserService.create_user(
        data=data,
        caller_role=current_user["role"],
        db=db,
    )


@router.get(
    "",
    response_model=PaginatedUserSchema,
    summary="Get paginated list of users with separated search filters",
)
async def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    name: Optional[str] = Query(None, description="Search by first or last name"),
    phone: Optional[str] = Query(None, description="Search by phone number"),
    login: Optional[str] = Query(None, description="Search by username/login"),
    role: Optional[UserRole] = Query(None, description="Filter by user role"),
    mahalla_id: Optional[int] = Query(None, description="Filter by assigned mahalla"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await UserService.get_users(
        db=db,
        page=page,
        page_size=page_size,
        name=name,
        phone=phone,
        login=login,
        role=role,
        mahalla_id=mahalla_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
    )


@router.get(
    "/{user_id}",
    response_model=UserResponseSchema,
    summary="Get user details by ID",
)
async def get_user_by_id(
    user_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await UserService.get_user_by_id(
        user_id=user_id,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponseSchema,
    summary="Update user details or de-activate (Admin, Prokuror)",
)
async def update_user(
    user_id: int,
    data: UserUpdateSchema,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await UserService.update_user(
        user_id=user_id,
        data=data,
        caller_id=current_user["id"],
        caller_role=current_user["role"],
        db=db,
    )
