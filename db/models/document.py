from enum import Enum
import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Text, Date, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.assignment import PersonCategoryAssignment
    from db.models.person import Person
    from db.models.category import Category
    from db.models.mahalla import Mahalla
    from db.models.user import User


class CheckInDocType(str, Enum):
    REGULAR = "regular"
    REMOVAL_REQUEST = "removal_request"


class CheckInDocStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CheckInDocument(Base):
    __tablename__ = "check_in_documents"

    assignment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("person_category_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    submitted_by_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    doc_type: Mapped[CheckInDocType] = mapped_column(
        SQLEnum(CheckInDocType, name="checkin_doc_type", native_enum=False),
        default=CheckInDocType.REGULAR,
        nullable=False,
    )
    photo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_in_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)

    status: Mapped[CheckInDocStatus] = mapped_column(
        SQLEnum(CheckInDocStatus, name="checkin_doc_status", native_enum=False),
        default=CheckInDocStatus.PENDING,
        nullable=False,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)

    seen_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    seen_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())

    assignment: Mapped["PersonCategoryAssignment"] = relationship(
        "PersonCategoryAssignment", back_populates="documents", lazy="selectin"
    )
    person: Mapped["Person"] = relationship("Person", lazy="selectin")
    category: Mapped["Category"] = relationship("Category", lazy="selectin")
    mahalla: Mapped["Mahalla"] = relationship("Mahalla", lazy="selectin")
    submitted_by: Mapped["User"] = relationship("User", foreign_keys=[submitted_by_id], lazy="selectin")
    reviewed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by_id], lazy="selectin")
    seen_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[seen_by_id], lazy="selectin")

