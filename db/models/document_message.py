from enum import Enum
import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Text, Date, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func

from db.connection import Base
from db.models.base_enum import RobustEnumType

if TYPE_CHECKING:
    from db.models.document import CheckInDocument
    from db.models.user import User


class DocumentMessageType(str, Enum):
    TEXT = "text"
    EXTENSION_REQUEST = "extension_request"
    EXTENSION_GRANTED = "extension_granted"
    EXTENSION_REJECTED = "extension_rejected"
    SYSTEM = "system"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            val_lower = value.lower()
            for member in cls:
                if member.value == val_lower:
                    return member
        return None


class DocumentMessage(Base):
    __tablename__ = "document_messages"

    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("check_in_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[DocumentMessageType] = mapped_column(
        RobustEnumType(DocumentMessageType),
        default=DocumentMessageType.TEXT,
        nullable=False,
    )
    requested_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)
    granted_date: Mapped[Optional[datetime.date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["CheckInDocument"] = relationship(
        "CheckInDocument", back_populates="messages"
    )
    sender: Mapped["User"] = relationship("User", lazy="selectin")
