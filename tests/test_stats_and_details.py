import io
import datetime
import pytest
from httpx import AsyncClient

from db.models.mahalla import Mahalla
from db.models.user import User, UserRole
from db.models.category import Category
from db.models.person import Person
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus


@pytest.mark.asyncio
async def test_employee_photo_upload_and_career_details(
    client: AsyncClient,
    admin_token: str,
    inspector_user: User,
):
    # Upload photo for employee
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy avatar image")
    files = {"photo": ("avatar.jpg", fake_photo, "image/jpeg")}

    photo_res = await client.post(
        f"/users/{inspector_user.id}/photo",
        headers={"Authorization": f"Bearer {admin_token}"},
        files=files,
    )
    assert photo_res.status_code == 200
    assert "/uploads/photos/" in photo_res.json()["photo_url"]

    # Update career details (birth_date_text, appointed_date_text, specialization, previous_workplace)
    patch_res = await client.patch(
        f"/users/{inspector_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "birth_date_text": "1993 йил",
            "appointed_date_text": "2024 йил 20 декабр ойидан буён",
            "specialization": "Тарих",
            "previous_workplace": "Кинология",
        },
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["birth_date_text"] == "1993 йил"
    assert data["appointed_date_text"] == "2024 йил 20 декабр ойидан буён"
    assert data["specialization"] == "Тарих"
    assert data["previous_workplace"] == "Кинология"


@pytest.mark.asyncio
async def test_category_icon_upload_and_live_stats(
    client: AsyncClient,
    prokuror_token: str,
    sample_category: Category,
    sample_person: Person,
    sample_mahalla: Mahalla,
    db_session,
):
    # Upload icon for category
    fake_icon = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"dummy icon bytes")
    files = {"icon": ("icon.png", fake_icon, "image/png")}

    icon_res = await client.post(
        f"/categories/{sample_category.id}/icon",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        files=files,
    )
    assert icon_res.status_code == 200
    assert "/uploads/icons/" in icon_res.json()["icon_url"]

    # Assign sample_person to sample_category
    await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"category_id": sample_category.id, "frequency_days": 5},
    )

    # Fetch live category stats
    stats_res = await client.get(
        "/categories/stats",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert stats_res.status_code == 200
    items = stats_res.json()
    cat_stat = [c for c in items if c["id"] == sample_category.id][0]
    assert cat_stat["persons_count"] == 1
    assert cat_stat["active_assignments_count"] == 1
    assert "/uploads/icons/" in cat_stat["icon_url"]


@pytest.mark.asyncio
async def test_remaining_days_stats_and_separate_fetching(
    client: AsyncClient,
    prokuror_token: str,
    sample_person: Person,
    sample_category: Category,
    sample_mahalla: Mahalla,
    db_session,
):
    today = datetime.date.today()

    # Create assignment with exactly 5 days remaining
    a5 = PersonCategoryAssignment(
        person_id=sample_person.id,
        category_id=sample_category.id,
        mahalla_id=sample_mahalla.id,
        frequency_days=5,
        next_check_in_due=today + datetime.timedelta(days=5),
        status=AssignmentStatus.ACTIVE,
    )
    # Create another person and assignment with 4 days remaining
    p4 = Person(
        full_name="Исаков Атабек Махмуд ўғли",
        birth_date=datetime.date(2001, 1, 9),
        mahalla_id=sample_mahalla.id,
    )
    db_session.add_all([a5, p4])
    await db_session.commit()
    await db_session.refresh(p4)

    a4 = PersonCategoryAssignment(
        person_id=p4.id,
        category_id=sample_category.id,
        mahalla_id=sample_mahalla.id,
        frequency_days=4,
        next_check_in_due=today + datetime.timedelta(days=4),
        status=AssignmentStatus.ACTIVE,
    )
    db_session.add(a4)
    await db_session.commit()

    # 1. Request without payload: GET count of docs broken down by remaining days
    stats_res = await client.get(
        "/persons/assignments/stats/remaining-days",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_active"] >= 2
    # 5 days has 1
    assert stats["by_day"]["5"] >= 1
    # 4 days has 1
    assert stats["by_day"]["4"] >= 1

    # Check top KPI cards (Image red circle)
    assert "jami_hujjatlar" in stats
    assert "kiruvchi_hujjatlar" in stats
    assert "bajarilgan_hujjatlar" in stats
    assert "muddati_buzilib_bajarilgan" in stats
    assert "kech_qabul_qilingan" in stats
    assert "muddati_buzilgan_hujjatlar" in stats
    assert "total_documents" in stats
    assert "pending_documents" in stats
    assert "bugun" in stats
    assert "ertaga" in stats
    assert "indinga" in stats

    # 2. Separate fetching: fetch items with exactly 5 days remaining
    fetch_5 = await client.get(
        "/persons/assignments?days_remaining=5",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert fetch_5.status_code == 200
    items_5 = fetch_5.json()
    assert len(items_5) >= 1
    assert all(item["days_remaining"] == 5 for item in items_5)

    # 3. Separate fetching: fetch items with exactly 4 days remaining
    fetch_4 = await client.get(
        "/persons/assignments?days_remaining=4",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert fetch_4.status_code == 200
    items_4 = fetch_4.json()
    assert len(items_4) >= 1
    assert all(item["days_remaining"] == 4 for item in items_4)


@pytest.mark.asyncio
async def test_mahalla_stats_crud(
    client: AsyncClient,
    rais_token: str,
    sample_mahalla: Mahalla,
):
    # Put / update stats for mahalla (matching Image 3)
    put_res = await client.put(
        f"/mahallas/{sample_mahalla.id}/stats",
        headers={"Authorization": f"Bearer {rais_token}"},
        json={
            "maydoni": "141.45 га",
            "xonadonlar_soni": 1005,
            "savdo_dokonlari_soni": 6,
            "maktablar_soni": 1,
            "kochalar_soni": 19,
            "mtm_soni": 1,
            "aholi_soni": 5351,
            "erkaklar_soni": 2662,
            "ayollar_soni": 2689,
            "yoshlar_soni": 921,
            "voyaga_etmaganlar_soni": 418,
            "oilalar_soni": 1415,
            "ijarada_yashovchilar_soni": 6,
            "chetga_ketganlar_soni": 118,
            "toifa": "Мураккаб тоифа (2 йилдан бери яшил тоифада)",
            "aholi_oqimi": "Аҳоли оқими паст (кунлик ўртача 10-15 киши)",
            "murojaatlar_soni": "Мурожаатлар сони кам (ойлик ўртача 14-15 та)",
        },
    )
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["maydoni"] == "141.45 га"
    assert data["xonadonlar_soni"] == 1005
    assert data["aholi_soni"] == 5351
    assert data["toifa"] == "Мураккаб тоифа (2 йилдан бери яшил тоифада)"

    # Get stats
    get_res = await client.get(
        f"/mahallas/{sample_mahalla.id}/stats",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["aholi_soni"] == 5351

