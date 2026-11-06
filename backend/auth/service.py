import os
from datetime import datetime, timedelta, timezone
from typing import Optional, MutableMapping, Any, List
from typing_extensions import TypedDict
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession


def get_auth_rp_id(request: Optional[Request] = None) -> str:
    env_rp = os.getenv("RP_ID") or os.getenv("WEBAUTHN_RP_ID")
    if env_rp:
        return env_rp
    if request:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if host:
            return host.split(":")[0]
    return "localhost"

from backend.auth.schemas.register import RegisterSchema
from backend.auth.schemas.token import TokenRes
from backend.auth.schemas.device import (
    DeviceRegisterChallengeResponse,
    DeviceRegisterVerifyRequest,
    DeviceLoginChallengeResponse,
    DeviceLoginVerifyRequest,
    DeviceTransferTokenResponse,
)
from backend.auth.webauthn_utils import (
    generate_challenge,
    create_challenge_token,
    verify_challenge_token,
    parse_and_verify_client_data,
    parse_attestation,
    verify_assertion_signature,
    urlsafe_b64encode,
)
from db.connection import get_async_db
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES
from db.models.user_device import UserDevice

ACCESS_SECRET = os.getenv("ACCESS_SECRET", "prokratura_access_secret_key_change_in_production")
REFRESH_SECRET = os.getenv("REFRESH_SECRET", "prokratura_refresh_secret_key_change_in_production")
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=True)


class TokenPayload(TypedDict):
    sub: str  # user.id
    login: Optional[str]
    phone: str
    role: str
    ver: Optional[int]  # user.token_version for instant session revocation
    exp: Optional[int]


class UserAuth(TypedDict):
    id: int
    login: Optional[str]
    phone: str
    role: UserRole
    mahalla_id: Optional[int]


class AuthServices:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not hashed_password:
            return False
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=1))
        to_encode["exp"] = int(expire.timestamp())
        return jwt.encode(to_encode, ACCESS_SECRET, algorithm=ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=7))
        to_encode["exp"] = int(expire.timestamp())
        return jwt.encode(to_encode, REFRESH_SECRET, algorithm=ALGORITHM)

    @staticmethod
    def verify_token(token: str, secret_key: str) -> Optional[dict[str, Any]]:
        try:
            return jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        except JWTError:
            return None

    @classmethod
    def issue_tokens(cls, user: User) -> TokenRes:
        """Issue JWT tokens for any verified user entity.
        This enables plugging in USB key (E-IMZO) and MyID/OneID strategies seamlessly.
        """
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role).lower()
        role_enum = user.role if isinstance(user.role, UserRole) else UserRole(role_val)
        payload = {
            "sub": str(user.id),
            "login": user.login,
            "phone": user.phone,
            "role": role_val,
            "ver": user.token_version,
        }
        access_token = cls.create_access_token(payload)
        refresh_token = cls.create_refresh_token(payload)
        return TokenRes(
            access_token=access_token,
            refresh_token=refresh_token,
            role=role_enum,
            user_id=user.id,
            mahalla_id=user.mahalla_id,
        )

    @classmethod
    async def register(cls, data: RegisterSchema, db: AsyncSession) -> TokenRes:
        if data.login:
            login_exist = (
                await db.execute(select(User.id).where(User.login == data.login))
            ).scalars().first()
            if login_exist:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Login already exists",
                )

        phone_exist = (
            await db.execute(select(User.id).where(User.phone == data.phone))
        ).scalars().first()
        if phone_exist:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number already exists",
            )

        hashed_password = cls.hash_password(data.password)
        new_user = User(
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            login=data.login,
            password=hashed_password,
            role=data.role or UserRole.PROKUROR,
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return cls.issue_tokens(new_user)

    @classmethod
    async def login(cls, identifier: str, password: str, db: AsyncSession) -> TokenRes:
        result = await db.execute(
            select(User).where(
                or_(User.login == identifier, User.phone == identifier)
            )
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login or password",
            )

        if not user.password or not cls.verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login or password",
            )

        # If user has an active hardware device, device login is supported,
        # but valid password authentication is also accepted for standard sign-in.
        return cls.issue_tokens(user)

    @classmethod
    async def refresh(cls, refresh_token: str, db: AsyncSession) -> str:
        payload = cls.verify_token(refresh_token, REFRESH_SECRET)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user_id = int(payload["sub"])
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        new_access_payload = {
            "sub": str(user.id),
            "login": user.login,
            "phone": user.phone,
            "role": user.role.value,
            "ver": user.token_version,
        }
        return cls.create_access_token(new_access_payload)

    @classmethod
    async def generate_device_register_challenge(
        cls,
        user_id: int,
        db: AsyncSession,
        caller_role: Optional[UserRole] = None,
        is_transfer: bool = False,
        request: Optional[Request] = None,
    ) -> DeviceRegisterChallengeResponse:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive",
            )

        # Once pairing device, changing or removing it should only be accessible to prokuror and admin
        existing_device = (
            await db.execute(
                select(UserDevice).where(
                    UserDevice.user_id == user_id,
                    UserDevice.is_active == True,
                )
            )
        ).scalar_one_or_none()

        if existing_device and not is_transfer:
            if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Biriktirilgan qurilmani faqat Prokuror yoki Admin o'zgartirishi mumkin.",
                )

        challenge_b64, _ = generate_challenge()
        challenge_token = create_challenge_token(
            user.id,
            challenge_b64,
            "register",
            is_transfer=is_transfer,
            caller_role=caller_role.value if caller_role else (user.role.value if user else None),
        )
        user_id_b64 = urlsafe_b64encode(user.id.to_bytes(8, "big"))
        rp_id = get_auth_rp_id(request)

        return DeviceRegisterChallengeResponse(
            challenge=challenge_b64,
            challenge_token=challenge_token,
            rp={"name": "Prokratura Uzbekistan", "id": rp_id},
            user={
                "id": user_id_b64,
                "name": user.login or user.phone,
                "displayName": f"{user.first_name} {user.last_name}",
            },
            pub_key_cred_params=[
                {"alg": -7, "type": "public-key"},   # ES256 (ECDSA P-256)
                {"alg": -257, "type": "public-key"}, # RS256
            ],
            authenticator_selection={
                "userVerification": "preferred",
                "residentKey": "preferred",
            },
            timeout=60000,
        )

    @classmethod
    async def verify_device_register(
        cls,
        user_id: int,
        data: DeviceRegisterVerifyRequest,
        request_ip: Optional[str],
        user_agent: Optional[str],
        db: AsyncSession,
        caller_role: Optional[UserRole] = None,
        is_transfer: bool = False,
    ) -> TokenRes:
        # 1. Verify signed challenge token
        try:
            token_payload = verify_challenge_token(data.challenge_token, expected_type="register")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        if int(token_payload["sub"]) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Challenge token does not match user",
            )

        expected_challenge = token_payload["challenge"]
        is_transfer = is_transfer or token_payload.get("is_transfer", False)

        # 2. Verify clientDataJSON
        try:
            parse_and_verify_client_data(data.client_data_json, expected_challenge, "webauthn.create")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # 3. Parse attestationObject and extract credential data
        try:
            cred_id_b64, pub_key_b64, aaguid_str = parse_attestation(data.attestation_object)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse hardware attestation: {str(e)}",
            )

        if data.credential_id.rstrip("=") != cred_id_b64.rstrip("="):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credential ID mismatch between request and attestation",
            )

        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive",
            )

        # 4. Enforce SINGLE DEVICE INVARIANT: replace/update user's active device
        if caller_role is None:
            token_role = token_payload.get("caller_role")
            if token_role:
                try:
                    caller_role = UserRole(token_role)
                except ValueError:
                    pass
            elif user and user.role:
                caller_role = user.role

        existing_device = (
            await db.execute(select(UserDevice).where(UserDevice.user_id == user_id))
        ).scalar_one_or_none()

        if existing_device and not is_transfer:
            if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Biriktirilgan qurilmani faqat Prokuror yoki Admin o'zgartirishi mumkin.",
                )

        if existing_device:
            existing_device.credential_id = cred_id_b64
            existing_device.public_key = pub_key_b64
            existing_device.sign_count = 0
            existing_device.aaguid = aaguid_str
            existing_device.device_name = data.device_name or existing_device.device_name or "Hardware Key"
            existing_device.user_agent = user_agent
            existing_device.last_ip = request_ip
            existing_device.is_active = True
            existing_device.last_login_at = func.now()
        else:
            new_device = UserDevice(
                user_id=user_id,
                credential_id=cred_id_b64,
                public_key=pub_key_b64,
                sign_count=0,
                aaguid=aaguid_str,
                device_name=data.device_name or "Hardware Key",
                user_agent=user_agent,
                last_ip=request_ip,
                is_active=True,
                last_login_at=func.now(),
            )
            db.add(new_device)

        # Invalidate previous sessions
        user.token_version += 1
        await db.commit()
        await db.refresh(user)

        return cls.issue_tokens(user)

    @classmethod
    async def generate_device_login_challenge(
        cls,
        identifier: str,
        db: AsyncSession,
        request: Optional[Request] = None,
    ) -> DeviceLoginChallengeResponse:
        result = await db.execute(
            select(User).where(or_(User.login == identifier, User.phone == identifier))
        )
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        dev_result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.is_active == True)
        )
        device = dev_result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No registered active device for this user. Please register a device first.",
            )

        challenge_b64, _ = generate_challenge()
        challenge_token = create_challenge_token(user.id, challenge_b64, "login")
        rp_id = get_auth_rp_id(request)

        return DeviceLoginChallengeResponse(
            challenge=challenge_b64,
            challenge_token=challenge_token,
            credential_id=device.credential_id,
            rp_id=rp_id,
        )

    @classmethod
    async def verify_device_login(
        cls,
        data: DeviceLoginVerifyRequest,
        request_ip: Optional[str],
        db: AsyncSession,
    ) -> TokenRes:
        # 1. Verify challenge token
        try:
            token_payload = verify_challenge_token(data.challenge_token, expected_type="login")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        user_id = int(token_payload["sub"])
        expected_challenge = token_payload["challenge"]

        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # 2. Get registered active device
        dev_result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.is_active == True)
        )
        device = dev_result.scalar_one_or_none()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active device registered for this user",
            )

        # Enforce single device identity
        if data.credential_id.rstrip("=") != device.credential_id.rstrip("="):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Device mismatch: This credential is not the active registered device for this user",
            )

        # 3. Verify clientDataJSON
        try:
            parse_and_verify_client_data(data.client_data_json, expected_challenge, "webauthn.get")
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        # 4. Verify cryptographic signature from hardware chip
        try:
            new_sign_count = verify_assertion_signature(
                device.public_key,
                data.authenticator_data,
                data.client_data_json,
                data.signature,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Hardware signature verification failed: {str(e)}",
            )

        # Check monotonic counter if supported
        if new_sign_count > 0 and new_sign_count <= device.sign_count:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Potential authenticator clone or replay attack detected",
            )

        device.sign_count = new_sign_count
        device.last_login_at = func.now()
        if request_ip:
            device.last_ip = request_ip

        await db.commit()
        await db.refresh(user)

        return cls.issue_tokens(user)

    @classmethod
    async def create_transfer_token(cls, user_id: int) -> DeviceTransferTokenResponse:
        """Create a 5-minute single-use transfer token allowing new device enrollment."""
        challenge_b64, _ = generate_challenge()
        transfer_token = create_challenge_token(user_id, challenge_b64, "register", expires_in=300)
        return DeviceTransferTokenResponse(
            transfer_token=transfer_token,
            expires_in=300,
            message="Device transfer token valid for 5 minutes. Use on new PC to bind its hardware key.",
        )


class AuthGuard:
    def __init__(self, roles: List[UserRole]):
        self.roles = roles

    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_async_db),
    ) -> UserAuth:
        token = credentials.credentials
        payload = AuthServices.verify_token(token, ACCESS_SECRET)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            )

        user_id = int(payload["sub"])
        result = await db.execute(
            select(
                User.id,
                User.login,
                User.phone,
                User.role,
                User.mahalla_id,
                User.is_active,
                User.token_version,
            ).where(User.id == user_id)
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        uid, login, phone, role, mahalla_id, is_active, token_version = row
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Enforce instant session invalidation when device is reset/changed
        token_ver = payload.get("ver")
        if token_ver is not None and token_ver != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked or device changed. Please log in again.",
            )

        if role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: requires one of {[r.value for r in self.roles]}",
            )

        return {
            "id": uid,
            "login": login,
            "phone": phone,
            "role": role,
            "mahalla_id": mahalla_id,
        }


# Guards for routes
admin_guard = AuthGuard([UserRole.ADMIN])
prokuror_guard = AuthGuard([UserRole.ADMIN, UserRole.PROKUROR])
prokuror_or_admin_guard = AuthGuard([UserRole.ADMIN, UserRole.PROKUROR])
rais_guard = AuthGuard([UserRole.ADMIN, UserRole.PROKUROR, UserRole.MAHALLA_RAISI])
mahalla_guard = AuthGuard([UserRole.ADMIN, UserRole.PROKUROR, *MAHALLA_SEVEN_ROLES])
all_guard = AuthGuard([UserRole.ADMIN, UserRole.PROKUROR, *MAHALLA_SEVEN_ROLES])

optional_security = HTTPBearer(auto_error=False)


async def optional_guard(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_async_db),
) -> Optional[UserAuth]:
    if not credentials:
        return None
    try:
        return await all_guard(credentials=credentials, db=db)
    except HTTPException:
        return None

