import datetime
from typing import Optional, List
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, JSON, String, Boolean
from sqlalchemy.sql import func

from db.connection import Base


class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    icon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    assigned_roles: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    default_frequency_days: Mapped[int] = mapped_column(default=7, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="t", default=True)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

