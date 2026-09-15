import pytest
from httpx import AsyncClient
from db.models.user import UserRole


@pytest.mark.asyncio
async def test_register_by_admin(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/auth/register",
        json={
            "first_name": "Sardor",
            "last_name": "Rahimov",
            "phone": "+998901234567",
            "login": "prokuror_sardor",
            "password": "strongPassword123",
            "role": UserRole.PROKUROR.value,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == UserRole.PROKUROR.value


@pytest.mark.asyncio
async def test_register_without_admin_fails(client: AsyncClient, prokuror_token: str):
    response = await client.post(
        "/auth/register",
        json={
            "first_name": "Hacker",
            "last_name": "Attempt",
            "phone": "+998901234568",
            "login": "hacker_user",
            "password": "strongPassword123",
        },
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_public_fails(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={
            "first_name": "Public",
            "last_name": "User",
            "phone": "+998901234569",
            "password": "strongPassword123",
        },
    )
    assert response.status_code == 401 or response.status_code == 403


@pytest.mark.asyncio
async def test_login_success_with_login(client: AsyncClient, prokuror_user):
    response = await client.post(
        "/auth/login",
        json={
            "login": prokuror_user.login,
            "password": "prokuror123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == UserRole.PROKUROR.value


@pytest.mark.asyncio
async def test_login_success_with_phone(client: AsyncClient, prokuror_user):
    response = await client.post(
        "/auth/login",
        json={
            "login": prokuror_user.phone,
            "password": "prokuror123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, prokuror_user):
    response = await client.post(
        "/auth/login",
        json={
            "login": prokuror_user.login,
            "password": "wrong_password",
        },
    )
    assert response.status_code == 401
    assert "Invalid login or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, prokuror_user):
    login_res = await client.post(
        "/auth/login",
        json={"login": prokuror_user.login, "password": "prokuror123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    refresh_res = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, prokuror_token: str, prokuror_user):
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == prokuror_user.id
    assert data["phone"] == prokuror_user.phone
    assert data["role"] == UserRole.PROKUROR.value
