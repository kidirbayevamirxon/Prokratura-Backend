import io
import datetime
import pytest
from httpx import AsyncClient
from db.models.assignment import PersonCategoryAssignment, AssignmentStatus
from db.models.document import CheckInDocType, CheckInDocStatus
from db.models.mahalla import Mahalla
from db.models.user import User, UserRole
from backend.auth.service import AuthServices


@pytest.mark.asyncio
async def test_upload_document_success(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo content" * 50)
    fake_pdf = io.BytesIO(b"%PDF-1.4 " + b"dummy pdf content" * 50)

    files = {
        "photo": ("visit_photo.jpg", fake_photo, "image/jpeg"),
        "pdf": ("dalolatnoma.pdf", fake_pdf, "application/pdf"),
    }
    data = {
        "assignment_id": str(sample_assignment.id),
        "check_in_date": str(datetime.date.today()),
        "doc_type": "regular",
        "notes": "Fuqaro bilan profilaktik suhbat o'tkazildi",
    }

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["status"] == "pending"
    assert res_data["assignment_id"] == sample_assignment.id
    assert "/files/photos/" in res_data["photo_url"]
    assert "/files/documents/" in res_data["pdf_url"]
    assert res_data["notes"] == "Fuqaro bilan profilaktik suhbat o'tkazildi"


@pytest.mark.asyncio
async def test_photo_file_size_limit(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    # Over 5 MB photo
    large_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"X" * (5 * 1024 * 1024 + 100))
    files = {
        "photo": ("large_photo.jpg", large_photo, "image/jpeg"),
    }
    data = {
        "assignment_id": str(sample_assignment.id),
    }

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_pdf_file_size_limit(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    valid_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    large_pdf = io.BytesIO(b"%PDF-1.4 " + b"X" * (10 * 1024 * 1024 + 100))
    files = {
        "photo": ("photo.jpg", valid_photo, "image/jpeg"),
        "pdf": ("large.pdf", large_pdf, "application/pdf"),
    }
    data = {
        "assignment_id": str(sample_assignment.id),
    }

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_forbidden_for_unassigned_worker_role(
    client: AsyncClient,
    women_activist_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    data = {"assignment_id": str(sample_assignment.id)}

    # Women activist should not be able to upload for a profilaktika_inspektori-assigned category
    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {women_activist_token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_upload_forbidden_for_worker_from_different_mahalla(
    client: AsyncClient,
    db_session,
    sample_assignment: PersonCategoryAssignment,
):
    # Worker in another mahalla
    other_mahalla = Mahalla(name="Boshqa MFY", is_active=True)
    db_session.add(other_mahalla)
    await db_session.commit()
    await db_session.refresh(other_mahalla)

    foreign_inspector = User(
        first_name="Foreign",
        last_name="Inspector",
        phone="+998907776655",
        login="foreign_inspector",
        password=AuthServices.hash_password("pass123"),
        role=UserRole.PROFILAKTIKA_INSPEKTORI,
        mahalla_id=other_mahalla.id,
        is_active=True,
    )
    db_session.add(foreign_inspector)
    await db_session.commit()
    await db_session.refresh(foreign_inspector)

    token = AuthServices.issue_tokens(foreign_inspector).access_token

    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    data = {"assignment_id": str(sample_assignment.id)}

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_prokuror_rejection_requires_reason(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    # Upload doc
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id)},
        files=files,
    )
    doc_id = upload_res.json()["id"]

    # Reject without reason -> 422
    rej_fail = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "rejected", "rejection_reason": ""},
    )
    assert rej_fail.status_code == 422

    # Reject with reason -> 200
    rej_ok = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={
            "status": "rejected",
            "rejection_reason": "Rasm xira, shaxsning yuzi ko'rinmayapti. Qayta yuklang.",
        },
    )
    assert rej_ok.status_code == 200
    assert rej_ok.json()["status"] == "rejected"
    assert rej_ok.json()["rejection_reason"] == "Rasm xira, shaxsning yuzi ko'rinmayapti. Qayta yuklang."


@pytest.mark.asyncio
async def test_prokuror_approval_advances_frequency(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    today = datetime.date.today()
    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(today),
        },
        files=files,
    )
    doc_id = upload_res.json()["id"]

    # Prokuror approves
    app_res = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Verify assignment next_check_in_due advanced by 5 days
    ass_res = await client.get(
        f"/persons/assignments?status_filter=active",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = [a for a in ass_res.json() if a["id"] == sample_assignment.id][0]
    expected_due = str(today + datetime.timedelta(days=5))
    assert assignment["next_check_in_due"] == expected_due


@pytest.mark.asyncio
async def test_removal_request_flow(
    client: AsyncClient,
    prokuror_token: str,
    rais_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    # Rais submits removal request
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    files = {"photo": ("final_photo.jpg", fake_photo, "image/jpeg")}
    data = {
        "assignment_id": str(sample_assignment.id),
        "doc_type": "removal_request",
        "notes": "Fuqaro to'liq tuzalish yo'liga o'tdi, hisobdan chiqarish taklif etiladi.",
    }

    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {rais_token}"},
        data=data,
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]
    assert upload_res.json()["doc_type"] == "removal_request"

    # Prokuror approves removal
    app_res = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved"},
    )
    assert app_res.status_code == 200

    # Verify assignment status is now REMOVED
    ass_res = await client.get(
        f"/persons/assignments?status_filter=removed",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    removed_ids = [a["id"] for a in ass_res.json()]
    assert sample_assignment.id in removed_ids


@pytest.mark.asyncio
async def test_history_and_visibility_for_rais_and_prokuror(
    client: AsyncClient,
    prokuror_token: str,
    rais_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id)},
        files=files,
    )

    # Prokuror sees all documents in history
    p_docs = await client.get(
        "/documents", headers={"Authorization": f"Bearer {prokuror_token}"}
    )
    assert p_docs.status_code == 200
    assert p_docs.json()["total"] >= 1

    # Rais sees all documents in their own mahalla
    r_docs = await client.get(
        "/documents", headers={"Authorization": f"Bearer {rais_token}"}
    )
    assert r_docs.status_code == 200
    assert r_docs.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_documents_filter_by_remaining_days(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
    sample_category,
    sample_mahalla,
    db_session,
):
    today = datetime.date.today()
    sample_assignment.next_check_in_due = today + datetime.timedelta(days=5)
    await db_session.commit()

    # Upload document for sample_assignment (has 5 days remaining)
    fake_photo1 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo1")
    res1 = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id)},
        files={"photo": ("doc1.jpg", fake_photo1, "image/jpeg")},
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["id"]

    # Create another person and assignment with 4 days remaining
    from db.models.person import Person
    p2 = Person(
        full_name="Тест Қолган Кунлар",
        birth_date=datetime.date(1995, 5, 20),
        mahalla_id=sample_mahalla.id,
    )
    db_session.add(p2)
    await db_session.commit()
    await db_session.refresh(p2)

    a2 = PersonCategoryAssignment(
        person_id=p2.id,
        category_id=sample_category.id,
        mahalla_id=sample_mahalla.id,
        frequency_days=4,
        next_check_in_due=today + datetime.timedelta(days=4),
        status=AssignmentStatus.ACTIVE,
    )
    db_session.add(a2)
    await db_session.commit()
    await db_session.refresh(a2)

    # Upload document for a2 (has 4 days remaining)
    fake_photo2 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo2")
    res2 = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(a2.id)},
        files={"photo": ("doc2.jpg", fake_photo2, "image/jpeg")},
    )
    assert res2.status_code == 201
    doc2_id = res2.json()["id"]

    # 1. Query with remaining_days = 5 -> should return ONLY doc1
    res_5 = await client.get(
        "/documents?remaining_days=5",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_5.status_code == 200
    data_5 = res_5.json()
    assert data_5["total"] == 1
    assert data_5["items"][0]["id"] == doc1_id
    assert data_5["items"][0]["days_remaining"] == 5

    # 2. Query with remaining_days = 4 -> should return ONLY doc2
    res_4 = await client.get(
        "/documents?remaining_days=4",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_4.status_code == 200
    data_4 = res_4.json()
    assert data_4["total"] == 1
    assert data_4["items"][0]["id"] == doc2_id
    assert data_4["items"][0]["days_remaining"] == 4

    # 3. Query with remaining_days = 3 -> none match
    res_3 = await client.get(
        "/documents?remaining_days=3",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_3.status_code == 200
    assert res_3.json()["total"] == 0

    # 4. Query with alias days_remaining = 5 -> works identically
    res_alias = await client.get(
        "/documents?days_remaining=5",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_alias.status_code == 200
    assert res_alias.json()["total"] == 1
    assert res_alias.json()["items"][0]["id"] == doc1_id


