from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.service import admin_guard, rais_guard, all_guard, UserAuth
from backend.mahallas.schemas.create import MahallaCreateSchema
from backend.mahallas.schemas.patch import MahallaUpdateSchema
from backend.mahallas.schemas.get import (
    MahallaDetailSchema,
    PaginatedMahallaSchema,
)
from backend.users.schemas.get import UserResponseSchema
from backend.mahallas.schemas.stats import (
    MahallaStatsCreateOrUpdateSchema,
    MahallaStatsResponseSchema,
)
from backend.mahallas.schemas.radar import SituationalRadarResponse
from backend.mahallas.service import MahallaService
from db.connection import get_async_db
from db.models.user import UserRole

router = APIRouter(prefix="/mahallas", tags=["Mahallas"])


@router.post(
    "",
    response_model=MahallaDetailSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Mahalla (Admin only)",
    dependencies=[Depends(admin_guard)],
)
async def create_mahalla(
    data: MahallaCreateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    mahalla = await MahallaService.create_mahalla(data, db)
    return await MahallaService.get_mahalla_by_id(mahalla.id, db)


@router.get(
    "",
    response_model=PaginatedMahallaSchema,
    summary="Get paginated list of mahallas (Admin, Prokuror, Rais)",
)
async def get_mahallas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by name"),
    current_user: UserAuth = Depends(rais_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.get_mahallas(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
    )


@router.get(
    "/situational-radar",
    response_model=SituationalRadarResponse,
    summary="Get real-time situational radar & risk heatmap data for all mahallas (Admin, Prokuror, Rais)",
)
async def get_situational_radar(
    current_user: UserAuth = Depends(rais_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.get_situational_radar(
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.get(
    "/{mahalla_id}",
    response_model=MahallaDetailSchema,
    summary="Get Mahalla details and its members (Admin, Prokuror, or own Rais)",
)
async def get_mahalla(
    mahalla_id: int,
    current_user: UserAuth = Depends(rais_guard),
    db: AsyncSession = Depends(get_async_db),
):
    # Rais can only see their own mahalla
    if (
        current_user["role"] == UserRole.MAHALLA_RAISI
        and current_user["mahalla_id"] != mahalla_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rais can only view details of their own Mahalla",
        )

    return await MahallaService.get_mahalla_by_id(mahalla_id, db)


@router.get(
    "/{mahalla_id}/members",
    response_model=List[UserResponseSchema],
    summary="Get members/officials of a Mahalla (Admin, Prokuror, or own Rais)",
)
async def get_mahalla_members(
    mahalla_id: int,
    role: Optional[UserRole] = Query(None, description="Filter members by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    current_user: UserAuth = Depends(rais_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.get_mahalla_members(
        mahalla_id=mahalla_id,
        role=role,
        is_active=is_active,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.patch(
    "/{mahalla_id}",
    response_model=MahallaDetailSchema,
    summary="Update Mahalla (Admin only)",
    dependencies=[Depends(admin_guard)],
)
async def update_mahalla(
    mahalla_id: int,
    data: MahallaUpdateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.update_mahalla(mahalla_id, data, db)


@router.get(
    "/{mahalla_id}/stats",
    response_model=MahallaStatsResponseSchema,
    summary="Get infrastructure, demographic, and characteristics stats for a Mahalla",
)
async def get_mahalla_stats(
    mahalla_id: int,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.get_mahalla_stats(
        mahalla_id=mahalla_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.put(
    "/{mahalla_id}/stats",
    response_model=MahallaStatsResponseSchema,
    summary="Update or create infrastructure, demographic, and characteristics stats (Admin, Prokuror, or own Rais)",
)
async def update_mahalla_stats(
    mahalla_id: int,
    data: MahallaStatsCreateOrUpdateSchema,
    current_user: UserAuth = Depends(rais_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await MahallaService.update_mahalla_stats(
        mahalla_id=mahalla_id,
        data=data,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )
