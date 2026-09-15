import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

os.environ["ACCESS_SECRET"] = "test_access_secret_key_1234567890123456"
os.environ["REFRESH_SECRET"] = "test_refresh_secret_key_1234567890123456"

from db.connection import Base, get_async_db, ASYNC_DB_URL
from backend.main import app
from db.models.user import User, UserRole
from db.models.mahalla import Mahalla
from backend.auth.service import AuthServices


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE TABLE users, mahallas RESTART IDENTITY CASCADE;"))
    await engine.dispose()
    yield
    engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE users, mahallas RESTART IDENTITY CASCADE;"))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_async_db():
        yield db_session

    app.dependency_overrides[get_async_db] = override_get_async_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Super",
        last_name="Admin",
        phone="+998900000000",
        login="superadmin",
        password=AuthServices.hash_password("admin123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    tokens = AuthServices.issue_tokens(admin_user)
    return tokens.access_token


@pytest_asyncio.fixture
async def prokuror_user(db_session: AsyncSession) -> User:
    user = User(
        first_name="Alisher",
        last_name="Navoiy",
        phone="+998901112233",
        login="prokuror_boss",
        password=AuthServices.hash_password("prokuror123"),
        role=UserRole.PROKUROR,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def prokuror_token(prokuror_user: User) -> str:
    tokens = AuthServices.issue_tokens(prokuror_user)
    return tokens.access_token


@pytest_asyncio.fixture
async def sample_mahalla(db_session: AsyncSession) -> Mahalla:
    mahalla = Mahalla(name="Oqtepa MFY", is_active=True)
    db_session.add(mahalla)
    await db_session.commit()
    await db_session.refresh(mahalla)
    return mahalla


@pytest_asyncio.fixture
async def rais_user(db_session: AsyncSession, sample_mahalla: Mahalla) -> User:
    user = User(
        first_name="Temur",
        last_name="Barlos",
        phone="+998909998877",
        login="rais_oqtepa",
        password=AuthServices.hash_password("rais123"),
        role=UserRole.MAHALLA_RAISI,
        mahalla_id=sample_mahalla.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def rais_token(rais_user: User) -> str:
    tokens = AuthServices.issue_tokens(rais_user)
    return tokens.access_token


@pytest_asyncio.fixture
async def member_user(db_session: AsyncSession, sample_mahalla: Mahalla) -> User:
    user = User(
        first_name="Jasur",
        last_name="Yosh",
        phone="+998905554433",
        login="yoshlar_jasur",
        password=AuthServices.hash_password("jasur123"),
        role=UserRole.YOSHLAR_YETAKCHISI,
        mahalla_id=sample_mahalla.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def member_token(member_user: User) -> str:
    tokens = AuthServices.issue_tokens(member_user)
    return tokens.access_token
