import datetime
import pytest
from httpx import AsyncClient
from db.models.mahalla import Mahalla
from db.models.category import Category
from db.models.person import Person
from db.models.user import UserRole


@pytest.mark.asyncio
async def test_create_person_by_prokuror(
    client: AsyncClient, prokuror_token: str, sample_mahalla: Mahalla
):
    res = await client.post(
        "/persons",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "full_name": "Мубараков Жамшид Курал ўғли",
            "birth_date": "2000-02-12",
            "mahalla_id": sample_mahalla.id,
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Мубараков Жамшид Курал ўғли"
    assert data["birth_date"] == "2000-02-12"
    assert data["mahalla_id"] == sample_mahalla.id


@pytest.mark.asyncio
async def test_create_person_forbidden_for_members(
    client: AsyncClient, inspector_token: str, sample_mahalla: Mahalla
):
    res = await client.post(
        "/persons",
        headers={"Authorization": f"Bearer {inspector_token}"},
        json={
            "full_name": "Test Person",
            "birth_date": "1995-05-15",
            "mahalla_id": sample_mahalla.id,
        },
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_assign_multiple_categories_with_different_frequencies(
    client: AsyncClient,
    prokuror_token: str,
    sample_person: Person,
    sample_category: Category,
    db_session,
):
    # Create second category (e.g. Probation)
    cat2 = Category(
        name="Пробация ҳисобидагилар рўйхати",
        assigned_roles=[UserRole.PROFILAKTIKA_INSPEKTORI.value],
        default_frequency_days=10,
        is_active=True,
    )
    db_session.add(cat2)
    await db_session.commit()
    await db_session.refresh(cat2)

    # Assign to first category with 5 days
    res1 = await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "category_id": sample_category.id,
            "frequency_days": 5,
        },
    )
    assert res1.status_code == 201
    assert res1.json()["frequency_days"] == 5

    # Assign to second category with 10 days
    res2 = await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "category_id": cat2.id,
            "frequency_days": 10,
        },
    )
    assert res2.status_code == 201
    assert res2.json()["frequency_days"] == 10

    # Person now has 2 assignments
    p_res = await client.get(
        f"/persons/{sample_person.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert p_res.status_code == 200
    assert len(p_res.json()["assignments"]) == 2


@pytest.mark.asyncio
async def test_duplicate_active_assignment_rejected(
    client: AsyncClient,
    prokuror_token: str,
    sample_person: Person,
    sample_category: Category,
):
    # First assignment
    res1 = await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"category_id": sample_category.id, "frequency_days": 5},
    )
    assert res1.status_code == 201

    # Second assignment to same active category -> 409
    res2 = await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"category_id": sample_category.id, "frequency_days": 7},
    )
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_rbac_person_visibility(
    client: AsyncClient,
    prokuror_token: str,
    rais_token: str,
    inspector_token: str,
    women_activist_token: str,
    sample_person: Person,
    sample_category: Category,
    db_session,
):
    # Assign sample_person to sample_category (assigned_roles = ["profilaktika_inspektori"])
    await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"category_id": sample_category.id, "frequency_days": 5},
    )

    # 1. Prokuror sees the person
    res_p = await client.get(
        "/persons", headers={"Authorization": f"Bearer {prokuror_token}"}
    )
    assert res_p.status_code == 200
    assert res_p.json()["total"] >= 1

    # 2. Rais sees the person (in own mahalla)
    res_r = await client.get(
        "/persons", headers={"Authorization": f"Bearer {rais_token}"}
    )
    assert res_r.status_code == 200
    assert res_r.json()["total"] >= 1

    # 3. Profilaktika inspector sees the assignment for their role
    res_i = await client.get(
        "/persons/assignments", headers={"Authorization": f"Bearer {inspector_token}"}
    )
    assert res_i.status_code == 200
    assert len(res_i.json()) >= 1

    # 4. Women activist has no assignments for her role on this person
    res_w = await client.get(
        "/persons/assignments", headers={"Authorization": f"Bearer {women_activist_token}"}
    )
    assert res_w.status_code == 200
    assert len(res_w.json()) == 0

