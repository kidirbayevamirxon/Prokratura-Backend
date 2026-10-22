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
        "description": "Test photo size limit",
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
        "description": "Test pdf size limit",
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
        data={"assignment_id": str(sample_assignment.id), "notes": "Suhbat o'tkazildi"},
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
            "notes": "Navbatdagi ko'rik",
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
    women_activist_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo")
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id), "notes": "Tekshiruv o'tkazildi"},
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

    # Assigned worker (Inspector) sees their documents
    i_docs = await client.get(
        "/documents", headers={"Authorization": f"Bearer {inspector_token}"}
    )
    assert i_docs.status_code == 200
    assert i_docs.json()["total"] == 1

    # Another Mahalla 7 worker not assigned to this category (Women activist) does NOT see this document
    w_docs = await client.get(
        "/documents", headers={"Authorization": f"Bearer {women_activist_token}"}
    )
    assert w_docs.status_code == 200
    assert w_docs.json()["total"] == 0


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
        data={"assignment_id": str(sample_assignment.id), "notes": "5 kun qoldi"},
        files={"photo": ("doc1.jpg", fake_photo1, "image/jpeg")},
    )
    assert res1.status_code == 201
    doc1_id = res1.json()["id"]

    # Create another person and assignment with 4 days remaining
    from db.models.person import Person
    p2 = Person(
        full_name="Тест Қолган Кунlar",
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
        data={"assignment_id": str(a2.id), "notes": "4 kun qoldi"},
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

    # 5. Upload a second document for sample_assignment (same assignment, duplicate prevention)
    fake_photo3 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo3")
    res_doc3 = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id), "notes": "ikkinchi tekshiruv"},
        files={"photo": ("doc3.jpg", fake_photo3, "image/jpeg")},
    )
    assert res_doc3.status_code == 201
    doc3_id = res_doc3.json()["id"]

    # When querying remaining_days = 5, it should deduplicate by assignment and return only 1 item (the latest doc3)
    res_dedup = await client.get(
        "/documents?remaining_days=5",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_dedup.status_code == 200
    dedup_json = res_dedup.json()
    assert dedup_json["total"] == 1
    assert len(dedup_json["items"]) == 1
    assert dedup_json["items"][0]["id"] == doc3_id

    # If latest_only=false is passed, it returns all historical documents for that day
    res_all = await client.get(
        "/documents?remaining_days=5&latest_only=false",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 2

    # 6. If doc3 is approved, Jami tab (no status filter) still returns 1 item for this assignment,
    # and status=approved returns 1, while status=pending returns 0
    await client.patch(
        f"/documents/{doc3_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved"},
    )
    res_approved_jami = await client.get(
        "/documents?remaining_days=5",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_approved_jami.status_code == 200
    assert res_approved_jami.json()["total"] == 1
    assert res_approved_jami.json()["items"][0]["status"] == "approved"

    res_approved_tab = await client.get(
        "/documents?remaining_days=5&status=approved",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_approved_tab.status_code == 200
    assert res_approved_tab.json()["total"] == 1

    res_pending_tab = await client.get(
        "/documents?remaining_days=5&status=pending",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res_pending_tab.status_code == 200
    # Because doc3 was approved, doc1 is now the latest pending document for this assignment
    assert res_pending_tab.json()["total"] == 1
    assert res_pending_tab.json()["items"][0]["id"] == doc1_id


@pytest.mark.asyncio
async def test_upload_document_requires_description(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo")

    # 1. Missing description and notes -> 422
    res_no_desc = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id)},
        files={"photo": ("visit.jpg", fake_photo, "image/jpeg")},
    )
    assert res_no_desc.status_code == 422
    assert "Description is required" in res_no_desc.text

    # 2. Whitespace-only description -> 422
    fake_photo2 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo")
    res_empty_desc = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={"assignment_id": str(sample_assignment.id), "description": "   "},
        files={"photo": ("visit.jpg", fake_photo2, "image/jpeg")},
    )
    assert res_empty_desc.status_code == 422

    # 3. Provided description -> 201
    fake_photo3 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo")
    res_valid = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "description": "Profilaktik ko'rik to'liq yakunlandi",
        },
        files={"photo": ("visit.jpg", fake_photo3, "image/jpeg")},
    )
    assert res_valid.status_code == 201
    doc_data = res_valid.json()
    assert doc_data["description"] == "Profilaktik ko'rik to'liq yakunlandi"
    assert doc_data["notes"] == "Profilaktik ko'rik to'liq yakunlandi"


@pytest.mark.asyncio
async def test_prokuror_document_seen_by_assigned_role_and_not_completed(
    client: AsyncClient,
    prokuror_token: str,
    rais_token: str,
    inspector_token: str,
    women_activist_token: str,
    sample_assignment: PersonCategoryAssignment,
    db_session,
):
    today = datetime.date.today()
    sample_assignment.next_check_in_due = today + datetime.timedelta(days=5)
    await db_session.commit()

    # 1. Prokuror creates document and sends to Mahalla
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"prokuror photo proof")
    prok_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(today),
            "description": "Prokuror tomonidan fuqaro holatini o'rganish topshirig'i",
        },
        files={"photo": ("topshiriq.jpg", fake_photo, "image/jpeg")},
    )
    assert prok_res.status_code == 201
    doc = prok_res.json()
    doc_id = doc["id"]
    assert doc["status"] == "pending"
    assert doc["is_seen"] is False
    assert doc["seen_at"] is None
    assert doc["seen_by_id"] is None

    # 2. Mahalla Raisi opens/views the document details (GET /documents/{doc_id})
    # Rais is NOT in assigned_roles (only profilaktika_inspektori is assigned).
    # Must NOT mark completed ("approved") and must NOT mark seen.
    rais_res = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert rais_res.status_code == 200
    rais_doc = rais_res.json()
    assert rais_doc["status"] == "pending"
    assert rais_doc["is_seen"] is False
    assert rais_doc["seen_at"] is None
    assert rais_doc["seen_by_id"] is None

    # 3. Another official not in assigned role (e.g., women activist) views document
    # Must also NOT mark seen or completed.
    activist_res = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {women_activist_token}"},
    )
    assert activist_res.status_code == 200
    activist_doc = activist_res.json()
    assert activist_doc["status"] == "pending"
    assert activist_doc["is_seen"] is False

    # 4. Assigned worker (profilaktika inspektori) opens/views the document
    # MUST mark seen (seen_at, seen_by_id, seen_by_name)
    # BUT must NOT mark completed (status remains "pending")
    inspector_res = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert inspector_res.status_code == 200
    seen_doc = inspector_res.json()
    assert seen_doc["is_seen"] is True
    assert seen_doc["seen_at"] is not None
    assert seen_doc["seen_by_name"] == "Mansur Polatov"
    assert seen_doc["status"] == "pending"

    # 5. Prokuror checks the document -> prokuror sees that the assigned employee saw it, status still pending
    prok_view = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert prok_view.status_code == 200
    prok_doc = prok_view.json()
    assert prok_doc["is_seen"] is True
    assert prok_doc["seen_at"] is not None
    assert prok_doc["seen_by_name"] == "Mansur Polatov"
    assert prok_doc["status"] == "pending"

    # 6. In documents list, prokuror sees the document with seen info and pending status
    list_res = await client.get(
        f"/documents?assignment_id={sample_assignment.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    target_item = [item for item in items if item["id"] == doc_id][0]
    assert target_item["is_seen"] is True
    assert target_item["seen_by_name"] == "Mansur Polatov"
    assert target_item["status"] == "pending"

    # 7. Explicit mark-as-seen endpoint POST /documents/{doc_id}/seen also preserves seen state and pending status
    seen_endpoint_res = await client.post(
        f"/documents/{doc_id}/seen",
        headers={"Authorization": f"Bearer {inspector_token}"},
    )
    assert seen_endpoint_res.status_code == 200
    assert seen_endpoint_res.json()["is_seen"] is True
    assert seen_endpoint_res.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_document_saves_previous_and_new_date(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo content" * 50)
    files = {"photo": ("visit_photo.jpg", fake_photo, "image/jpeg")}

    asked_date = str(datetime.date.today() + datetime.timedelta(days=12))
    original_due = str(sample_assignment.next_check_in_due)

    data = {
        "assignment_id": str(sample_assignment.id),
        "check_in_date": str(datetime.date.today()),
        "doc_type": "regular",
        "new_date": asked_date,
        "description": "Fuqaro betob bo'lganligi sababli muddat uzaytirish so'ralmoqda",
    }

    res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data=data,
        files=files,
    )
    assert res.status_code == 201
    doc = res.json()
    assert doc["status"] == "pending"
    assert doc["doc_type"] == "regular"
    assert doc["previous_date"] == original_due
    assert doc["new_date"] == asked_date


@pytest.mark.asyncio
async def test_prokuror_review_approves_submitted_new_date(
    client: AsyncClient,
    inspector_token: str,
    prokuror_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo" * 50)
    files = {"photo": ("visit.jpg", fake_photo, "image/jpeg")}
    asked_date = str(datetime.date.today() + datetime.timedelta(days=15))

    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "doc_type": "regular",
            "new_date": asked_date,
            "description": "Muddat uzaytirish so'ralmoqda",
        },
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Prokuror approves
    rev_res = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved"},
    )
    assert rev_res.status_code == 200
    rev_doc = rev_res.json()
    assert rev_doc["status"] == "approved"
    assert rev_doc["new_date"] == asked_date

    # Verify assignment next_check_in_due was updated to the new date
    person_res = await client.get(
        f"/persons/{sample_assignment.person_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = person_res.json()["assignments"][0]
    assert assignment["next_check_in_due"] == asked_date


@pytest.mark.asyncio
async def test_prokuror_review_with_custom_new_date(
    client: AsyncClient,
    inspector_token: str,
    prokuror_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo" * 50)
    files = {"photo": ("visit.jpg", fake_photo, "image/jpeg")}
    original_due = str(sample_assignment.next_check_in_due)

    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "description": "Muntazam tekshiruv hisoboti",
        },
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    custom_new_date = str(datetime.date.today() + datetime.timedelta(days=20))
    rev_res = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved", "new_date": custom_new_date},
    )
    assert rev_res.status_code == 200
    rev_doc = rev_res.json()
    assert rev_doc["status"] == "approved"
    assert rev_doc["previous_date"] == original_due
    assert rev_doc["new_date"] == custom_new_date

    person_res = await client.get(
        f"/persons/{sample_assignment.person_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = person_res.json()["assignments"][0]
    assert assignment["next_check_in_due"] == custom_new_date


@pytest.mark.asyncio
async def test_prokuror_patch_document_changes_date(
    client: AsyncClient,
    inspector_token: str,
    prokuror_token: str,
    rais_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"photo" * 50)
    files = {"photo": ("visit.jpg", fake_photo, "image/jpeg")}

    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "description": "Tekshiruv dalolatnomasi",
        },
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 1. Non-prokuror / non-admin cannot patch document
    forbidden_res = await client.patch(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {inspector_token}"},
        json={"new_date": "2026-10-30"},
    )
    assert forbidden_res.status_code == 403

    rais_forbidden = await client.patch(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {rais_token}"},
        json={"new_date": "2026-10-30"},
    )
    assert rais_forbidden.status_code == 403

    # 2. Prokuror successfully patches document new_date
    target_date = str(datetime.date.today() + datetime.timedelta(days=25))
    patch_res = await client.patch(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"new_date": target_date},
    )
    assert patch_res.status_code == 200
    patched_doc = patch_res.json()
    assert patched_doc["new_date"] == target_date
    assert patched_doc["previous_date"] is not None

    # Check assignment updated
    person_res = await client.get(
        f"/persons/{sample_assignment.person_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = person_res.json()["assignments"][0]
    assert assignment["next_check_in_due"] == target_date


@pytest.mark.asyncio
async def test_upload_document_request_extension(
    client: AsyncClient,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy photo content" * 50)
    files = {"photo": ("photo.jpg", fake_photo, "image/jpeg")}
    target_ext_date = str(datetime.date.today() + datetime.timedelta(days=14))

    data = {
        "assignment_id": str(sample_assignment.id),
        "check_in_date": str(datetime.date.today()),
        "doc_type": "request_extension",
        "requested_date": target_ext_date,
        "description": "Muddatni uzaytirish so'rovi",
    }

    response = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data=data,
        files=files,
    )
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["doc_type"] == "request_extension"
    assert res_data["requested_date"] == target_ext_date


@pytest.mark.asyncio
async def test_prokuror_sends_doc_outside_regular_frequency_with_optional_frequency_days(
    client: AsyncClient,
    prokuror_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"prokuror task photo" * 50)
    files = {"photo": ("task.jpg", fake_photo, "image/jpeg")}
    original_due = str(sample_assignment.next_check_in_due)

    # Prokuror sends document for employers with frequency_days = 3
    prokuror_doc_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "frequency_days": "3",
            "description": "Prokuror topshirig'i: 3 kun muddatda fuqaro holatini o'rganish",
        },
        files=files,
    )
    assert prokuror_doc_res.status_code == 201
    doc = prokuror_doc_res.json()
    expected_due = str(datetime.date.today() + datetime.timedelta(days=3))
    assert doc["is_from_prokuror"] is True
    assert doc["frequency_days"] == 3
    assert doc["due_date"] == expected_due

    # The regular assignment's next_check_in_due is unchanged (outside regular frequency)
    person_res = await client.get(
        f"/persons/{sample_assignment.person_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = person_res.json()["assignments"][0]
    assert str(assignment["next_check_in_due"]) == original_due


@pytest.mark.asyncio
async def test_employer_requests_extension_on_prokuror_sent_doc(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"task" * 50)
    files = {"photo": ("task.jpg", fake_photo, "image/jpeg")}
    original_due = str(sample_assignment.next_check_in_due)

    # 1. Prokuror sends doc with frequency_days = 2
    prokuror_doc_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "frequency_days": "2",
            "description": "Tezkor tekshiruv",
        },
        files=files,
    )
    assert prokuror_doc_res.status_code == 201
    doc_id = prokuror_doc_res.json()["id"]

    # 2. Employer requests extension for this prokuror doc via POST /{document_id}/request-extension
    ext_date = str(datetime.date.today() + datetime.timedelta(days=7))
    ext_res = await client.post(
        f"/documents/{doc_id}/request-extension",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "requested_date": ext_date,
            "description": "Qo'shimcha hujjatlarni to'plash uchun 7 kun muddat so'raladi",
        },
    )
    assert ext_res.status_code == 200
    ext_doc = ext_res.json()
    assert ext_doc["requested_date"] == ext_date
    assert ext_doc["doc_type"] == "request_extension"

    # 3. Prokuror reviews and approves the extension request on the prokuror doc
    rev_res = await client.patch(
        f"/documents/{doc_id}/review",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"status": "approved"},
    )
    assert rev_res.status_code == 200
    rev_doc = rev_res.json()
    assert rev_doc["status"] == "approved"
    assert rev_doc["due_date"] == ext_date
    assert rev_doc["new_date"] == ext_date

    # 4. Assignment's regular frequency schedule remains intact (outside regular frequency)
    person_res = await client.get(
        f"/persons/{sample_assignment.person_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assignment = person_res.json()["assignments"][0]
    assert str(assignment["next_check_in_due"]) == original_due


@pytest.mark.asyncio
async def test_employer_requests_extension_via_patch_document(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"doc" * 50)
    files = {"photo": ("doc.jpg", fake_photo, "image/jpeg")}

    # Upload document
    upload_res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(datetime.date.today()),
            "frequency_days": "5",
            "description": "Tekshiruv vazifasi",
        },
        files=files,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Employer uses PATCH /documents/{doc_id} to request extension
    ext_date = str(datetime.date.today() + datetime.timedelta(days=10))
    patch_res = await client.patch(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {inspector_token}"},
        json={
            "requested_date": ext_date,
            "description": "Muddat uzaytirish so'rovi",
        },
    )
    assert patch_res.status_code == 200
    patched_doc = patch_res.json()
    assert patched_doc["requested_date"] == ext_date
    assert patched_doc["doc_type"] == "request_extension"


@pytest.mark.asyncio
async def test_mahalla_document_seen_by_prokuror(
    client: AsyncClient,
    prokuror_token: str,
    inspector_token: str,
    sample_assignment: PersonCategoryAssignment,
):
    today = datetime.date.today()
    fake_photo = io.BytesIO(b"\xff\xd8\xff\xe0" + b"mahalla photo proof")

    # 1. Mahalla inspector uploads document
    res = await client.post(
        "/documents",
        headers={"Authorization": f"Bearer {inspector_token}"},
        data={
            "assignment_id": str(sample_assignment.id),
            "check_in_date": str(today),
            "description": "Mahalla xodimi tekshiruvi",
        },
        files={"photo": ("visit.jpg", fake_photo, "image/jpeg")},
    )
    assert res.status_code == 201
    doc = res.json()
    doc_id = doc["id"]
    assert doc["is_from_prokuror"] is False
    assert doc["is_seen"] is False
    assert doc["seen_at"] is None
    assert doc["seen_by_id"] is None

    # 2. Prokuror views the document details -> MUST mark seen
    prok_res = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert prok_res.status_code == 200
    seen_doc = prok_res.json()
    assert seen_doc["is_seen"] is True
    assert seen_doc["seen_at"] is not None
    assert seen_doc["seen_by_name"] == "Alisher Navoiy"

    # 3. In documents list, prokuror sees the document with seen info
    list_res = await client.get(
        f"/documents?assignment_id={sample_assignment.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert list_res.status_code == 200
    target_item = [item for item in list_res.json()["items"] if item["id"] == doc_id][0]
    assert target_item["is_seen"] is True
    assert target_item["seen_by_name"] == "Alisher Navoiy"




