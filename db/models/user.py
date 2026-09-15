from enum import Enum
import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Enum as SQLEnum, ForeignKey
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.mahalla import Mahalla


class UserRole(str, Enum):
    ADMIN = "admin"
    PROKUROR = "prokuror"
    MAHALLA_RAISI = "mahalla_raisi"
    HOKIM_YORDAMCHISI = "hokim_yordamchisi"
    YOSHLAR_YETAKCHISI = "yoshlar_yetakchisi"
    XOTIN_QIZLAR_FAOLI = "xotin_qizlar_faoli"
    PROFILAKTIKA_INSPEKTORI = "profilaktika_inspektori"
    SOLIQ_INSPEKTORI = "soliq_inspektori"
    IJTIMOIY_XODIM = "ijtimoiy_xodim"


# The 7 members of a Mahalla ("Mahalla yettiligi")
MAHALLA_SEVEN_ROLES = {
    UserRole.MAHALLA_RAISI,
    UserRole.HOKIM_YORDAMCHISI,
    UserRole.YOSHLAR_YETAKCHISI,
    UserRole.XOTIN_QIZLAR_FAOLI,
    UserRole.PROFILAKTIKA_INSPEKTORI,
    UserRole.SOLIQ_INSPEKTORI,
    UserRole.IJTIMOIY_XODIM,
}


class User(Base):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(nullable=False)
    last_name: Mapped[str] = mapped_column(nullable=False)
    phone: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    login: Mapped[Optional[str]] = mapped_column(unique=True, index=True, nullable=True)
    password: Mapped[Optional[str]] = mapped_column(nullable=True)  # Nullable for external auth (e-imzo/myid)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", native_enum=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(server_default="t", default=True)

    mahalla_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("mahallas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    mahalla: Mapped[Optional["Mahalla"]] = relationship(
        "Mahalla", back_populates="members", lazy="selectin"
    )

