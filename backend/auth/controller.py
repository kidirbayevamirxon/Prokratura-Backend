from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.auth.schemas.login import LoginSchema
from backend.auth.schemas.register import RegisterSchema
from backend.auth.schemas.token import TokenRes, RefreshRequest, RefreshResponse, MeResponseSchema
from backend.auth.schemas.device import (
    DeviceRegisterChallengeResponse,
    DeviceRegisterVerifyRequest,
    DeviceLoginChallengeRequest,
    DeviceLoginChallengeResponse,
    DeviceLoginVerifyRequest,
)
from backend.auth.webauthn_utils import verify_challenge_token
from backend.auth.service import AuthServices, UserAuth, all_guard, admin_guard, optional_guard
from db.connection import get_async_db
from db.models.user import User, UserRole
from db.models.user_device import UserDevice

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


# ==============================================================================
# Hardware Chip Device Authentication (WebAuthn / FIDO2)
# ==============================================================================

@router.post(
    "/device/register/challenge",
    response_model=DeviceRegisterChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get WebAuthn creation options to register hardware device (Authenticated or Transfer Token)",
)
async def device_register_challenge(
    request: Request,
    transfer_token: Optional[str] = Query(None, description="Optional transfer token for registering new PC"),
    current_user: Optional[UserAuth] = Depends(optional_guard),
    db: AsyncSession = Depends(get_async_db),
):
    user_id: Optional[int] = None
    is_transfer = False
    caller_role: Optional[UserRole] = None

    if current_user:
        user_id = current_user["id"]
        caller_role = UserRole(current_user["role"])
    elif transfer_token:
        try:
            token_payload = verify_challenge_token(transfer_token, expected_type="register")
            user_id = int(token_payload["sub"])
            is_transfer = True
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Provide Bearer token or valid transfer_token",
        )

    return await AuthServices.generate_device_register_challenge(
        user_id=user_id,
        db=db,
        caller_role=caller_role,
        is_transfer=is_transfer,
        request=request,
    )


@router.post(
    "/device/register/verify",
    response_model=TokenRes,
    status_code=status.HTTP_201_CREATED,
    summary="Verify hardware attestation and bind PC hardware key to user",
)
async def device_register_verify(
    data: DeviceRegisterVerifyRequest,
    request: Request,
    current_user: Optional[UserAuth] = Depends(optional_guard),
    db: AsyncSession = Depends(get_async_db),
):
    # Challenge token contains user_id
    try:
        token_payload = verify_challenge_token(data.challenge_token, expected_type="register")
        user_id = int(token_payload["sub"])
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    caller_role = UserRole(current_user["role"]) if current_user else None
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    return await AuthServices.verify_device_register(
        user_id=user_id,
        data=data,
        request_ip=client_ip,
        user_agent=user_agent,
        db=db,
        caller_role=caller_role,
    )


@router.post(
    "/device/login/challenge",
    response_model=DeviceLoginChallengeResponse,
    status_code=status.HTTP_200_OK,
    summary="Request login challenge for registered hardware device",
)
async def device_login_challenge(
    data: DeviceLoginChallengeRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    return await AuthServices.generate_device_login_challenge(
        identifier=data.identifier, db=db, request=request
    )


@router.post(
    "/device/login/verify",
    response_model=TokenRes,
    status_code=status.HTTP_200_OK,
    summary="Verify hardware signature from PC chip and issue session tokens",
)
async def device_login_verify(
    data: DeviceLoginVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    client_ip = request.client.host if request.client else None
    return await AuthServices.verify_device_login(data=data, request_ip=client_ip, db=db)


@router.get(
    "/device/status",
    summary="Check device binding status for current authenticated user",
)
async def get_my_device_status(
    current_user: UserAuth = Depends(all_guard),
    db: AsyncSession = Depends(get_async_db),
):
    result = await db.execute(
        select(UserDevice).where(UserDevice.user_id == current_user["id"], UserDevice.is_active == True)
    )
    device = result.scalar_one_or_none()
    return {
        "has_registered_device": device is not None,
        "device_name": device.device_name if device else None,
        "registered_at": device.registered_at if device else None,
        "last_login_at": device.last_login_at if device else None,
    }
