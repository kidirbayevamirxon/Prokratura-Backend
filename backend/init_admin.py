import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from db.connection import ASYNC_DB_URL, Base, engine
from db.models.user import User, UserRole
from backend.auth.service import AuthServices

ADMIN_LOGIN = os.getenv("FIRST_ADMIN_LOGIN", "admin")
ADMIN_PHONE = os.getenv("FIRST_ADMIN_PHONE", "+998900000000")
ADMIN_PASSWORD = os.getenv("FIRST_ADMIN_PASSWORD", "AdminPass123!")

Base.metadata.create_all(engine)
async def seed_first_admin():
    print("[INIT] Database tables created (if not existing)")
    engine = create_async_engine(ASYNC_DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        # Check if any admin exists
        result = await session.execute(select(User).where(User.role == UserRole.ADMIN))
        admin = result.scalars().first()
        if not admin:
            new_admin = User(
                first_name="Super",
                last_name="Admin",
                phone=ADMIN_PHONE,
                login=ADMIN_LOGIN,
                password=AuthServices.hash_password(ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(new_admin)
            await session.commit()
            print(f"[INIT] Created initial admin: login='{ADMIN_LOGIN}', phone='{ADMIN_PHONE}'")
        else:
            print(f"[INIT] Admin already exists (id={admin.id}, login='{admin.login}')")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_first_admin())
