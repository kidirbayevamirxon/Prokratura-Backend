from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.schemas.token import TokenRes
from backend.auth.service import UserAuth, admin_guard, all_guard, prokuror_or_admin_guard
from backend.devices.schemas.get import (
    DeviceResponseSchema,
    DeviceStatusResponseSchema,
    MessageResponseSchema,
)
from backend.devices.schemas.patch import DeviceUpdateSchema
from backend.devices.schemas.post import (
    LoginOptionsRequestSchema,
    LoginVerifyRequestSchema,
    RegisterVerifyRequestSchema,
)
from backend.devices.service import DeviceService
from db.connection import get_async_db

router = APIRouter(
    prefix="/devices",
    tags=["Devices"],
)


@router.post(
    "/register-options",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Generate WebAuthn registration options for current user",
)
async def register_options(
    request: Request,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    return await DeviceService.generate_registration_options(
        user_id=current_user["id"],
        db=db,
        request=request,
    )


@router.post(
    "/register-verify",
    response_model=DeviceResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Verify registration response and bind hardware device",
)
async def register_verify(
    data: RegisterVerifyRequestSchema,
    request: Request,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
) -> DeviceResponseSchema:
    return await DeviceService.verify_registration(
        user_id=current_user["id"],
        data=data,
        db=db,
        request=request,
    )


@router.post(
    "/login-options",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Generate WebAuthn authentication options for user login",
)
async def login_options(
    data: LoginOptionsRequestSchema,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    return await DeviceService.generate_login_options(
        data=data,
        db=db,
        request=request,
    )


@router.post(
    "/login-verify",
    response_model=TokenRes,
    status_code=status.HTTP_200_OK,
    summary="Verify WebAuthn assertion and issue JWT tokens",
)
async def login_verify(
    data: LoginVerifyRequestSchema,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> TokenRes:
    return await DeviceService.verify_login(
        data=data,
        db=db,
        request=request,
    )


@router.get(
    "/status",
    response_model=DeviceStatusResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Get bound hardware device information for current user",
)
async def get_device_status(
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
) -> DeviceStatusResponseSchema:
    return await DeviceService.get_device_status(
        user_id=current_user["id"],
        db=db,
    )


@router.delete(
    "/unbind",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Unbind and remove current user's hardware device (Prokuror and Admin only)",
    dependencies=[Depends(prokuror_or_admin_guard)],
)
async def unbind_device(
    current_user: UserAuth = Depends(prokuror_or_admin_guard),
    db: AsyncSession = Depends(get_async_db),
) -> MessageResponseSchema:
    return await DeviceService.unbind_device(
        user_id=current_user["id"],
        db=db,
    )


@router.post(
    "/admin/reset/{user_id}",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Admin reset/unbind registered device for target user",
    dependencies=[Depends(admin_guard)],
)
async def admin_reset_device(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
) -> MessageResponseSchema:
    return await DeviceService.admin_reset_device(
        target_user_id=user_id,
        db=db,
    )


@router.patch(
    "/rename",
    response_model=DeviceResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Update device name for current user",
)
async def update_device_name(
    data: DeviceUpdateSchema,
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
) -> DeviceResponseSchema:
    return await DeviceService.update_device_name(
        user_id=current_user["id"],
        data=data,
        db=db,
    )
