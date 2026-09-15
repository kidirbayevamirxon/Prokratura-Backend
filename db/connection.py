# db/connection.py
from os import getenv
from dotenv import load_dotenv
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, mapped_column, Mapped
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from typing import AsyncGenerator

load_dotenv()

# Normal DB
DB_URL = getenv("DB_URL", "postgresql://prokratura:prokratura_pass@localhost:5439/prokratura")

# Async DB
ASYNC_DB_URL = getenv(
    "ASYNC_DB_URL",
    "postgresql+asyncpg://prokratura:prokratura_pass@localhost:5439/prokratura",
)

# Test DB (used in pytest)
TEST_ASYNC_DB_URL = getenv("TEST_ASYNC_DB_URL", "sqlite+aiosqlite:///:memory:")

# Engines
engine = create_engine(DB_URL)
async_engine = create_async_engine(ASYNC_DB_URL)
test_async_engine = create_async_engine(TEST_ASYNC_DB_URL)

# Session makers
SessionLocal = sessionmaker(bind=engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, expire_on_commit=False, class_=AsyncSession
)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_test_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        yield session

