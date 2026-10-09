import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from db.models.user import User, UserRole
from db.models.category import Category
from db.models.person import Person
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from backend.files.service import FileService


@pytest.mark.asyncio
async def test_member_cannot_elevate_role_to_admin(
    client: AsyncClient, member_user: User, member_token: str
):
    """Verify that a regular Mahalla official cannot elevate their own role to Admin."""
    res = await client.patch(
        f"/users/{member_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"role": "admin"},
    )
    assert res.status_code == 403
    assert "Mahalla officials cannot change user roles" in res.json()["detail"]


@pytest.mark.asyncio
async def test_member_cannot_elevate_role_to_prokuror(
    client: AsyncClient, member_user: User, member_token: str
):
    """Verify that a regular Mahalla official cannot elevate their own role to Prokuror."""
    res = await client.patch(
        f"/users/{member_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"role": "prokuror"},
    )
    assert res.status_code == 403
    assert "Mahalla officials cannot change user roles" in res.json()["detail"]


@pytest.mark.asyncio
async def test_member_cannot_change_active_status_or_mahalla(
    client: AsyncClient, member_user: User, member_token: str
):
    """Verify that a regular Mahalla official cannot modify their active status or mahalla assignment."""
    res_status = await client.patch(
        f"/users/{member_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"is_active": False},
    )
    assert res_status.status_code == 403
    assert "cannot change active status" in res_status.json()["detail"]

    res_mahalla = await client.patch(
        f"/users/{member_user.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"mahalla_id": 999},
    )
    assert res_mahalla.status_code == 403
    assert "cannot change mahalla assignment" in res_mahalla.json()["detail"]


@pytest.mark.asyncio
async def test_assign_category_without_frequency_days_uses_default(
    client: AsyncClient,
    prokuror_token: str,
    sample_person: Person,
    sample_category: Category,
):
    """Verify assign_category does not crash with NotNullViolationError when frequency_days is omitted."""
    res = await client.post(
        f"/persons/{sample_person.id}/assign-category",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"category_id": sample_category.id},
    )
    assert res.status_code == 201
    assignment = res.json()
    assert assignment["frequency_days"] == sample_category.default_frequency_days
    assert assignment["next_check_in_due"] is not None


def test_path_traversal_is_relative_to():
    """Verify resolve_safe_path blocks path traversal and sibling directory attacks."""
    with pytest.raises(HTTPException) as exc_info:
        FileService.resolve_safe_path("../uploads_backup/secret.txt")
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info2:
        FileService.resolve_safe_path("../../etc/passwd")
    assert exc_info2.value.status_code == 400
