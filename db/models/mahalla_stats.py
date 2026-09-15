import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import BigInteger, String, Integer, JSON, ForeignKey
from sqlalchemy.sql import func

from db.connection import Base

if TYPE_CHECKING:
    from db.models.mahalla import Mahalla


class MahallaStats(Base):
    __tablename__ = "mahalla_stats"

    mahalla_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("mahallas.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Инфратузилма объектлари (Infrastructure)
    maydoni: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. "141.45 га"
    xonadonlar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1005
    savdo_dokonlari_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 6
    maktablar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1
    kochalar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 19
    mtm_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1

    # Демографик маълумотлар (Demographics)
    aholi_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 5351
    erkaklar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 2662
    ayollar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 2689
    yoshlar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 921 (18-30)
    voyaga_etmaganlar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 418 (0-18)
    oilalar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1415
    ijarada_yashovchilar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 6
    chetga_ketganlar_soni: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 118
    chetga_ketganlar_erkak: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 69
    chetga_ketganlar_ayol: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 47
    chetga_ketganlar_voyaga_etmagan: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 14

    # Ўзига хос хусусиятлари (Specific characteristics)
    toifa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Мураккаб тоифа"
    aholi_oqimi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Аҳоли оқими паст"
    murojaatlar_soni: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Мурожаатлар сони кам"

    # Flexible extra handwritten fields
    extra_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    mahalla: Mapped["Mahalla"] = relationship("Mahalla", lazy="selectin")

