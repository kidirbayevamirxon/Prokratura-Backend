from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.mahallas.schemas.create import MahallaCreateSchema
from backend.mahallas.schemas.patch import MahallaUpdateSchema
from backend.mahallas.schemas.get import PaginatedMahallaSchema, MahallaDetailSchema
from db.models.mahalla import Mahalla
from db.models.user import UserRole


class MahallaService:
    @staticmethod
    async def create_mahalla(data: MahallaCreateSchema, db: AsyncSession) -> Mahalla:
        existing = await db.execute(
            select(Mahalla).where(Mahalla.name == data.name.strip())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mahalla with name '{data.name.strip()}' already exists",
            )

        new_mahalla = Mahalla(name=data.name.strip())
        db.add(new_mahalla)
        await db.commit()
        await db.refresh(new_mahalla)
        return new_mahalla

    @staticmethod
    async def get_mahallas(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        caller_role: Optional[UserRole] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> PaginatedMahallaSchema:
        query = select(Mahalla).options(selectinload(Mahalla.members))
        count_query = select(func.count(Mahalla.id))

        # If Rais, only show their own mahalla
        if caller_role == UserRole.MAHALLA_RAISI:
            if caller_mahalla_id is None:
                return PaginatedMahallaSchema(items=[], total=0, page=page, page_size=page_size)
            query = query.where(Mahalla.id == caller_mahalla_id)
            count_query = count_query.where(Mahalla.id == caller_mahalla_id)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(Mahalla.name.ilike(search_pattern))
            count_query = count_query.where(Mahalla.name.ilike(search_pattern))

        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(Mahalla.id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        mahallas = result.scalars().all()

        return PaginatedMahallaSchema(
            items=[MahallaDetailSchema.model_validate(m) for m in mahallas],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_mahalla_by_id(mahalla_id: int, db: AsyncSession) -> Mahalla:
        query = (
            select(Mahalla)
            .options(selectinload(Mahalla.members))
            .where(Mahalla.id == mahalla_id)
        )
        result = await db.execute(query)
        mahalla = result.scalar_one_or_none()
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {mahalla_id} not found",
            )
        return mahalla

    @staticmethod
    async def update_mahalla(
        mahalla_id: int, data: MahallaUpdateSchema, db: AsyncSession
    ) -> Mahalla:
        mahalla = await MahallaService.get_mahalla_by_id(mahalla_id, db)

        if data.name is not None:
            new_name = data.name.strip()
            existing = await db.execute(
                select(Mahalla).where(Mahalla.name == new_name, Mahalla.id != mahalla_id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mahalla with name '{new_name}' already exists",
                )
            mahalla.name = new_name

        if data.is_active is not None:
            mahalla.is_active = data.is_active

        await db.commit()
        await db.refresh(mahalla)
        return mahalla
