import math
from datetime import date
from collections import defaultdict
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.mahallas.schemas.create import MahallaCreateSchema
from backend.mahallas.schemas.patch import MahallaUpdateSchema
from backend.mahallas.schemas.get import PaginatedMahallaSchema, MahallaDetailSchema
from backend.mahallas.schemas.stats import (
    MahallaStatsCreateOrUpdateSchema,
    MahallaStatsResponseSchema,
)
from backend.mahallas.schemas.radar import (
    SituationalRadarResponse,
    RadarMahallaItem,
    RadarSummary,
    RadarMahallaStats,
    RadarCoordinates,
    RadarMemberStatus,
    RadarCategoryBreakdown,
)
from db.models.mahalla import Mahalla
from db.models.mahalla_stats import MahallaStats
from db.models.user import User, UserRole, MAHALLA_SEVEN_ROLES
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.document import CheckInDocument, CheckInDocStatus

ROLE_LABELS: dict[str, str] = {
    "mahalla_raisi": "Mahalla raisi",
    "hokim_yordamchisi": "Hokim yordamchisi",
    "yoshlar_yetakchisi": "Yoshlar yetakchisi",
    "xotin_qizlar_faoli": "Xotin-qizlar faoli",
    "profilaktika_inspektori": "Profilaktika inspektori",
    "soliq_inspektori": "Soliq inspektori",
    "ijtimoiy_xodim": "Ijtimoiy xodim",
    "admin": "Administrator",
    "prokuror": "Prokuror",
}


class MahallaService:
    @staticmethod
    async def create_mahalla(data: MahallaCreateSchema, db: AsyncSession) -> Mahalla:
        existing = await db.execute(
            select(Mahalla).where(Mahalla.name == data.name.strip())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mahalla with name '{data.name.strip()}' already exists",
            )

        new_mahalla = Mahalla(name=data.name.strip())
        db.add(new_mahalla)
        await db.commit()
        await db.refresh(new_mahalla)
        return new_mahalla

    @staticmethod
    async def get_mahallas(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None,
        caller_role: Optional[UserRole] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> PaginatedMahallaSchema:
        query = select(Mahalla).options(selectinload(Mahalla.members)).where(Mahalla.is_active == True, Mahalla.id <= 39)
        count_query = select(func.count(Mahalla.id)).where(Mahalla.is_active == True, Mahalla.id <= 39)

        # If Rais, only show their own mahalla
        if caller_role == UserRole.MAHALLA_RAISI:
            if caller_mahalla_id is None:
                return PaginatedMahallaSchema(items=[], total=0, page=page, page_size=page_size)
            query = query.where(Mahalla.id == caller_mahalla_id)
            count_query = count_query.where(Mahalla.id == caller_mahalla_id)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(Mahalla.name.ilike(search_pattern))
            count_query = count_query.where(Mahalla.name.ilike(search_pattern))

        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(Mahalla.id.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        mahallas = result.scalars().all()

        return PaginatedMahallaSchema(
            items=[MahallaDetailSchema.model_validate(m) for m in mahallas],
            total=total,
            page=page,
            page_size=page_size,
        )

    @staticmethod
    async def get_mahalla_by_id(mahalla_id: int, db: AsyncSession) -> Mahalla:
        query = (
            select(Mahalla)
            .options(selectinload(Mahalla.members))
            .where(Mahalla.id == mahalla_id)
        )
        result = await db.execute(query)
        mahalla = result.scalar_one_or_none()
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {mahalla_id} not found",
            )
        return mahalla

    @staticmethod
    async def get_mahalla_members(
        mahalla_id: int,
        db: AsyncSession,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        caller_role: Optional[UserRole] = None,
        caller_mahalla_id: Optional[int] = None,
    ) -> List[User]:
        # 1. Verify Mahalla exists
        mahalla = await db.get(Mahalla, mahalla_id)
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {mahalla_id} not found",
            )

        # 2. RBAC check: Rais can only see members in their own Mahalla
        if caller_role == UserRole.MAHALLA_RAISI and caller_mahalla_id != mahalla_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rais can only view members of their own Mahalla",
            )

        # 3. Query members
        query = select(User).where(User.mahalla_id == mahalla_id)
        if role is not None:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)

        query = query.order_by(User.id.asc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_mahalla(
        mahalla_id: int, data: MahallaUpdateSchema, db: AsyncSession
    ) -> Mahalla:
        mahalla = await MahallaService.get_mahalla_by_id(mahalla_id, db)

        if data.name is not None:
            new_name = data.name.strip()
            existing = await db.execute(
                select(Mahalla).where(Mahalla.name == new_name, Mahalla.id != mahalla_id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mahalla with name '{new_name}' already exists",
                )
            mahalla.name = new_name

        if data.is_active is not None:
            mahalla.is_active = data.is_active

        await db.commit()
        await db.refresh(mahalla)
        return mahalla

    @staticmethod
    async def get_mahalla_stats(
        mahalla_id: int,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> MahallaStats:
        # Verify mahalla exists
        mahalla = await db.get(Mahalla, mahalla_id)
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {mahalla_id} not found",
            )

        # RBAC:
        if caller_role in [UserRole.MAHALLA_RAISI, *MAHALLA_SEVEN_ROLES]:
            if caller_mahalla_id != mahalla_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot view stats for another Mahalla",
                )

        stats = await db.scalar(
            select(MahallaStats).where(MahallaStats.mahalla_id == mahalla_id)
        )
        if not stats:
            # Create default empty stats row
            stats = MahallaStats(mahalla_id=mahalla_id, extra_data={})
            db.add(stats)
            await db.commit()
            await db.refresh(stats)

        return stats

    @staticmethod
    async def update_mahalla_stats(
        mahalla_id: int,
        data: MahallaStatsCreateOrUpdateSchema,
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> MahallaStats:
        # Verify mahalla exists
        mahalla = await db.get(Mahalla, mahalla_id)
        if not mahalla:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mahalla with id {mahalla_id} not found",
            )

        # RBAC: Only Admin, Prokuror, or Rais of this mahalla can update stats
        if caller_role not in [UserRole.ADMIN, UserRole.PROKUROR]:
            if caller_role == UserRole.MAHALLA_RAISI:
                if caller_mahalla_id != mahalla_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Rais can only update stats for their own Mahalla",
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only Admin, Prokuror, or Mahalla Raisi can update stats",
                )

        stats = await db.scalar(
            select(MahallaStats).where(MahallaStats.mahalla_id == mahalla_id)
        )
        if not stats:
            stats = MahallaStats(mahalla_id=mahalla_id)
            db.add(stats)

        # Update all fields if provided
        data_dict = data.model_dump(exclude_unset=True)
        for key, value in data_dict.items():
            setattr(stats, key, value)

        await db.commit()
        await db.refresh(stats)
        return stats

    @staticmethod
    async def get_situational_radar(
        caller_role: UserRole,
        caller_mahalla_id: Optional[int],
        db: AsyncSession,
    ) -> SituationalRadarResponse:
        # 1. Fetch Mahallas according to RBAC (Strictly 39 official entities)
        m_query = select(Mahalla).options(selectinload(Mahalla.members)).where(Mahalla.is_active == True, Mahalla.id <= 39)
        if caller_role in [UserRole.MAHALLA_RAISI, *MAHALLA_SEVEN_ROLES]:
            if caller_mahalla_id is not None:
                m_query = m_query.where(Mahalla.id == caller_mahalla_id)
            else:
                return SituationalRadarResponse(
                    summary=RadarSummary(),
                    mahallas=[],
                )

        mahalla_res = await db.execute(m_query.order_by(Mahalla.id.asc()))
        mahallas = list(mahalla_res.scalars().all())
        if not mahallas:
            return SituationalRadarResponse(
                summary=RadarSummary(),
                mahallas=[],
            )

        mahalla_ids = [m.id for m in mahallas]

        # 2. Fetch MahallaStats
        stats_query = select(MahallaStats).where(MahallaStats.mahalla_id.in_(mahalla_ids))
        stats_res = await db.execute(stats_query)
        stats_map = {s.mahalla_id: s for s in stats_res.scalars().all()}

        # 3. Fetch active Assignments with category and person
        asg_query = (
            select(PersonCategoryAssignment)
            .options(
                selectinload(PersonCategoryAssignment.category),
                selectinload(PersonCategoryAssignment.person),
            )
            .where(
                PersonCategoryAssignment.mahalla_id.in_(mahalla_ids),
                PersonCategoryAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        asg_res = await db.execute(asg_query)
        assignments = list(asg_res.scalars().all())

        asg_by_mahalla = defaultdict(list)
        for a in assignments:
            asg_by_mahalla[a.mahalla_id].append(a)

        # 4. Fetch CheckInDocuments
        doc_query = select(CheckInDocument).where(CheckInDocument.mahalla_id.in_(mahalla_ids))
        doc_res = await db.execute(doc_query)
        docs = list(doc_res.scalars().all())

        docs_by_mahalla = defaultdict(list)
        for d in docs:
            docs_by_mahalla[d.mahalla_id].append(d)

        today = date.today()
        radar_items: List[RadarMahallaItem] = []

        total_red = 0
        total_yellow = 0
        total_green = 0
        total_risk_score = 0
        total_overdue = 0
        total_active_sup = 0
        total_pending_docs = 0

        total_count = len(mahallas)

        for idx, m in enumerate(mahallas):
            m_stats = stats_map.get(m.id)
            m_asgs = asg_by_mahalla[m.id]
            m_docs = docs_by_mahalla[m.id]

            overdue_count = 0
            due_today = 0
            due_soon = 0
            person_ids = set()

            cat_counts = defaultdict(lambda: {"name": "", "total": 0, "overdue": 0})
            role_overdue = defaultdict(int)

            for a in m_asgs:
                person_ids.add(a.person_id)
                cat_name = a.category.name if a.category else "Maxsus toifa"
                cat_id = a.category_id
                cat_counts[cat_id]["name"] = cat_name
                cat_counts[cat_id]["total"] += 1

                if a.next_check_in_due:
                    diff = (a.next_check_in_due - today).days
                    if diff < 0:
                        overdue_count += 1
                        cat_counts[cat_id]["overdue"] += 1
                        roles = a.assigned_roles or (a.category.assigned_roles if a.category else [])
                        for r in roles:
                            role_overdue[r] += 1
                    elif diff == 0:
                        due_today += 1
                    elif 1 <= diff <= 3:
                        due_soon += 1

            total_active = len(m_asgs)
            total_persons = len(person_ids)

            pending_docs = sum(1 for d in m_docs if d.status == CheckInDocStatus.PENDING)
            rejected_docs = sum(1 for d in m_docs if d.status == CheckInDocStatus.REJECTED)
            approved_docs = sum(1 for d in m_docs if d.status == CheckInDocStatus.APPROVED)

            evaluated_tasks = approved_docs + overdue_count
            if evaluated_tasks > 0:
                compliance_rate = round((approved_docs / evaluated_tasks) * 100, 1)
            else:
                compliance_rate = 100.0 if overdue_count == 0 else 50.0

            active_members = [u for u in m.members if u.is_active]
            active_roles = {
                (u.role.value if hasattr(u.role, "value") else str(u.role)).lower()
                for u in active_members
            }
            missing_roles = [
                r.value for r in MAHALLA_SEVEN_ROLES
                if r.value.lower() not in active_roles
            ]

            members_list: List[RadarMemberStatus] = []
            for u in active_members:
                role_val = (u.role.value if hasattr(u.role, "value") else str(u.role)).lower()
                ov = role_overdue.get(role_val, 0)
                if ov > 2:
                    m_status = "critical"
                elif ov > 0:
                    m_status = "warning"
                else:
                    m_status = "ok"

                full_name = f"{u.first_name} {u.last_name}".strip()
                if not full_name:
                    full_name = u.login or "Xodim"

                members_list.append(
                    RadarMemberStatus(
                        id=u.id,
                        full_name=full_name,
                        role=role_val,
                        role_label=ROLE_LABELS.get(role_val, role_val),
                        phone=u.phone,
                        is_active=u.is_active,
                        status=m_status,
                        overdue_tasks=ov,
                    )
                )

            # Calculate risk score (0 - 100)
            score = 10
            score += overdue_count * 15
            score += rejected_docs * 5
            score += min(pending_docs * 3, 15)
            score += len(missing_roles) * 6
            score += int((100 - min(compliance_rate, 100)) * 0.25)

            toifa_str = m_stats.toifa if (m_stats and m_stats.toifa) else "Oddiy"
            if toifa_str and any(k in toifa_str.lower() for k in ["мураккаб", "qizil", "og'ir"]):
                score += 10

            risk_score = max(5, min(100, score))

            if risk_score >= 60 or overdue_count >= 3:
                risk_level = "red"
                total_red += 1
            elif risk_score >= 30 or overdue_count > 0 or due_today >= 2 or len(missing_roles) >= 2:
                risk_level = "yellow"
                total_yellow += 1
            else:
                risk_level = "green"
                total_green += 1

            if overdue_count > 2 or rejected_docs > 1:
                trend = "worsening"
            elif compliance_rate >= 80 and overdue_count == 0:
                trend = "improving"
            else:
                trend = "stable"

            alerts = []
            if overdue_count > 0:
                alerts.append(f"{overdue_count} ta nazorat topshirig'i muddati o'tgan")
            if missing_roles:
                first_missing = [ROLE_LABELS.get(r, r) for r in missing_roles[:2]]
                alerts.append(f"Yettilikda {len(missing_roles)} ta lavozim bo'sh: {', '.join(first_missing)}")
            if pending_docs > 2:
                alerts.append(f"{pending_docs} ta tekshiruv hujjati prokuror tasdiqlashini kutmoqda")
            if rejected_docs > 0:
                alerts.append(f"{rejected_docs} ta hisobot kamchilik sabab rad etilgan")
            if due_today > 0:
                alerts.append(f"Bugun {due_today} ta nazorat o'tkazilishi shart")

            if not alerts:
                alerts.append("Barcha profilaktik tadbirlar reja asosida o'tkazilmoqda")

            crit_cats: List[RadarCategoryBreakdown] = []
            sorted_cats = sorted(cat_counts.items(), key=lambda x: (x[1]["overdue"], x[1]["total"]), reverse=True)
            for cid, cinfo in sorted_cats[:4]:
                crit_cats.append(
                    RadarCategoryBreakdown(
                        category_id=cid,
                        name=cinfo["name"],
                        total_assigned=cinfo["total"],
                        overdue_count=cinfo["overdue"],
                    )
                )

            # Distances:
            # Red zone: inner circle 16% - 32%
            # Yellow zone: middle circle 38% - 58%
            # Green zone: outer circle 66% - 86%
            if risk_level == "red":
                dist = 16.0 + float(risk_score % 15)
            elif risk_level == "yellow":
                dist = 38.0 + float(risk_score % 18)
            else:
                dist = 66.0 + float(risk_score % 18)

            base_angle = float(idx * (360.0 / max(total_count, 1)))
            jitter = float(((m.id * 37) % 25) - 12.0)
            angle_deg = (base_angle + jitter) % 360.0
            angle_rad = math.radians(angle_deg)

            coord_x = round(50.0 + (dist * math.cos(angle_rad) * 0.46), 2)
            coord_y = round(50.0 + (dist * math.sin(angle_rad) * 0.46), 2)

            coord_x = max(6.0, min(94.0, coord_x))
            coord_y = max(6.0, min(94.0, coord_y))

            radar_items.append(
                RadarMahallaItem(
                    id=m.id,
                    name=m.name,
                    toifa=toifa_str,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    trend=trend,
                    stats=RadarMahallaStats(
                        overdue_count=overdue_count,
                        due_today=due_today,
                        due_soon=due_soon,
                        total_active=total_active,
                        total_persons=total_persons,
                        pending_documents=pending_docs,
                        rejected_documents=rejected_docs,
                        approved_documents=approved_docs,
                        compliance_rate=compliance_rate,
                        yettilik_active=len(active_members),
                        yettilik_total=7,
                    ),
                    missing_roles=missing_roles,
                    alerts=alerts,
                    critical_categories=crit_cats,
                    members=members_list,
                    coordinates=RadarCoordinates(
                        x=coord_x,
                        y=coord_y,
                        distance=round(dist, 1),
                        angle=round(angle_deg, 1),
                    ),
                )
            )

            total_risk_score += risk_score
            total_overdue += overdue_count
            total_active_sup += total_active
            total_pending_docs += pending_docs

        radar_items.sort(
            key=lambda item: (
                0 if item.risk_level == "red" else 1 if item.risk_level == "yellow" else 2,
                -item.risk_score,
            )
        )

        avg_score = round(total_risk_score / max(total_count, 1), 1)

        summary = RadarSummary(
            total_mahallas=total_count,
            red_count=total_red,
            yellow_count=total_yellow,
            green_count=total_green,
            average_risk_score=avg_score,
            critical_overdue_total=total_overdue,
            total_active_supervisions=total_active_sup,
            total_pending_documents=total_pending_docs,
        )

        return SituationalRadarResponse(
            summary=summary,
            mahallas=radar_items,
        )
