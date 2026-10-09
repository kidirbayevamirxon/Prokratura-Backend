from typing import Optional, Dict, Any
from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.files.service import FileService

from backend.auth.service import AuthServices
from backend.users.schemas.create import UserCreateSchema
from backend.users.schemas.patch import UserUpdateSchema
from backend.users.schemas.get import PaginatedUserSchema, UserResponseSchema
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES
from db.models.user_device import UserDevice
from db.models.mahalla import Mahalla


class UserService:
    @staticmethod
    async def create_user(
        data: UserCreateSchema,
        caller_role: UserRole,
        db: AsyncSession,
    ) -> User:
        # Check permissions for target role
        if data.role == UserRole.ADMIN:
            if caller_role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only an Admin can create another Admin",
                )

        if data.role == UserRole.PROKUROR:
            if caller_role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only an Admin can create a Prokuror",
                )
            # Enforce single active prokuror rule
            existing_prokuror = await db.execute(
                select(User.id).where(
                    User.role == UserRole.PROKUROR, User.is_active == True
                )
            )
            if existing_prokuror.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only one active Prokuror is allowed in the system",
                )

        if caller_role == UserRole.PROKUROR and data.role not in MAHALLA_SEVEN_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Prokuror can only create Mahalla officials ({[r.value for r in MAHALLA_SEVEN_ROLES]})",
            )

        # Check phone uniqueness
        existing_phone = await db.execute(
            select(User.id).where(User.phone == data.phone)
        )
        if existing_phone.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone '{data.phone}' already in use",
            )

        # Check login uniqueness if provided
        if data.login:
            existing_login = await db.execute(
                select(User.id).where(User.login == data.login)
            )
            if existing_login.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Login '{data.login}' already in use",
                )

        # If role is one of the 7 mahalla roles, verify mahalla exists and enforce 1 person per role
        if data.role in MAHALLA_SEVEN_ROLES:
            if not data.mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"mahalla_id is required for '{data.role.value}'",
                )

            mahalla = await db.get(Mahalla, data.mahalla_id)
            if not mahalla:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Mahalla with id {data.mahalla_id} does not exist",
                )

            # Enforce 1 active person per role per mahalla: replace previous occupant
            existing_role_holder = await db.execute(
                select(User).where(
                    User.mahalla_id == data.mahalla_id,
                    User.role == data.role,
                    User.is_active == True,
                )
            )
            prev_holder = existing_role_holder.scalar_one_or_none()
            if prev_holder:
                prev_holder.mahalla_id = None
                prev_holder.is_active = False

        hashed_password = (
            AuthServices.hash_password(data.password) if data.password else None
        )

        new_user = User(
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            login=data.login,
            password=hashed_password,
            role=data.role,
            mahalla_id=data.mahalla_id,
            photo_url=data.photo_url,
            birth_date_text=data.birth_date_text,
            appointed_date_text=data.appointed_date_text,
            specialization=data.specialization,
            previous_workplace=data.previous_workplace,
            is_active=data.is_active,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def get_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        login: Optional[str] = None,
        role: Optional[UserRole] = None,
        mahalla_id: Optional[int] = None,
        caller_role: Optional[UserRole] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> PaginatedUserSchema:
        # Permission check: other 6 officials cannot see other people
        if caller_role in MAHALLA_SEVEN_ROLES and caller_role != UserRole.MAHALLA_RAISI:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mahalla officials cannot view other members. You may only view your own profile.",
            )

        query = select(User)
        count_query = select(func.count(User.id))

        # Rais can only see users in their own mahalla
        if caller_role == UserRole.MAHALLA_RAISI:
            if caller_mahalla_id is None:
                return PaginatedUserSchema(
                    items=[], total=0, page=page, page_size=page_size
                )
            query = query.where(User.mahalla_id == caller_mahalla_id)
            count_query = count_query.where(User.mahalla_id == caller_mahalla_id)

        # 3 separate search filters
        if name:
            name_pattern = f"%{name.strip()}%"
            name_filter = or_(
                User.first_name.ilike(name_pattern),
                User.last_name.ilike(name_pattern),
            )
            query = query.where(name_filter)
            count_query = count_query.where(name_filter)

        if phone:
            phone_pattern = f"%{phone.strip()}%"
            query = query.where(User.phone.ilike(phone_pattern))
            count_query = count_query.where(User.phone.ilike(phone_pattern))

        if login:
            login_pattern = f"%{login.strip()}%"
            query = query.where(User.login.ilike(login_pattern))
            count_query = count_query.where(User.login.ilike(login_pattern))

        if role is not None:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)

        if mahalla_id is not None:
            query = query.where(User.mahalla_id == mahalla_id)
            count_query = count_query.where(User.mahalla_id == mahalla_id)

        total = (await db.execute(count_query)).scalar() or 0

        query = (
            query.order_by(User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(query)
        users = result.scalars().all()

        return PaginatedUserSchema(
            items=[UserResponseSchema.model_validate(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_user_by_id(
        user_id: int,
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Access check
        if caller_role in [UserRole.ADMIN, UserRole.PROKUROR]:
            return user

        if caller_role == UserRole.MAHALLA_RAISI:
            if user.mahalla_id == caller_mahalla_id or user.id == caller_id:
                return user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rais can only view members within their own Mahalla",
            )

        # Other 6 members can only view themselves
        if user_id != caller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own user profile",
            )

        return user

    @staticmethod
    async def update_user(
        user_id: int,
        data: UserUpdateSchema,
        caller_id: int,
        caller_role: UserRole,
        db: AsyncSession,
    ) -> User:
        # Rais and the other 6 members cannot change people
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if user_id != caller_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Mahalla officials cannot modify other users",
                )

        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Prokuror cannot modify Admin or another Prokuror
        if caller_role == UserRole.PROKUROR:
            if (
                user.role in [UserRole.ADMIN, UserRole.PROKUROR]
                and user.id != caller_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Prokuror cannot modify Admin or Prokuror accounts",
                )
            if data.role in [UserRole.ADMIN, UserRole.PROKUROR]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Prokuror cannot elevate roles to Admin or Prokuror",
                )

        if data.phone is not None and data.phone != user.phone:
            existing_phone = await db.execute(
                select(User.id).where(User.phone == data.phone, User.id != user_id)
            )
            if existing_phone.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Phone '{data.phone}' already in use",
                )
            user.phone = data.phone

        if data.login is not None and data.login != user.login:
            existing_login = await db.execute(
                select(User.id).where(User.login == data.login, User.id != user_id)
            )
            if existing_login.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Login '{data.login}' already in use",
                )
            user.login = data.login

        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        if data.password is not None:
            user.password = AuthServices.hash_password(data.password)
        if data.is_active is not None:
            user.is_active = data.is_active

        if data.mahalla_id is not None:
            if data.mahalla_id > 0:
                mahalla = await db.get(Mahalla, data.mahalla_id)
                if not mahalla:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Mahalla {data.mahalla_id} does not exist",
                    )
                user.mahalla_id = data.mahalla_id
            else:
                user.mahalla_id = None

        if data.role is not None:
            if data.role == UserRole.PROKUROR and caller_role == UserRole.ADMIN:
                # Check single prokuror constraint
                existing_p = await db.execute(
                    select(User.id).where(
                        User.role == UserRole.PROKUROR,
                        User.id != user_id,
                        User.is_active == True,
                    )
                )
                if existing_p.scalars().first():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Only one active Prokuror is allowed in the system",
                    )
                user.mahalla_id = None
            user.role = data.role

        if data.photo_url is not None:
            if user.photo_url and user.photo_url != data.photo_url:
                FileService.delete_file_by_url_or_path(user.photo_url)
            user.photo_url = data.photo_url
        if data.birth_date_text is not None:
            user.birth_date_text = data.birth_date_text
        if data.appointed_date_text is not None:
            user.appointed_date_text = data.appointed_date_text
        if data.specialization is not None:
            user.specialization = data.specialization
        if data.previous_workplace is not None:
            user.previous_workplace = data.previous_workplace

        # If user has a mahalla member role, enforce 1 person per role
        if user.mahalla_id and user.role in MAHALLA_SEVEN_ROLES and user.is_active:
            existing_holder = await db.execute(
                select(User).where(
                    User.mahalla_id == user.mahalla_id,
                    User.role == user.role,
                    User.id != user.id,
                    User.is_active == True,
                )
            )
            prev_holder = existing_holder.scalar_one_or_none()
            if prev_holder:
                prev_holder.mahalla_id = None
                prev_holder.is_active = False

        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def upload_photo(
        user_id: int,
        photo_file: UploadFile,
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> User:
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # RBAC Check:
        # Admin / Prokuror can upload for anyone
        # A user can upload their own photo
        # Mahalla Raisi can upload for members of their own mahalla
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if caller_id != user_id:
                if caller_role == UserRole.MAHALLA_RAISI:
                    if user.mahalla_id != caller_mahalla_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Rais can only upload photos for members of their own Mahalla",
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cannot upload photo for another user",
                    )

        old_photo_url = user.photo_url
        photo_url = await FileService.save_uploaded_photo(photo_file)
        user.photo_url = photo_url
        await db.commit()
        await db.refresh(user)

        if old_photo_url and old_photo_url != photo_url:
            FileService.delete_file_by_url_or_path(old_photo_url)

        return user

    @staticmethod
    async def delete_user(
        user_id: int,
        caller_role: UserRole,
        db: AsyncSession,
    ) -> bool:
        if caller_role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin can delete users",
            )
        user = await db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        await db.delete(user)
        await db.commit()
        return True

    @staticmethod
    async def reset_user_device(
        user_id: int,
        caller_id: int,
        caller_role: UserRole,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        target_user = await db.get(User, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Permissions:
        # Admin can reset anyone's PC (their own, other admins, prokurors, mahalla officials)
        # Prokuror can reset Mahalla officials or their own PC, but NOT other Prokurors or Admins
        if caller_role == UserRole.ADMIN:
            pass  # Allowed
        elif caller_role == UserRole.PROKUROR:
            if target_user.role in [UserRole.ADMIN, UserRole.PROKUROR] and target_user.id != caller_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Prokuror can only reset PC for Mahalla officials or their own device",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin and Prokuror can reset devices",
            )

        # Unlink device
        device_result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user_id)
        )
        device = device_result.scalar_one_or_none()
        if device:
            await db.delete(device)

        # Invalidate active sessions of target user
        target_user.token_version += 1
        await db.commit()
        await db.refresh(target_user)

        return {
            "message": f"Device unlinked successfully for user {target_user.login or target_user.phone}. User may now enroll a new PC.",
            "user_id": user_id,
            "status": "device_reset",
        }

    @staticmethod
    async def get_user_device(
        user_id: int,
        caller_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> Optional[UserDevice]:
        target_user = await db.get(User, user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Permissions to view device
        if caller_role == UserRole.ADMIN:
            pass
        elif caller_role == UserRole.PROKUROR:
            if target_user.role in [UserRole.ADMIN, UserRole.PROKUROR] and target_user.id != caller_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Prokuror cannot inspect devices of other prosecutors or admins",
                )
        elif user_id != caller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own device status",
            )

        device_result = await db.execute(
            select(UserDevice).where(UserDevice.user_id == user_id, UserDevice.is_active == True)
        )
        return device_result.scalar_one_or_none()

