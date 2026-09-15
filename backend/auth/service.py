import os
from datetime import datetime, timedelta, timezone
from typing import Optional, MutableMapping, Any, List
from typing_extensions import TypedDict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.schemas.register import RegisterSchema
from backend.auth.schemas.token import TokenRes
from db.connection import get_async_db
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES

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
        payload = {
            "sub": str(user.id),
            "login": user.login,
            "phone": user.phone,
            "role": user.role.value,
        }
        access_token = cls.create_access_token(payload)
        refresh_token = cls.create_refresh_token(payload)
        return TokenRes(
            access_token=access_token,
            refresh_token=refresh_token,
            role=user.role,
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
        }
        return cls.create_access_token(new_access_payload)


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
            select(User.id, User.login, User.phone, User.role, User.mahalla_id, User.is_active).where(
                User.id == user_id
            )
        )
        row = result.first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        uid, login, phone, role, mahalla_id, is_active = row
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
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

