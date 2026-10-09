import os
import datetime
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
from db.models.category import Category
from db.models.person import Person
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.document import CheckInDocument, CheckInDocType, CheckInDocStatus
from backend.auth.service import AuthServices

TABLES_TO_CLEAN = "user_devices, users, mahallas, mahalla_stats, categories, persons, person_category_assignments, check_in_documents"


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(f"TRUNCATE TABLE {TABLES_TO_CLEAN} RESTART IDENTITY CASCADE;"))
    await engine.dispose()
    yield
    engine = create_async_engine(ASYNC_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {TABLES_TO_CLEAN} RESTART IDENTITY CASCADE;"))
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


@pytest_asyncio.fixture
async def inspector_user(db_session: AsyncSession, sample_mahalla: Mahalla) -> User:
    user = User(
        first_name="Mansur",
        last_name="Polatov",
        phone="+998901114455",
        login="inspector_mansur",
        password=AuthServices.hash_password("mansur123"),
        role=UserRole.PROFILAKTIKA_INSPEKTORI,
        mahalla_id=sample_mahalla.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inspector_token(inspector_user: User) -> str:
    tokens = AuthServices.issue_tokens(inspector_user)
    return tokens.access_token


@pytest_asyncio.fixture
async def women_activist_user(db_session: AsyncSession, sample_mahalla: Mahalla) -> User:
    user = User(
        first_name="Zulhumor",
        last_name="Karimova",
        phone="+998902223344",
        login="activist_zulhumor",
        password=AuthServices.hash_password("zulhumor123"),
        role=UserRole.XOTIN_QIZLAR_FAOLI,
        mahalla_id=sample_mahalla.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def women_activist_token(women_activist_user: User) -> str:
    tokens = AuthServices.issue_tokens(women_activist_user)
    return tokens.access_token


@pytest_asyncio.fixture
async def sample_category(db_session: AsyncSession) -> Category:
    category = Category(
        name="Проф ҳисоб рўйхати",
        description="Preventive registration list",
        assigned_roles=[UserRole.PROFILAKTIKA_INSPEKTORI.value],
        default_frequency_days=5,
        is_active=True,
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def sample_person(db_session: AsyncSession, sample_mahalla: Mahalla) -> Person:
    person = Person(
        full_name="Даўлетбаев Айдос Муратбаевич",
        birth_date=datetime.date(1990, 7, 30),
        mahalla_id=sample_mahalla.id,
        is_active=True,
    )
    db_session.add(person)
    await db_session.commit()
    await db_session.refresh(person)
    return person


@pytest_asyncio.fixture
async def sample_assignment(
    db_session: AsyncSession,
    sample_person: Person,
    sample_category: Category,
    sample_mahalla: Mahalla,
    prokuror_user: User,
) -> PersonCategoryAssignment:
    assignment = PersonCategoryAssignment(
        person_id=sample_person.id,
        category_id=sample_category.id,
        mahalla_id=sample_mahalla.id,
        frequency_days=5,
        assigned_roles=[UserRole.PROFILAKTIKA_INSPEKTORI.value],
        next_check_in_due=datetime.date.today() + datetime.timedelta(days=5),
        status=AssignmentStatus.ACTIVE,
        created_by_id=prokuror_user.id,
    )
    db_session.add(assignment)
    await db_session.commit()
    await db_session.refresh(assignment)
    return assignment
