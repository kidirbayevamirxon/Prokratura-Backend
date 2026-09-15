import pytest
from httpx import AsyncClient
from db.models.user import UserRole


@pytest.mark.asyncio
async def test_admin_creates_prokuror_and_enforces_single_prokuror(
    client: AsyncClient, admin_token: str
):
    # Admin creates Prokuror (no mahalla_id allowed)
    response = await client.post(
        "/users",
        json={
            "first_name": "Azamat",
            "last_name": "Qosimov",
            "phone": "+998901239999",
            "login": "prokuror_azamat",
            "password": "Password123",
            "role": UserRole.PROKUROR.value,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == UserRole.PROKUROR.value
    assert response.json()["mahalla_id"] is None

    # Admin attempts to create a SECOND active Prokuror -> 409 Conflict
    second_res = await client.post(
        "/users",
        json={
            "first_name": "Second",
            "last_name": "Prokuror",
            "phone": "+998901239998",
            "login": "second_prokuror",
            "password": "Password123",
            "role": UserRole.PROKUROR.value,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second_res.status_code == 409
    assert "Only one active Prokuror is allowed" in second_res.json()["detail"]


@pytest.mark.asyncio
async def test_prokuror_cannot_create_prokuror_or_admin(
    client: AsyncClient, prokuror_token: str
):
    response = await client.post(
        "/users",
        json={
            "first_name": "Illegal",
            "last_name": "Admin",
            "phone": "+998901238888",
            "role": UserRole.ADMIN.value,
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_prokuror_adds_seven_officials_with_required_mahalla_id(
    client: AsyncClient, prokuror_token: str, sample_mahalla
):
    # Attempting to add a Rais without mahalla_id -> Rejected by validation
    invalid_res = await client.post(
        "/users",
        json={
            "first_name": "Botir",
            "last_name": "Zokirov",
            "phone": "+998901237777",
            "role": UserRole.MAHALLA_RAISI.value,
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert invalid_res.status_code == 422

    # Prokuror creates Rais with valid mahalla_id
    rais_res = await client.post(
        "/users",
        json={
            "first_name": "Botir",
            "last_name": "Zokirov",
            "phone": "+998901237777",
            "role": UserRole.MAHALLA_RAISI.value,
            "mahalla_id": sample_mahalla.id,
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert rais_res.status_code == 201
    assert rais_res.json()["mahalla_id"] == sample_mahalla.id

    # Enforcing 1 Rais per Mahalla: Prokuror assigns a NEW Rais to the same mahalla
    new_rais_res = await client.post(
        "/users",
        json={
            "first_name": "Anvar",
            "last_name": "Jalilov",
            "phone": "+998901237776",
            "role": UserRole.MAHALLA_RAISI.value,
            "mahalla_id": sample_mahalla.id,
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert new_rais_res.status_code == 201
    new_rais_id = new_rais_res.json()["id"]

    # Verify old Rais (Botir) was unlinked / displaced
    old_rais_id = rais_res.json()["id"]
    check_old = await client.get(
        f"/users/{old_rais_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert check_old.json()["mahalla_id"] is None


@pytest.mark.asyncio
async def test_rais_can_see_only_members_in_own_mahalla(
    client: AsyncClient, admin_token: str, rais_token: str, sample_mahalla
):
    # Rais queries users list: only users in sample_mahalla are returned
    response = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert response.status_code == 200
    for u in response.json()["items"]:
        assert u["mahalla_id"] == sample_mahalla.id


@pytest.mark.asyncio
async def test_other_members_cannot_browse_users(
    client: AsyncClient, member_token: str
):
    response = await client.get(
        "/users",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rais_cannot_change_people(
    client: AsyncClient, rais_token: str, member_user
):
    # Rais cannot modify member
    response = await client.patch(
        f"/users/{member_user.id}",
        json={"first_name": "HackedName"},
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_three_separate_search_queries(
    client: AsyncClient, prokuror_token: str, sample_mahalla
):
    # Create test user
    await client.post(
        "/users",
        json={
            "first_name": "Nodirbek",
            "last_name": "Aliyev",
            "phone": "+998939876543",
            "login": "nodir_soliq_99",
            "role": UserRole.SOLIQ_INSPEKTORI.value,
            "mahalla_id": sample_mahalla.id,
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )

    # 1. Search by name
    res_name = await client.get(
        "/users?name=Nodirbek",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_name.status_code == 200
    assert any(u["first_name"] == "Nodirbek" for u in res_name.json()["items"])

    # 2. Search by phone
    res_phone = await client.get(
        "/users?phone=9876543",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_phone.status_code == 200
    assert any(u["phone"] == "+998939876543" for u in res_phone.json()["items"])

    # 3. Search by login
    res_login = await client.get(
        "/users?login=nodir_soliq",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_login.status_code == 200
    assert any(u["login"] == "nodir_soliq_99" for u in res_login.json()["items"])


@pytest.mark.asyncio
async def test_soft_deactivation_via_patch_and_no_delete(
    client: AsyncClient, prokuror_token: str, member_user
):
    # Soft deactivation
    patch_res = await client.patch(
        f"/users/{member_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    # Verify DELETE method returns 405 Method Not Allowed (endpoint does not exist)
    del_res = await client.delete(
        f"/users/{member_user.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert del_res.status_code == 405
