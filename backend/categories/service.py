import math
from datetime import date
from typing import Optional, List
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.categories.schemas import (
    CategoryCreateSchema,
    CategoryUpdateSchema,
    CategoryResponseSchema,
    CategoryStatsSchema,
    PaginatedCategorySchema,
)
from backend.files.service import FileService
from db.models.category import Category
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.user import UserRole, MAHALLA_SEVEN_ROLES


class CategoryService:
    @classmethod
    async def create_category(
        cls, data: CategoryCreateSchema, db: AsyncSession
    ) -> Category:
        existing = await db.execute(
            select(Category.id).where(Category.name == data.name)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category with name '{data.name}' already exists",
            )

        roles_list = [r.value if hasattr(r, "value") else str(r) for r in data.assigned_roles]
        new_category = Category(
            name=data.name,
            description=data.description,
            assigned_roles=roles_list,
            default_frequency_days=data.default_frequency_days,
            is_active=True,
        )
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return new_category

    @classmethod
    async def get_categories(
        cls,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> PaginatedCategorySchema:
        query = select(Category)
        count_query = select(func.count(Category.id))

        if is_active is not None:
            query = query.where(Category.is_active == is_active)
            count_query = count_query.where(Category.is_active == is_active)

        if search:
            search_pattern = f"%{search}%"
            query = query.where(Category.name.ilike(search_pattern))
            count_query = count_query.where(Category.name.ilike(search_pattern))

        total = (await db.execute(count_query)).scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(Category.id.asc()).offset(offset).limit(page_size)

        result = await db.execute(query)
        categories = result.scalars().all()

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        items = [
            CategoryResponseSchema(
                id=c.id,
                name=c.name,
                icon_url=c.icon_url,
                description=c.description,
                assigned_roles=c.assigned_roles or [],
                default_frequency_days=c.default_frequency_days,
                is_active=c.is_active,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in categories
        ]

        return PaginatedCategorySchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    async def get_category_by_id(cls, category_id: int, db: AsyncSession) -> Category:
        result = await db.execute(select(Category).where(Category.id == category_id))
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        return category

    @classmethod
    async def update_category(
        cls, category_id: int, data: CategoryUpdateSchema, db: AsyncSession
    ) -> Category:
        category = await cls.get_category_by_id(category_id, db)

        if data.name is not None and data.name != category.name:
            existing = await db.execute(
                select(Category.id).where(
                    Category.name == data.name, Category.id != category_id
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Category with name '{data.name}' already exists",
                )
            category.name = data.name

        if data.description is not None:
            category.description = data.description

        if data.assigned_roles is not None:
            category.assigned_roles = [
                r.value if hasattr(r, "value") else str(r) for r in data.assigned_roles
            ]

        if data.default_frequency_days is not None:
            category.default_frequency_days = data.default_frequency_days

        if data.is_active is not None:
            category.is_active = data.is_active

        await db.commit()
        await db.refresh(category)
        return category

    @classmethod
    async def upload_icon(
        cls, category_id: int, file: UploadFile, db: AsyncSession
    ) -> Category:
        category = await cls.get_category_by_id(category_id, db)
        old_icon_url = category.icon_url
        icon_url = await FileService.save_uploaded_icon(file)
        category.icon_url = icon_url
        await db.commit()
        await db.refresh(category)

        if old_icon_url and old_icon_url != icon_url:
            FileService.delete_file_by_url_or_path(old_icon_url)

        return category

    @classmethod
    async def delete_category(
        cls, category_id: int, db: AsyncSession
    ) -> bool:
        category = await cls.get_category_by_id(category_id, db)
        await db.delete(category)
        await db.commit()
        return True

    @classmethod
    async def get_category_stats(
        cls,
        mahalla_id: Optional[int],
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> List[CategoryStatsSchema]:
        target_mahalla_id = mahalla_id
        if caller_role in [UserRole.MAHALLA_RAISI, *MAHALLA_SEVEN_ROLES]:
            target_mahalla_id = caller_mahalla_id

        categories = (
            await db.scalars(
                select(Category).where(Category.is_active == True).order_by(Category.id.asc())
            )
        ).all()

        today = date.today()
        stats_list = []

        for cat in categories:
            # Query active assignments for this category
            query = select(PersonCategoryAssignment).where(
                PersonCategoryAssignment.category_id == cat.id
            )
            if target_mahalla_id is not None:
                query = query.where(PersonCategoryAssignment.mahalla_id == target_mahalla_id)

            assignments = (await db.scalars(query)).all()

            distinct_persons = len({a.person_id for a in assignments})
            active_count = len([a for a in assignments if a.status == AssignmentStatus.ACTIVE])
            overdue_count = len(
                [
                    a
                    for a in assignments
                    if a.status == AssignmentStatus.ACTIVE and a.next_check_in_due < today
                ]
            )

            stats_list.append(
                CategoryStatsSchema(
                    id=cat.id,
                    name=cat.name,
                    icon_url=cat.icon_url,
                    description=cat.description,
                    assigned_roles=cat.assigned_roles or [],
                    default_frequency_days=cat.default_frequency_days,
                    persons_count=distinct_persons,
                    active_assignments_count=active_count,
                    overdue_assignments_count=overdue_count,
                )
            )

        return stats_list
