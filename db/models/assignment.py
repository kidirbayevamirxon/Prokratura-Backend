from enum import Enum
import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Date, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.person import Person
    from db.models.category import Category
    from db.models.mahalla import Mahalla
    from db.models.user import User
    from db.models.document import CheckInDocument


class AssignmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    REMOVED = "removed"


class PersonCategoryAssignment(Base):
    __tablename__ = "person_category_assignments"

    person_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mahalla_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("mahallas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frequency_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    assigned_roles: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    next_check_in_due: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        SQLEnum(AssignmentStatus, name="assignment_status", native_enum=False),
        default=AssignmentStatus.ACTIVE,
        nullable=False,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    person: Mapped["Person"] = relationship("Person", back_populates="assignments", lazy="selectin")
    category: Mapped["Category"] = relationship("Category", lazy="selectin")
    mahalla: Mapped["Mahalla"] = relationship("Mahalla", lazy="selectin")
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id], lazy="selectin")
    documents: Mapped[List["CheckInDocument"]] = relationship(
        "CheckInDocument",
        back_populates="assignment",
        lazy="selectin",
        order_by="desc(CheckInDocument.created_at)",
        cascade="all, delete-orphan",
    )

