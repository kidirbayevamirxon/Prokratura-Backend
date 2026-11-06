import math
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class RadarCategoryBreakdown(BaseModel):
    category_id: int
    name: str
    total_assigned: int
    overdue_count: int


class RadarMemberStatus(BaseModel):
    id: int
    full_name: str
    role: str
    role_label: str
    phone: Optional[str] = None
    is_active: bool
    status: str  # "ok", "warning", "critical"
    overdue_tasks: int = 0


class RadarCoordinates(BaseModel):
    x: float  # 0 - 100%
    y: float  # 0 - 100%
    distance: float  # Distance from center 0 - 100
    angle: float  # Angle in degrees 0 - 360


class RadarMahallaStats(BaseModel):
    overdue_count: int = 0
    due_today: int = 0
    due_soon: int = 0
    total_active: int = 0
    total_persons: int = 0
    pending_documents: int = 0
    rejected_documents: int = 0
    approved_documents: int = 0
    compliance_rate: float = 100.0
    yettilik_active: int = 0
    yettilik_total: int = 7


class RadarMahallaItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    toifa: Optional[str] = "Oddiy"
    risk_level: str  # "red" | "yellow" | "green"
    risk_score: int  # 0 to 100
    trend: str  # "worsening" | "stable" | "improving"
    stats: RadarMahallaStats
    missing_roles: List[str] = []
    alerts: List[str] = []
    critical_categories: List[RadarCategoryBreakdown] = []
    members: List[RadarMemberStatus] = []
    coordinates: RadarCoordinates


class RadarSummary(BaseModel):
    total_mahallas: int = 0
    red_count: int = 0
    yellow_count: int = 0
    green_count: int = 0
    average_risk_score: float = 0.0
    critical_overdue_total: int = 0
    total_active_supervisions: int = 0
    total_pending_documents: int = 0


class SituationalRadarResponse(BaseModel):
    summary: RadarSummary
    mahallas: List[RadarMahallaItem]

