from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class MahallaStatsCreateOrUpdateSchema(BaseModel):
    # Инфратузилма объектлари (Infrastructure)
    maydoni: Optional[str] = None  # e.g. "141.45 га"
    xonadonlar_soni: Optional[int] = None  # e.g. 1005
    savdo_dokonlari_soni: Optional[int] = None  # e.g. 6
    maktablar_soni: Optional[int] = None  # e.g. 1
    kochalar_soni: Optional[int] = None  # e.g. 19
    mtm_soni: Optional[int] = None  # e.g. 1

    # Демографик маълумотлар (Demographics)
    aholi_soni: Optional[int] = None  # e.g. 5351
    erkaklar_soni: Optional[int] = None  # e.g. 2662
    ayollar_soni: Optional[int] = None  # e.g. 2689
    yoshlar_soni: Optional[int] = None  # e.g. 921
    voyaga_etmaganlar_soni: Optional[int] = None  # e.g. 418
    oilalar_soni: Optional[int] = None  # e.g. 1415
    ijarada_yashovchilar_soni: Optional[int] = None  # e.g. 6
    chetga_ketganlar_soni: Optional[int] = None  # e.g. 118
    chetga_ketganlar_erkak: Optional[int] = None  # e.g. 69
    chetga_ketganlar_ayol: Optional[int] = None  # e.g. 47
    chetga_ketganlar_voyaga_etmagan: Optional[int] = None  # e.g. 14

    # Ўзига хос хусусиятлари (Specific characteristics)
    toifa: Optional[str] = None  # e.g. "Мураккаб тоифа (2 йилдан бери яшил тоифада)"
    aholi_oqimi: Optional[str] = None  # e.g. "Аҳоли оқими паст (кунлик ўртача 10-15 киши)"
    murojaatlar_soni: Optional[str] = None  # e.g. "Мурожаатлар сони кам (ойлик ўртача 14-15 та, йиллик 155-160 та)"

    # Additional handwritten indicators
    extra_data: Optional[Dict[str, Any]] = None


class MahallaStatsResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mahalla_id: int
    maydoni: Optional[str] = None
    xonadonlar_soni: Optional[int] = None
    savdo_dokonlari_soni: Optional[int] = None
    maktablar_soni: Optional[int] = None
    kochalar_soni: Optional[int] = None
    mtm_soni: Optional[int] = None
    aholi_soni: Optional[int] = None
    erkaklar_soni: Optional[int] = None
    ayollar_soni: Optional[int] = None
    yoshlar_soni: Optional[int] = None
    voyaga_etmaganlar_soni: Optional[int] = None
    oilalar_soni: Optional[int] = None
    ijarada_yashovchilar_soni: Optional[int] = None
    chetga_ketganlar_soni: Optional[int] = None
    chetga_ketganlar_erkak: Optional[int] = None
    chetga_ketganlar_ayol: Optional[int] = None
    chetga_ketganlar_voyaga_etmagan: Optional[int] = None
    toifa: Optional[str] = None
    aholi_oqimi: Optional[str] = None
    murojaatlar_soni: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    updated_at: datetime

