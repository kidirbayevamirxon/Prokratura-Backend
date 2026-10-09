import hashlib
import json
import os
import time
import pytest
import cbor2
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes

from backend.devices.service import challenge_store, ChallengeStore
from db.models.user import User


def make_webauthn_credentials(
    rp_id: str = "test", origin: str = "http://test", custom_cred_id: bytes = None
):
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_numbers = private_key.public_key().public_numbers()
    x = public_numbers.x.to_bytes(32, "big")
    y = public_numbers.y.to_bytes(32, "big")
    cose_key = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: x, -3: y})
    rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
    cred_id = custom_cred_id if custom_cred_id is not None else (b"cred_" + os.urandom(16))

    def create_registration_credential(challenge: bytes):
        client_data = json.dumps({
            "type": "webauthn.create",
            "challenge": bytes_to_base64url(challenge),
            "origin": origin,
            "crossOrigin": False,
        }).encode("utf-8")
        flags = 0x45  # UP | UV | AT
        aaguid = b"\x00" * 16
        attested_data = aaguid + len(cred_id).to_bytes(2, "big") + cred_id + cose_key
        auth_data = rp_id_hash + bytes([flags]) + (0).to_bytes(4, "big") + attested_data
        att_obj = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": bytes_to_base64url(cred_id),
            "rawId": bytes_to_base64url(cred_id),
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(att_obj),
            },
            "type": "public-key",
        }

    def create_authentication_credential(challenge: bytes, sign_count: int = 1):
        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": bytes_to_base64url(challenge),
            "origin": origin,
            "crossOrigin": False,
        }).encode("utf-8")
        client_data_hash = hashlib.sha256(client_data).digest()
        auth_flags = 0x05  # UP | UV
        auth_data = rp_id_hash + bytes([auth_flags]) + sign_count.to_bytes(4, "big")
        sig = private_key.sign(auth_data + client_data_hash, ec.ECDSA(hashes.SHA256()))
        return {
            "id": bytes_to_base64url(cred_id),
            "rawId": bytes_to_base64url(cred_id),
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(sig),
            },
            "type": "public-key",
        }

    return cred_id, create_registration_credential, create_authentication_credential


@pytest.mark.asyncio
async def test_get_device_status_unbound(client: AsyncClient, prokuror_token: str):
    res = await client.get(
        "/devices/status",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_bound"] is False
    assert data["has_device"] is False
    assert data["device"] is None


@pytest.mark.asyncio
async def test_register_options(client: AsyncClient, prokuror_token: str):
    res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "challenge" in data
    assert "user" in data
    assert data["authenticatorSelection"]["authenticatorAttachment"] == "platform"
    assert data["authenticatorSelection"]["userVerification"] == "required"


@pytest.mark.asyncio
async def test_register_verify_and_status(
    client: AsyncClient, prokuror_user: User, prokuror_token: str
):
    # 1. Get registration options
    opt_res = await client.post(
        "/devices/register-options",
        headers={
            "Authorization": f"Bearer {prokuror_token}",
            "Origin": "http://test",
        },
    )
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    challenge_b64 = opt_data["challenge"]
    challenge_bytes = base64url_to_bytes(challenge_b64)

    # 2. Build mock registration response
    cred_id, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    # 3. Verify and bind
    verify_res = await client.post(
        "/devices/register-verify",
        headers={
            "Authorization": f"Bearer {prokuror_token}",
            "Origin": "http://test",
        },
        json={
            "credential": cred_payload,
            "device_name": "Work Laptop TPM",
        },
    )
    assert verify_res.status_code == 201
    dev_data = verify_res.json()
    assert dev_data["user_id"] == prokuror_user.id
    assert dev_data["device_name"] == "Work Laptop TPM"
    assert dev_data["sign_count"] == 0

    # 4. Check status
    status_res = await client.get(
        "/devices/status",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_bound"] is True
    assert status_data["has_device"] is True
    assert status_data["device_name"] == "Work Laptop TPM"
    assert status_data["user_id"] == prokuror_user.id


@pytest.mark.asyncio
async def test_single_device_restriction_on_register_options(
    client: AsyncClient, prokuror_user: User, prokuror_token: str
):
    # First, register a device
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    cred_id, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    verify_res = await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Device 1"},
    )
    assert verify_res.status_code == 201

    # Attempting to get register options again MUST raise 409 Conflict
    second_opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    assert second_opt_res.status_code == 409
    assert (
        second_opt_res.json()["detail"]
        == "User already has a registered device. Only one device per user is permitted."
    )


@pytest.mark.asyncio
async def test_single_device_restriction_on_register_verify(
    client: AsyncClient, prokuror_user: User, prokuror_token: str
):
    # Register first device
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Device 1"},
    )

    # Force challenge into store to simulate a bypassed options call
    fake_challenge = os.urandom(32)
    challenge_store.set(f"reg:{prokuror_user.id}", fake_challenge)
    _, create_reg_2, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload_2 = create_reg_2(fake_challenge)

    second_verify_res = await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload_2, "device_name": "Device 2"},
    )
    assert second_verify_res.status_code == 409
    assert (
        second_verify_res.json()["detail"]
        == "User already has a registered device. Only one device per user is permitted."
    )


@pytest.mark.asyncio
async def test_login_options_and_login_verify(
    client: AsyncClient, prokuror_user: User, prokuror_token: str
):
    # 1. Register a device for prokuror_user
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, create_auth = make_webauthn_credentials(
        rp_id="test", origin="http://test"
    )
    cred_payload = create_reg(challenge_bytes)

    verify_res = await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Secure TPM"},
    )
    assert verify_res.status_code == 201

    # 2. Call public login-options with login
    login_opt_res = await client.post(
        "/devices/login-options",
        headers={"Origin": "http://test"},
        json={"identifier": prokuror_user.login},
    )
    assert login_opt_res.status_code == 200
    login_opt_data = login_opt_res.json()
    auth_challenge_bytes = base64url_to_bytes(login_opt_data["challenge"])
    assert len(login_opt_data["allowCredentials"]) == 1

    # 3. Create WebAuthn assertion
    auth_cred_payload = create_auth(auth_challenge_bytes, sign_count=1)

    # 4. Verify login
    login_verify_res = await client.post(
        "/devices/login-verify",
        headers={"Origin": "http://test"},
        json={
            "identifier": prokuror_user.login,
            "credential": auth_cred_payload,
        },
    )
    assert login_verify_res.status_code == 200
    token_data = login_verify_res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["user_id"] == prokuror_user.id
    assert token_data["role"] == prokuror_user.role.value

    # 5. Check that device sign_count was updated
    status_res = await client.get(
        "/devices/status",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["sign_count"] == 1
    assert status_data["last_used_at"] is not None


@pytest.mark.asyncio
async def test_login_options_no_device(client: AsyncClient, prokuror_user: User):
    res = await client.post(
        "/devices/login-options",
        json={"identifier": prokuror_user.login},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "No registered hardware device found for this user"


@pytest.mark.asyncio
async def test_unbind_device(client: AsyncClient, prokuror_user: User, prokuror_token: str):
    # Register device
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Device to unbind"},
    )

    # Unbind own device
    unbind_res = await client.delete(
        "/devices/unbind",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert unbind_res.status_code == 200
    assert unbind_res.json()["message"] == "Device successfully unbound"

    # Status should now be unbound
    status_res = await client.get(
        "/devices/status",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_bound"] is False

    # Now user should be able to register a new device again!
    new_opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert new_opt_res.status_code == 200


@pytest.mark.asyncio
async def test_admin_reset_device(
    client: AsyncClient,
    admin_token: str,
    prokuror_user: User,
    prokuror_token: str,
):
    # Register device for prokuror
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Prokuror PC"},
    )

    # Non-admin attempting admin reset MUST get 403 Forbidden
    forbidden_res = await client.post(
        f"/devices/admin/reset/{prokuror_user.id}",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert forbidden_res.status_code == 403

    # Admin resetting prokuror device succeeds
    admin_res = await client.post(
        f"/devices/admin/reset/{prokuror_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_res.status_code == 200
    assert "reset successfully" in admin_res.json()["message"]

    # Prokuror status is now unbound
    status_res = await client.get(
        "/devices/status",
        headers={"Authorization": f"Bearer {prokuror_token}"},
    )
    assert status_res.status_code == 200
    assert status_res.json()["is_bound"] is False


@pytest.mark.asyncio
async def test_rename_device(client: AsyncClient, prokuror_user: User, prokuror_token: str):
    # Register device
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {prokuror_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Old Name"},
    )

    # Rename
    patch_res = await client.patch(
        "/devices/rename",
        headers={"Authorization": f"Bearer {prokuror_token}"},
        json={"device_name": "New Name"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["device_name"] == "New Name"


def test_challenge_store_ttl():
    store = ChallengeStore(ttl_seconds=1)
    ch = b"test_challenge_bytes"
    store.set("test_key", ch)

    # Immediate get should return challenge
    assert store.get("test_key") == ch

    # Pop should return challenge and delete
    assert store.pop("test_key") == ch
    assert store.get("test_key") is None

    # Expiry test
    store.set("exp_key", ch)
    time.sleep(1.1)
    assert store.get("exp_key") is None
    assert store.pop("exp_key") is None


@pytest.mark.asyncio
async def test_option_a_password_login_blocked_when_device_bound(
    client: AsyncClient, rais_user: User, rais_token: str
):
    """Option A: If user has an active registered device, password-only login is strictly blocked."""
    # 1. Register a device for rais_user
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {rais_token}", "Origin": "http://test"},
    )
    assert opt_res.status_code == 200
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)

    verify_res = await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {rais_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Rais Laptop"},
    )
    assert verify_res.status_code == 201

    # 2. Attempt password login - must be blocked with 403 Forbidden
    login_res = await client.post(
        "/auth/login",
        json={"login": rais_user.login, "password": "rais123"},
    )
    assert login_res.status_code == 403
    assert "apparat xavfsizlik qurilmasi biriktirilgan" in login_res.json()["detail"]


@pytest.mark.asyncio
async def test_regular_user_cannot_re_register_paired_device(
    client: AsyncClient, rais_user: User, rais_token: str
):
    """Once a device is paired, changing it is forbidden for regular users."""
    # 1. Initial pairing via /auth/device/register/challenge is allowed
    opt_res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {rais_token}", "Host": "mahpro.uz"},
    )
    assert opt_res.status_code == 200
    challenge_data = opt_res.json()
    assert challenge_data["rp"]["id"] == "mahpro.uz"

    # Complete initial registration
    challenge_bytes = base64url_to_bytes(challenge_data["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="mahpro.uz", origin="https://mahpro.uz")
    cred_payload = create_reg(challenge_bytes)

    ver_res = await client.post(
        "/auth/device/register/verify",
        headers={"Authorization": f"Bearer {rais_token}"},
        json={
            "challenge_token": challenge_data["challenge_token"],
            "credential_id": cred_payload["id"],
            "client_data_json": cred_payload["response"]["clientDataJSON"],
            "attestation_object": cred_payload["response"]["attestationObject"],
            "device_name": "First PC",
        },
    )
    assert ver_res.status_code == 201
    new_token = ver_res.json()["access_token"]

    # 2. Now attempt to re-pair / change device as regular user - must be blocked with 403
    second_challenge_res = await client.post(
        "/auth/device/register/challenge",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert second_challenge_res.status_code == 403
    assert "Biriktirilgan qurilmani faqat Prokuror yoki Admin o'zgartirishi mumkin" in second_challenge_res.json()["detail"]


@pytest.mark.asyncio
async def test_regular_user_cannot_unbind_device(
    client: AsyncClient, rais_user: User, rais_token: str
):
    """Removing/unbinding a device is restricted to Prokuror and Admin only."""
    res = await client.delete(
        "/devices/unbind",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_generate_transfer_token(
    client: AsyncClient, rais_user: User, rais_token: str
):
    """Generating a transfer token is restricted to Prokuror and Admin only."""
    res = await client.post(
        "/users/me/device-transfer-token",
        headers={"Authorization": f"Bearer {rais_token}"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_reset_device_and_restore_login(
    client: AsyncClient, rais_user: User, rais_token: str, admin_token: str
):
    """Admin can reset a user's device, which then allows password login again."""
    # 1. Pair device for rais_user
    opt_res = await client.post(
        "/devices/register-options",
        headers={"Authorization": f"Bearer {rais_token}", "Origin": "http://test"},
    )
    challenge_bytes = base64url_to_bytes(opt_res.json()["challenge"])
    _, create_reg, _ = make_webauthn_credentials(rp_id="test", origin="http://test")
    cred_payload = create_reg(challenge_bytes)
    await client.post(
        "/devices/register-verify",
        headers={"Authorization": f"Bearer {rais_token}", "Origin": "http://test"},
        json={"credential": cred_payload, "device_name": "Device to Reset"},
    )

    # 2. Password login is blocked
    block_res = await client.post(
        "/auth/login",
        json={"login": rais_user.login, "password": "rais123"},
    )
    assert block_res.status_code == 403

    # 3. Admin resets the device
    reset_res = await client.post(
        f"/users/{rais_user.id}/reset-device",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reset_res.status_code == 200

    # 4. Password login now works again
    ok_res = await client.post(
        "/auth/login",
        json={"login": rais_user.login, "password": "rais123"},
    )
    assert ok_res.status_code == 200
    assert "access_token" in ok_res.json()
