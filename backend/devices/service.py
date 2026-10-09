import datetime
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import webauthn
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from backend.auth.schemas.token import TokenRes
from backend.auth.service import AuthServices
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
from db.models.user import User
from db.models.user_device import UserDevice


class ChallengeStore:
    """Thread-safe in-memory challenge cache with 180s TTL."""

    def __init__(self, ttl_seconds: int = 180) -> None:
        self._ttl: int = ttl_seconds
        self._store: Dict[str, Tuple[bytes, float]] = {}
        self._lock: threading.Lock = threading.Lock()

    def set(self, key: str, challenge: bytes) -> None:
        with self._lock:
            self._cleanup()
            self._store[key] = (challenge, time.time() + self._ttl)

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            self._cleanup()
            item = self._store.get(key)
            if item is None:
                return None
            challenge, expires_at = item
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return challenge

    def pop(self, key: str) -> Optional[bytes]:
        with self._lock:
            self._cleanup()
            item = self._store.pop(key, None)
            if item is None:
                return None
            challenge, expires_at = item
            if time.time() > expires_at:
                return None
            return challenge

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if now > exp]
        for k in expired:
            self._store.pop(k, None)


challenge_store = ChallengeStore(ttl_seconds=180)

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "https://prokratura.techsoftx.uz",
    "http://prokratura.techsoftx.uz",
]


def get_rp_id(request: Optional[Request] = None) -> str:
    env_rp = os.getenv("WEBAUTHN_RP_ID")
    if env_rp:
        return env_rp
    if request:
        host = request.headers.get("host")
        if host:
            return host.split(":")[0]
    return "localhost"


def get_rp_name() -> str:
    return os.getenv("WEBAUTHN_RP_NAME", "Prokratura Uzbekistan")


def get_expected_origins(request: Optional[Request] = None) -> List[str]:
    origins = list(DEFAULT_ORIGINS)
    custom = os.getenv("WEBAUTHN_ORIGIN")
    if custom:
        origins.extend([o.strip() for o in custom.split(",") if o.strip()])
    if request:
        origin_header = request.headers.get("origin")
        if origin_header and origin_header not in origins:
            origins.append(origin_header)
    return origins


class DeviceService:
    @staticmethod
    def device_to_response(device: UserDevice) -> DeviceResponseSchema:
        cred_id_str = bytes_to_base64url(device.credential_id) if isinstance(device.credential_id, bytes) else str(device.credential_id)
        return DeviceResponseSchema(
            id=device.id,
            user_id=device.user_id,
            credential_id=cred_id_str,
            device_name=device.device_name,
            aaguid=device.aaguid,
            sign_count=device.sign_count,
            created_at=device.registered_at,
            last_used_at=device.last_login_at,
        )

    @staticmethod
    def _extract_credential(
        payload: Union[RegisterVerifyRequestSchema, LoginVerifyRequestSchema, dict, str]
    ) -> Union[Dict[str, Any], str]:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            if "credential" in payload and payload["credential"] is not None:
                return payload["credential"]
            return payload
        if payload.credential is not None:
            return payload.credential
        dumped = payload.model_dump(exclude_unset=True)
        dumped.pop("device_name", None)
        dumped.pop("identifier", None)
        return dumped

    @classmethod
    async def generate_registration_options(
        cls,
        user_id: int,
        db: AsyncSession,
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        # Enforce single-device restriction
        existing = await db.execute(
            select(UserDevice.id).where(UserDevice.user_id == user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has a registered device. Only one device per user is permitted.",
            )

        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )

        rp_id = get_rp_id(request)
        rp_name = get_rp_name()

        options = webauthn.generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_id=str(user.id).encode("utf-8"),
            user_name=user.login or user.phone,
            user_display_name=f"{user.first_name} {user.last_name}",
            authenticator_selection=AuthenticatorSelectionCriteria(
                authenticator_attachment=AuthenticatorAttachment.PLATFORM,
                user_verification=UserVerificationRequirement.REQUIRED,
                resident_key=ResidentKeyRequirement.PREFERRED,
            ),
            timeout=180000,
        )

        challenge_store.set(f"reg:{user.id}", options.challenge)
        return json.loads(webauthn.options_to_json(options))

    @classmethod
    async def verify_registration(
        cls,
        user_id: int,
        data: RegisterVerifyRequestSchema,
        db: AsyncSession,
        request: Optional[Request] = None,
    ) -> DeviceResponseSchema:
        # Enforce single-device restriction
        existing = await db.execute(
            select(UserDevice.id).where(UserDevice.user_id == user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has a registered device. Only one device per user is permitted.",
            )

        challenge = challenge_store.pop(f"reg:{user_id}")
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration challenge expired or not found",
            )

        credential_data = cls._extract_credential(data)
        rp_id = get_rp_id(request)
        expected_origins = get_expected_origins(request)

        try:
            verified = webauthn.verify_registration_response(
                credential=credential_data,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=expected_origins,
                require_user_verification=False,
            )
        except WebAuthnException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration verification failed: {e}",
            )

        # Ensure credential ID is not already claimed by another user
        cred_id_str = bytes_to_base64url(verified.credential_id) if isinstance(verified.credential_id, bytes) else str(verified.credential_id)
        pub_key_str = bytes_to_base64url(verified.credential_public_key) if isinstance(verified.credential_public_key, bytes) else str(verified.credential_public_key)

        existing_cred = await db.execute(
            select(UserDevice.id).where(UserDevice.credential_id == cred_id_str)
        )
        if existing_cred.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This hardware device is already registered to another user.",
            )

        new_device = UserDevice(
            user_id=user_id,
            credential_id=cred_id_str,
            public_key=pub_key_str,
            sign_count=verified.sign_count,
            aaguid=verified.aaguid,
            device_name=data.device_name or "Hardware Authenticator",
            last_login_at=datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None),
        )
        db.add(new_device)
        try:
            await db.commit()
            await db.refresh(new_device)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has a registered device. Only one device per user is permitted.",
            )

        return cls.device_to_response(new_device)

    @classmethod
    async def generate_login_options(
        cls,
        data: LoginOptionsRequestSchema,
        db: AsyncSession,
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        result = await db.execute(
            select(User).where(
                or_(User.login == data.identifier, User.phone == data.identifier)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive",
            )

        dev_res = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user.id)
        )
        device = dev_res.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered hardware device found for this user",
            )

        rp_id = get_rp_id(request)
        options = webauthn.generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=[
                PublicKeyCredentialDescriptor(
                    id=base64url_to_bytes(device.credential_id)
                    if isinstance(device.credential_id, str)
                    else device.credential_id
                )
            ],
            user_verification=UserVerificationRequirement.REQUIRED,
            timeout=180000,
        )

        challenge_store.set(f"auth:{user.id}", options.challenge)
        return json.loads(webauthn.options_to_json(options))

    @classmethod
    async def verify_login(
        cls,
        data: LoginVerifyRequestSchema,
        db: AsyncSession,
        request: Optional[Request] = None,
    ) -> TokenRes:
        result = await db.execute(
            select(User).where(
                or_(User.login == data.identifier, User.phone == data.identifier)
            )
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials or user inactive",
            )

        dev_res = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user.id)
        )
        device = dev_res.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered hardware device found for this user",
            )

        challenge = challenge_store.pop(f"auth:{user.id}")
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authentication challenge expired or not found",
            )

        credential_data = cls._extract_credential(data)
        rp_id = get_rp_id(request)
        expected_origins = get_expected_origins(request)

        try:
            verified = webauthn.verify_authentication_response(
                credential=credential_data,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=expected_origins,
                credential_public_key=base64url_to_bytes(device.public_key) if isinstance(device.public_key, str) else device.public_key,
                credential_current_sign_count=device.sign_count,
                require_user_verification=False,
            )
        except WebAuthnException as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Device authentication failed: {e}",
            )

        verified_cred_id_str = bytes_to_base64url(verified.credential_id) if isinstance(verified.credential_id, bytes) else str(verified.credential_id)
        if verified_cred_id_str != device.credential_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credential ID does not match registered device",
            )

        # Update sign_count and last_login_at
        device.sign_count = verified.new_sign_count
        device.last_login_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        await db.commit()

        # Issue JWT tokens
        return AuthServices.issue_tokens(user)

    @classmethod
    async def get_device_status(
        cls,
        user_id: int,
        db: AsyncSession,
    ) -> DeviceStatusResponseSchema:
        result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            return DeviceStatusResponseSchema(
                is_bound=False,
                has_device=False,
                device=None,
            )

        dev_resp = cls.device_to_response(device)
        return DeviceStatusResponseSchema(
            is_bound=True,
            has_device=True,
            device=dev_resp,
            id=device.id,
            user_id=device.user_id,
            credential_id=dev_resp.credential_id,
            device_name=device.device_name,
            aaguid=device.aaguid,
            sign_count=device.sign_count,
            created_at=device.registered_at,
            last_used_at=device.last_login_at,
        )

    @classmethod
    async def unbind_device(
        cls,
        user_id: int,
        db: AsyncSession,
    ) -> MessageResponseSchema:
        result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered device found",
            )

        await db.delete(device)
        await db.commit()
        return MessageResponseSchema(message="Device successfully unbound")

    @classmethod
    async def admin_reset_device(
        cls,
        target_user_id: int,
        db: AsyncSession,
    ) -> MessageResponseSchema:
        target_user = (
            await db.execute(select(User).where(User.id == target_user_id))
        ).scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == target_user_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User does not have a registered device",
            )

        await db.delete(device)
        await db.commit()
        return MessageResponseSchema(
            message=f"Device reset successfully for user {target_user_id}"
        )

    @classmethod
    async def update_device_name(
        cls,
        user_id: int,
        data: DeviceUpdateSchema,
        db: AsyncSession,
    ) -> DeviceResponseSchema:
        result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user_id)
        )
        device = result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered device found",
            )

        if data.device_name is not None:
            device.device_name = data.device_name
        await db.commit()
        await db.refresh(device)
        return cls.device_to_response(device)
