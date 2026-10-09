import base64
import hashlib
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from fido2.cbor import encode as cbor_encode
from fido2.cose import ES256
from sqlalchemy import select

from backend.main import app
from backend.auth.service import AuthServices
from backend.auth.webauthn_utils import urlsafe_b64encode
from db.models.user import User, UserRole
from db.models.user_device import UserDevice


def create_simulated_webauthn_registration(challenge_b64: str, rp_id: str = "localhost"):
    """Simulate a browser hardware authenticator creating a P-256 key pair and attestation."""
    # 1. Generate on-chip key pair
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    cose_key = ES256.from_cryptography_key(public_key)

    # 2. Credential ID
    cred_id = b"hardware_key_" + hashlib.sha256(challenge_b64.encode()).digest()[:16]
    cred_id_b64 = urlsafe_b64encode(cred_id)

    # 3. ClientDataJSON
    client_data = {
        "type": "webauthn.create",
        "challenge": challenge_b64,
        "origin": f"https://{rp_id}",
    }
    client_data_bytes = json.dumps(client_data).encode("utf-8")
    client_data_b64 = urlsafe_b64encode(client_data_bytes)

    # 4. AuthenticatorData with attested credential data
    rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
    flags = bytes([0x01 | 0x04 | 0x40])  # UP (bit 0), UV (bit 2), AT (bit 6)
    sign_count = (0).to_bytes(4, "big")
    aaguid = b"\x00" * 16
    cred_id_len = len(cred_id).to_bytes(2, "big")
    cose_bytes = cbor_encode(cose_key)

    auth_data = rp_id_hash + flags + sign_count + aaguid + cred_id_len + cred_id + cose_bytes

    # 5. AttestationObject
    att_obj_dict = {
        "fmt": "none",
        "attStmt": {},
        "authData": auth_data,
    }
    att_obj_bytes = cbor_encode(att_obj_dict)
    att_obj_b64 = urlsafe_b64encode(att_obj_bytes)

    return private_key, cred_id_b64, client_data_b64, att_obj_b64


def create_simulated_webauthn_assertion(
    private_key,
    cred_id_b64: str,
    challenge_b64: str,
    counter: int = 1,
    rp_id: str = "localhost",
):
    """Simulate a browser hardware authenticator signing a login challenge."""
    client_data = {
        "type": "webauthn.get",
        "challenge": challenge_b64,
        "origin": f"https://{rp_id}",
    }
    client_data_bytes = json.dumps(client_data).encode("utf-8")
    client_data_b64 = urlsafe_b64encode(client_data_bytes)

    rp_id_hash = hashlib.sha256(rp_id.encode()).digest()
    flags = bytes([0x01 | 0x04])  # UP and UV
    sign_count = counter.to_bytes(4, "big")
    auth_data = rp_id_hash + flags + sign_count
    auth_data_b64 = urlsafe_b64encode(auth_data)

    client_data_hash = hashlib.sha256(client_data_bytes).digest()
    signed_data = auth_data + client_data_hash

    signature = private_key.sign(signed_data, ec.ECDSA(hashes.SHA256()))
    signature_b64 = urlsafe_b64encode(signature)

    return cred_id_b64, auth_data_b64, client_data_b64, signature_b64


@pytest.mark.asyncio
async def test_device_registration_and_login_flow(client: AsyncClient, admin_user: User, admin_token: str, db_session):
    # 1. Get registration challenge (Authenticated)
    res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200, res.text
    ch_data = res.json()
    challenge = ch_data["challenge"]
    challenge_token = ch_data["challenge_token"]

    # 2. Simulate hardware authenticator creating key
    priv_key, cred_id, client_data_b64, att_obj_b64 = create_simulated_webauthn_registration(challenge)

    # 3. Verify registration
    reg_verify_res = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": challenge_token,
            "credential_id": cred_id,
            "client_data_json": client_data_b64,
            "attestation_object": att_obj_b64,
            "device_name": "Admin Workstation X1",
        },
    )
    assert reg_verify_res.status_code == 201, reg_verify_res.text
    reg_tokens = reg_verify_res.json()
    assert "access_token" in reg_tokens

    # Verify device exists in DB
    dev = (await db_session.execute(select(UserDevice).where(UserDevice.user_id == admin_user.id))).scalar_one()
    assert dev.credential_id == cred_id
    assert dev.device_name == "Admin Workstation X1"
    assert dev.is_active is True

    # 4. Device login challenge
    login_ch_res = await client.post(
        "/auth/device/login/challenge",
        json={"identifier": admin_user.login},
    )
    assert login_ch_res.status_code == 200, login_ch_res.text
    login_ch_data = login_ch_res.json()
    login_challenge = login_ch_data["challenge"]
    login_ch_token = login_ch_data["challenge_token"]
    assert login_ch_data["credential_id"] == cred_id

    # 5. Sign login challenge with chip private key
    cred_id_res, auth_data_b64, login_cd_b64, sig_b64 = create_simulated_webauthn_assertion(
        priv_key, cred_id, login_challenge, counter=1
    )

    login_res = await client.post(
        "/auth/device/login/verify",
        json={
            "challenge_token": login_ch_token,
            "credential_id": cred_id_res,
            "authenticator_data": auth_data_b64,
            "client_data_json": login_cd_b64,
            "signature": sig_b64,
        },
    )
    assert login_res.status_code == 200, login_res.text
    login_tokens = login_res.json()
    assert "access_token" in login_tokens

    # 6. Wrong signature must fail
    bad_login_res = await client.post(
        "/auth/device/login/verify",
        json={
            "challenge_token": login_ch_token,
            "credential_id": cred_id_res,
            "authenticator_data": auth_data_b64,
            "client_data_json": login_cd_b64,
            "signature": urlsafe_b64encode(b"invalid_signature_bytes_here_1234567"),
        },
    )
    assert bad_login_res.status_code in [400, 401]


@pytest.mark.asyncio
async def test_single_device_invariant_and_replacement(client: AsyncClient, admin_user: User, admin_token: str, db_session):
    # Step A: Register Device A
    res_a = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    ch_a = res_a.json()
    priv_a, cred_a, cd_a, att_a = create_simulated_webauthn_registration(ch_a["challenge"])
    verify_a = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_a["challenge_token"],
            "credential_id": cred_a,
            "client_data_json": cd_a,
            "attestation_object": att_a,
            "device_name": "Device A",
        },
    )
    assert verify_a.status_code == 201
    token_device_a = verify_a.json()["access_token"]

    # Step B: Register Device B (Replacement)
    res_b = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {token_device_a}"},
    )
    ch_b = res_b.json()
    priv_b, cred_b, cd_b, att_b = create_simulated_webauthn_registration(ch_b["challenge"])
    verify_b = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_b["challenge_token"],
            "credential_id": cred_b,
            "client_data_json": cd_b,
            "attestation_object": att_b,
            "device_name": "Device B",
        },
    )
    assert verify_b.status_code == 201

    # Verify database has ONLY 1 active device for this user (Device B)
    dev_count = (await db_session.execute(select(UserDevice).where(UserDevice.user_id == admin_user.id))).scalars().all()
    assert len(dev_count) == 1
    assert dev_count[0].credential_id == cred_b

    # Verify Device A's old access token was instantly invalidated (Session revoked)
    me_res_old = await client.get("/auth/me", headers={"Authorization": f"Bearer {token_device_a}"})
    assert me_res_old.status_code == 401
    assert "revoked" in me_res_old.json()["detail"].lower()


@pytest.mark.asyncio
async def test_device_reset_permissions(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    prokuror_user: User,
    prokuror_token: str,
    rais_user: User,
    rais_token: str,
    db_session,
):
    # Bind a device to rais
    ch_res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    ch_data = ch_res.json()
    _, cred_id, cd_b64, att_b64 = create_simulated_webauthn_registration(ch_data["challenge"])
    await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_data["challenge_token"],
            "credential_id": cred_id,
            "client_data_json": cd_b64,
            "attestation_object": att_b64,
            "device_name": "Rais PC",
        },
    )

    # 1. Prokuror resets Mahalla Raisi device -> SUCCESS
    reset_res = await client.post(
        f"/users/{rais_user.id}/reset-device",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "device_reset"

    # Verify device unlinked in DB
    dev_in_db = (await db_session.execute(select(UserDevice).where(UserDevice.user_id == rais_user.id))).scalar_one_or_none()
    assert dev_in_db is None

    # 2. Prokuror tries to reset Admin device -> 403 FORBIDDEN
    bad_reset = await client.post(
        f"/users/{admin_user.id}/reset-device",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert bad_reset.status_code == 403

    # 3. Rais tries to reset another user's device -> 403 FORBIDDEN
    fresh_rais_token = AuthServices.issue_tokens(rais_user).access_token
    rais_bad_reset = await client.post(
        f"/users/{prokuror_user.id}/reset-device",
        headers={"Authorization": f"Bearer {fresh_rais_token}"},
    )
    assert rais_bad_reset.status_code == 403

    # 4. Admin resets Prokuror device -> 200 OK
    admin_reset = await client.post(
        f"/users/{prokuror_user.id}/reset-device",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_reset.status_code == 200


@pytest.mark.asyncio
async def test_device_transfer_token_flow(client: AsyncClient, admin_token: str):
    # 1. Generate transfer token while logged in on old PC
    transfer_res = await client.post(
        "/users/me/device-transfer-token",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert transfer_res.status_code == 200
    t_token = transfer_res.json()["transfer_token"]

    # 2. On New PC without headers, use transfer token to get registration challenge
    ch_res = await client.post(
        f"/auth/device/register/challenge?transfer_token={t_token}"
    )
    assert ch_res.status_code == 200
    ch_data = ch_res.json()

    # 3. Complete registration on New PC
    _, cred_id, cd_b64, att_b64 = create_simulated_webauthn_registration(ch_data["challenge"])
    new_reg_res = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_data["challenge_token"],
            "credential_id": cred_id,
            "client_data_json": cd_b64,
            "attestation_object": att_b64,
            "device_name": "New Replacement Laptop",
        },
    )
    assert new_reg_res.status_code == 201
    assert "access_token" in new_reg_res.json()


@pytest.mark.asyncio
async def test_option_a_password_login_blocked_when_device_bound(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    db_session,
):
    """Test Option A: Password login is blocked with 403 when hardware device is bound."""
    # 1. Before device registration, password login succeeds
    login_before = await client.post(
        "/auth/login",
        json={"login": admin_user.login, "password": "admin123"},
    )
    assert login_before.status_code == 200

    # 2. Register hardware device
    ch_res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    ch_data = ch_res.json()
    _, cred_id, cd_b64, att_b64 = create_simulated_webauthn_registration(ch_data["challenge"])
    reg_res = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_data["challenge_token"],
            "credential_id": cred_id,
            "client_data_json": cd_b64,
            "attestation_object": att_b64,
            "device_name": "Admin YubiKey",
        },
    )
    assert reg_res.status_code == 201

    # 3. Now password login MUST fail with 403 Forbidden (Option A)
    login_after = await client.post(
        "/auth/login",
        json={"login": admin_user.login, "password": "admin123"},
    )
    assert login_after.status_code == 403
    assert "apparat xavfsizlik qurilmasi biriktirilgan" in login_after.json()["detail"]


@pytest.mark.asyncio
async def test_regular_user_cannot_change_or_remove_device(
    client: AsyncClient,
    rais_user: User,
    rais_token: str,
    prokuror_user: User,
    prokuror_token: str,
    db_session,
):
    """Test that regular users cannot change or remove a paired device; only Prokuror/Admin can."""
    # 1. Rais pairs their initial device
    ch_res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert ch_res.status_code == 200
    ch_data = ch_res.json()
    _, cred_id, cd_b64, att_b64 = create_simulated_webauthn_registration(ch_data["challenge"])
    reg_res = await client.post(
        "/auth/device/register/verify",
        json={
            "challenge_token": ch_data["challenge_token"],
            "credential_id": cred_id,
            "client_data_json": cd_b64,
            "attestation_object": att_b64,
            "device_name": "Rais Laptop",
        },
    )
    assert reg_res.status_code == 201
    rais_dev_token = reg_res.json()["access_token"]

    # 2. Rais tries to change/re-register their device directly -> 403 Forbidden
    ch_change = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {rais_dev_token}"},
    )
    assert ch_change.status_code == 403
    assert "faqat Prokuror yoki Admin" in ch_change.json()["detail"]

    # 3. Rais cannot generate transfer token -> 403 Forbidden
    transfer_res = await client.post(
        "/users/me/device-transfer-token",
        headers={"Authorization": f"Bearer {rais_dev_token}"},
    )
    assert transfer_res.status_code == 403

    # 4. Rais cannot unbind/reset device -> 403 Forbidden
    reset_res = await client.post(
        f"/users/{rais_user.id}/reset-device",
        headers={"Authorization": f"Bearer {rais_dev_token}"},
    )
    assert reset_res.status_code == 403

    # 5. Prokuror resets the device -> 200 OK
    prok_reset = await client.post(
        f"/users/{rais_user.id}/reset-device",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert prok_reset.status_code == 200

    # 6. Device is reset; Rais can now pair a new device or login with password
    login_unbound = await client.post(
        "/auth/login",
        json={"login": rais_user.login, "password": "rais123"},
    )
    assert login_unbound.status_code == 200
