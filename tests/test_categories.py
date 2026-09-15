import pytest
from httpx import AsyncClient
from db.models.user import UserRole
from db.models.category import Category


@pytest.mark.asyncio
async def test_create_category_by_prokuror(client: AsyncClient, prokuror_token: str):
    response = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "name": "Боқувчиси бўлмаган ёлғиз аёллар рўйхати",
            "description": "Single women without breadwinner",
            "assigned_roles": [UserRole.IJTIMOIY_XODIM.value, UserRole.XOTIN_QIZLAR_FAOLI.value],
            "default_frequency_days": 15,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Боқувчиси бўлмаган ёлғиз аёллар рўйхати"
    assert len(data["assigned_roles"]) == 2
    assert UserRole.IJTIMOIY_XODIM.value in data["assigned_roles"]
    assert data["default_frequency_days"] == 15


@pytest.mark.asyncio
async def test_create_category_forbidden_for_rais_and_members(
    client: AsyncClient, rais_token: str, inspector_token: str
):
    # Rais attempt
    res1 = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {rais_token}"},
        json={"name": "Test Category", "assigned_roles": []},
    )
    assert res1.status_code == 403

    # Inspector attempt
    res2 = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {inspector_token}"},
        json={"name": "Test Category", "assigned_roles": []},
    )
    assert res2.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_category_name_conflict(
    client: AsyncClient, prokuror_token: str, sample_category: Category
):
    response = await client.post(
        "/categories",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "name": sample_category.name,
            "assigned_roles": ["profilaktika_inspektori"],
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_categories_and_search(
    client: AsyncClient, prokuror_token: str, sample_category: Category
):
    # Get list
    res = await client.get(
        "/categories",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(c["name"] == sample_category.name for c in data["items"])

    # Search
    search_res = await client.get(
        "/categories?search=Проф",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert search_res.status_code == 200
    assert len(search_res.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_update_category(
    client: AsyncClient, prokuror_token: str, sample_category: Category
):
    res = await client.patch(
        f"/categories/{sample_category.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "default_frequency_days": 10,
            "description": "Updated description",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["default_frequency_days"] == 10
    assert data["description"] == "Updated description"

