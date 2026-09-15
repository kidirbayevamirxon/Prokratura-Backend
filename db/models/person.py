import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Date, Boolean, ForeignKey
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.mahalla import Mahalla
    from db.models.assignment import PersonCategoryAssignment


class Person(Base):
    __tablename__ = "persons"

    full_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    birth_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    mahalla_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("mahallas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="t", default=True)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    mahalla: Mapped["Mahalla"] = relationship("Mahalla", lazy="selectin")
    assignments: Mapped[List["PersonCategoryAssignment"]] = relationship(
        "PersonCategoryAssignment", back_populates="person", lazy="selectin", cascade="all, delete-orphan"
    )

