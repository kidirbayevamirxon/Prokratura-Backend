from typing import Optional, List
from fastapi import APIRouter, Depends, Query, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.service import (
    all_guard,
    prokuror_or_admin_guard,
    UserAuth,
)
from backend.categories.schemas import (
    CategoryCreateSchema,
    CategoryUpdateSchema,
    CategoryResponseSchema,
    CategoryStatsSchema,
    PaginatedCategorySchema,
)
from backend.categories.service import CategoryService
from db.connection import get_async_db

router = APIRouter(prefix="/categories", tags=["Categories (Docs Types)"])


@router.post(
    "",
    response_model=CategoryResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Special Category / Docs Type (Prokuror or Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def create_category(
    data: CategoryCreateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    category = await CategoryService.create_category(data, db)
    return CategoryResponseSchema(
        id=category.id,
        name=category.name,
        icon_url=category.icon_url,
        description=category.description,
        assigned_roles=category.assigned_roles or [],
        default_frequency_days=category.default_frequency_days,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.get(
    "",
    response_model=PaginatedCategorySchema,
    summary="Get paginated list of categories",
    dependencies=[Depends(all_guard)],
)
async def get_categories(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search by category name"),
    is_active: Optional[bool] = Query(None, description="Filter active/inactive"),
    db: AsyncSession = Depends(get_async_db),
):
    return await CategoryService.get_categories(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
    )


@router.get(
    "/stats",
    response_model=List[CategoryStatsSchema],
    summary="Get live stats and citizen counts for all categories (Role-filtered)",
)
async def get_category_stats(
    mahalla_id: Optional[int] = Query(None, description="Filter by Mahalla (Admin/Prokuror only)"),
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    return await CategoryService.get_category_stats(
        mahalla_id=mahalla_id,
        caller_role=current_user["role"],
        caller_mahalla_id=current_user["mahalla_id"],
        db=db,
    )


@router.get(
    "/{category_id}",
    response_model=CategoryResponseSchema,
    summary="Get category details by ID",
    dependencies=[Depends(all_guard)],
)
async def get_category_by_id(
    category_id: int,
    db: AsyncSession = Depends(get_async_db),
):
    category = await CategoryService.get_category_by_id(category_id, db)
    return CategoryResponseSchema(
        id=category.id,
        name=category.name,
        icon_url=category.icon_url,
        description=category.description,
        assigned_roles=category.assigned_roles or [],
        default_frequency_days=category.default_frequency_days,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.post(
    "/{category_id}/icon",
    response_model=CategoryResponseSchema,
    summary="Upload icon / image for category (Prokuror or Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def upload_category_icon(
    category_id: int,
    icon: UploadFile = File(..., description="Category icon/image (max 2 MB)"),
    db: AsyncSession = Depends(get_async_db),
):
    category = await CategoryService.upload_icon(category_id, icon, db)
    return CategoryResponseSchema(
        id=category.id,
        name=category.name,
        icon_url=category.icon_url,
        description=category.description,
        assigned_roles=category.assigned_roles or [],
        default_frequency_days=category.default_frequency_days,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


@router.patch(
    "/{category_id}",
    response_model=CategoryResponseSchema,
    summary="Update category details or assigned roles (Prokuror or Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def update_category(
    category_id: int,
    data: CategoryUpdateSchema,
    db: AsyncSession = Depends(get_async_db),
):
    category = await CategoryService.update_category(category_id, data, db)
    return CategoryResponseSchema(
        id=category.id,
        name=category.name,
        icon_url=category.icon_url,
        description=category.description,
        assigned_roles=category.assigned_roles or [],
        default_frequency_days=category.default_frequency_days,
        is_active=category.is_active,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )
