from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.auth.schemas.login import LoginSchema
from backend.auth.schemas.register import RegisterSchema
from backend.auth.schemas.token import TokenRes, RefreshRequest, RefreshResponse, MeResponseSchema
from backend.auth.service import AuthServices, UserAuth, all_guard, admin_guard
from db.connection import get_async_db
from db.models.user import User

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post(
    "/register",
    response_model=TokenRes,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user (Admin only)",
    dependencies=[Depends(admin_guard)],
)
async def register_user(
    data: RegisterSchema,
    db: AsyncSession = Depends(get_async_db),
):
    return await AuthServices.register(data, db)


@router.post(
    "/login",
    response_model=TokenRes,
    status_code=status.HTTP_200_OK,
    summary="Login with username/phone and password",
)
async def login_user(
    data: LoginSchema,
    db: AsyncSession = Depends(get_async_db),
):
    return await AuthServices.login(data.login, data.password, db)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_async_db),
):
    new_access_token = await AuthServices.refresh(data.refresh_token, db)
    return RefreshResponse(access_token=new_access_token)


@router.get(
    "/me",
    response_model=MeResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user info",
)
async def get_me(
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(select(User).where(User.id == current_user["id"]))
    user = result.scalar_one_or_none()
    return MeResponseSchema(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        login=user.login,
        role=user.role,
        mahalla_id=user.mahalla_id,
        photo_url=user.photo_url,
        birth_date_text=user.birth_date_text,
        appointed_date_text=user.appointed_date_text,
        specialization=user.specialization,
        previous_workplace=user.previous_workplace,
        is_active=user.is_active,
    )
