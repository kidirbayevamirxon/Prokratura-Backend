import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.user import User


class Mahalla(Base):
    __tablename__ = "mahallas"

    name: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(server_default="t", default=True)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[List["User"]] = relationship(
        "User", back_populates="mahalla", lazy="selectin"
    )

