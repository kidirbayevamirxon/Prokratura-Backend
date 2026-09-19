import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_creates_mahalla(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/mahallas",
        json={"name": "Oqtepa MFY"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Oqtepa MFY"
    assert data["is_active"] is True
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_prokuror_cannot_create_or_update_mahalla(
    client: AsyncClient, prokuror_token: str, sample_mahalla
):
    # Prokuror cannot create mahalla
    create_res = await client.post(
        "/mahallas",
        json={"name": "Illegal Mahalla"},
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert create_res.status_code == 403

    # Prokuror cannot patch mahalla
    patch_res = await client.patch(
        f"/mahallas/{sample_mahalla.id}",
        json={"name": "Renamed Mahalla"},
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert patch_res.status_code == 403


@pytest.mark.asyncio
async def test_prokuror_can_get_mahallas_and_search(
    client: AsyncClient, admin_token: str, prokuror_token: str
):
    # Admin creates mahallas
    await client.post(
        "/mahallas",
        json={"name": "Chilonzor MFY"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    await client.post(
        "/mahallas",
        json={"name": "Navro'z MFY"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Prokuror can get and search mahallas
    response = await client.get(
        "/mahallas?search=Chilonzor",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(item["name"] == "Chilonzor MFY" for item in data["items"])


@pytest.mark.asyncio
async def test_rais_can_see_only_own_mahalla(
    client: AsyncClient, admin_token: str, rais_token: str, sample_mahalla
):
    # Create another mahalla
    other_m_res = await client.post(
        "/mahallas",
        json={"name": "Different MFY"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    other_m_id = other_m_res.json()["id"]

    # Rais can view own mahalla
    own_res = await client.get(
        f"/mahallas/{sample_mahalla.id}",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert own_res.status_code == 200
    assert own_res.json()["id"] == sample_mahalla.id

    # Rais CANNOT view different mahalla
    other_res = await client.get(
        f"/mahallas/{other_m_id}",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert other_res.status_code == 403


@pytest.mark.asyncio
async def test_other_members_cannot_view_mahallas(
    client: AsyncClient, member_token: str, sample_mahalla
):
    # Member from the other 6 roles cannot access mahallas list or detail
    list_res = await client.get(
        "/mahallas",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert list_res.status_code == 403

    detail_res = await client.get(
        f"/mahallas/{sample_mahalla.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert detail_res.status_code == 403


@pytest.mark.asyncio
async def test_admin_updates_mahalla_and_soft_deactivates(
    client: AsyncClient, admin_token: str, sample_mahalla
):
    # Admin updates name and is_active
    update_res = await client.patch(
        f"/mahallas/{sample_mahalla.id}",
        json={"name": "Oqtepa Yangi MFY", "is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Oqtepa Yangi MFY"
    assert update_res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_get_mahalla_members_by_prokuror_and_rais(
    client: AsyncClient,
    prokuror_token: str,
    rais_token: str,
    sample_mahalla,
    rais_user,
    member_user,
):
    # Prokuror queries mahalla members
    res = await client.get(
        f"/mahallas/{sample_mahalla.id}/members",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res.status_code == 200
    members = res.json()
    assert len(members) >= 2
    member_roles = [m["role"] for m in members]
    assert "mahalla_raisi" in member_roles
    assert "yoshlar_yetakchisi" in member_roles

    # Rais queries own mahalla members
    rais_res = await client.get(
        f"/mahallas/{sample_mahalla.id}/members",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert rais_res.status_code == 200
    assert len(rais_res.json()) >= 2


@pytest.mark.asyncio
async def test_get_mahalla_members_rbac_and_filters(
    client: AsyncClient,
    admin_token: str,
    prokuror_token: str,
    rais_token: str,
    sample_mahalla,
    rais_user,
    member_user,
):
    # Create another mahalla
    other_m_res = await client.post(
        "/mahallas",
        json={"name": "Bog'ishamol MFY"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    other_m_id = other_m_res.json()["id"]

    # Rais cannot query another mahalla's members
    forbidden_res = await client.get(
        f"/mahallas/{other_m_id}/members",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert forbidden_res.status_code == 403

    # Filter by role
    filtered_res = await client.get(
        f"/mahallas/{sample_mahalla.id}/members?role=yoshlar_yetakchisi",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert filtered_res.status_code == 200
    filtered_members = filtered_res.json()
    assert len(filtered_members) == 1
    assert filtered_members[0]["role"] == "yoshlar_yetakchisi"
    assert filtered_members[0]["id"] == member_user.id

    # Non-existent mahalla returns 404
    not_found_res = await client.get(
        "/mahallas/999999/members",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert not_found_res.status_code == 404
