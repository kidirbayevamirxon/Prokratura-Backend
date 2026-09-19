import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.files.service import FileService
from db.models.user import User
from db.models.category import Category
from db.models.assignment import PersonCategoryAssignment
from db.models.document import CheckInDocument


@pytest.mark.asyncio
async def test_file_upload_endpoint(client: AsyncClient, admin_token: str):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"file upload test content" * 10)
    files = {"file": ("test_avatar.jpg", fake_photo, "image/jpeg")}
    data = {"category": "photos"}

    response = await client.post(
        "/files/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files=files,
        data=data,
    )
    assert response.status_code == 201
    res_data = response.json()
    assert "/files/photos/" in res_data["file_url"]
    assert res_data["relative_path"].startswith("photos/")
    assert res_data["filename"].endswith(".jpg")
    assert res_data["size_bytes"] > 0

    # Test file retrieval through GET /files/{file_path}
    get_res = await client.get(f"/files/{res_data['relative_path']}")
    assert get_res.status_code == 200
    assert "image" in get_res.headers.get("content-type", "")
    assert len(get_res.content) == res_data["size_bytes"]


@pytest.mark.asyncio
async def test_file_security_traversal_and_404(client: AsyncClient):
    # Non-existent file
    res_404 = await client.get("/files/photos/2026/01/01/nonexistent.jpg")
    assert res_404.status_code == 404
    assert res_404.json()["detail"] == "File not found"

    # Directory traversal attempt
    with pytest.raises(Exception):
        FileService.resolve_safe_path("../../../../etc/passwd")

    res_traversal = await client.get("/files/..%2f..%2f..%2fetc/passwd")
    assert res_traversal.status_code in [400, 404]


@pytest.mark.asyncio
async def test_file_deleted_when_document_deleted_from_db(
    client: AsyncClient,
    inspector_token: str,
    admin_token: str,
    sample_assignment: PersonCategoryAssignment,
    db_session: AsyncSession,
):
    # 1. Upload a document with photo and pdf
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"document photo proof bytes" * 20)
    fake_pdf = io.BytesIO(b"%PDF-1.4 " + b"document pdf proof bytes" * 20)
    files = {
        "photo": ("visit_proof.jpg", fake_photo, "image/jpeg"),
        "pdf": ("act.pdf", fake_pdf, "application/pdf"),
    }
    data = {
        "assignment_id": str(sample_assignment.id),
        "notes": "Test document for file deletion",
    }

    doc_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        files=files,
        data=data,
    )
    assert doc_res.status_code == 201
    doc_data = doc_res.json()
    doc_id = doc_data["id"]

    photo_path = FileService.resolve_safe_path(doc_data["photo_url"])
    pdf_path = FileService.resolve_safe_path(doc_data["pdf_url"])

    # Verify physical files exist on disk
    assert photo_path.exists(), "Photo file should exist on disk after upload"
    assert pdf_path.exists(), "PDF file should exist on disk after upload"

    # 2. Delete document via API (which deletes DB object)
    del_res = await client.delete(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_res.status_code == 200

    # 3. Verify physical files are automatically deleted from disk
    assert not photo_path.exists(), "Photo file should be deleted from disk when document is deleted from DB"
    assert not pdf_path.exists(), "PDF file should be deleted from disk when document is deleted from DB"


@pytest.mark.asyncio
async def test_file_deleted_when_user_deleted_from_db(
    client: AsyncClient,
    admin_token: str,
    inspector_user: User,
    db_session: AsyncSession,
):
    # 1. Upload photo for user
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"user avatar bytes" * 20)
    files = {"photo": ("avatar.jpg", fake_photo, "image/jpeg")}

    photo_res = await client.post(
        f"/users/{inspector_user.id}/photo",
        headers={"Authorization": f"Bearer {admin_token}"},
        files=files,
    )
    assert photo_res.status_code == 200
    photo_url = photo_res.json()["photo_url"]
    photo_path = FileService.resolve_safe_path(photo_url)
    assert photo_path.exists(), "User photo should exist on disk"

    # 2. Delete user from DB session
    user_in_db = await db_session.get(User, inspector_user.id)
    assert user_in_db is not None
    await db_session.delete(user_in_db)
    await db_session.commit()

    # 3. Verify photo is deleted from disk
    assert not photo_path.exists(), "User photo should be deleted from disk when user is deleted from DB"


@pytest.mark.asyncio
async def test_file_deleted_when_category_deleted_from_db(
    client: AsyncClient,
    prokuror_token: str,
    sample_category: Category,
    db_session: AsyncSession,
):
    # 1. Upload icon for category
    fake_icon = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"category icon bytes" * 20)
    files = {"icon": ("cat_icon.png", fake_icon, "image/png")}

    icon_res = await client.post(
        f"/categories/{sample_category.id}/icon",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        files=files,
    )
    assert icon_res.status_code == 200
    icon_url = icon_res.json()["icon_url"]
    icon_path = FileService.resolve_safe_path(icon_url)
    assert icon_path.exists(), "Category icon should exist on disk"

    # 2. Delete category from DB
    del_res = await client.delete(
        f"/categories/{sample_category.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert del_res.status_code == 200

    # 3. Verify icon is deleted from disk
    assert not icon_path.exists(), "Category icon should be deleted from disk when category is deleted from DB"


@pytest.mark.asyncio
async def test_old_file_deleted_when_photo_replaced(
    client: AsyncClient,
    admin_token: str,
    inspector_user: User,
):
    # 1. Upload first photo
    photo_1 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"first photo content" * 20)
    res_1 = await client.post(
        f"/users/{inspector_user.id}/photo",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"photo": ("first.jpg", photo_1, "image/jpeg")},
    )
    assert res_1.status_code == 200
    path_1 = FileService.resolve_safe_path(res_1.json()["photo_url"])
    assert path_1.exists()

    # 2. Upload replacement photo
    photo_2 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"replacement photo content" * 20)
    res_2 = await client.post(
        f"/users/{inspector_user.id}/photo",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"photo": ("second.jpg", photo_2, "image/jpeg")},
    )
    assert res_2.status_code == 200
    path_2 = FileService.resolve_safe_path(res_2.json()["photo_url"])
    assert path_2.exists()

    # 3. Verify first photo was cleaned up from disk, and second photo exists
    assert not path_1.exists(), "Old photo must be deleted from disk when replaced"
    assert path_2.exists(), "New photo must exist on disk"

