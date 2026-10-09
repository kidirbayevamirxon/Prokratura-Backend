import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.user import User


class UserDevice(Base):
    """Stores the single active hardware-backed cryptographic device credential for a user.
    Enforces on-chip WebAuthn / FIDO2 authentication per user.
    """
    __tablename__ = "user_devices"

    # Enforce exactly ONE registered device per user via unique constraint
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    device_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    credential_id: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)  # Base64url-encoded COSE / SPKI key
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    aaguid: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="t", nullable=False)

    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    registered_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    last_login_at: Mapped[Optional[datetime.datetime]] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="device")
