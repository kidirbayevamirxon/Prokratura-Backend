import base64
import hashlib
import json
import os
import secrets
import struct
import time
from typing import Any, Dict, Optional, Tuple

from jose import jwt, JWTError
from fido2.cbor import decode as cbor_decode, encode as cbor_encode
from fido2.cose import CoseKey
from fido2.webauthn import AttestationObject, AuthenticatorData


WEBAUTHN_SECRET = os.getenv("WEBAUTHN_SECRET", os.getenv("ACCESS_SECRET", "webauthn_secret_key_change_in_production"))
ALGORITHM = "HS256"


def urlsafe_b64encode(data: bytes) -> str:
    """Encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def urlsafe_b64decode(s: str) -> bytes:
    """Decode base64url or standard base64 string with automatic padding."""
    # Convert standard base64 url safe characters if needed
    s = s.replace("-", "+").replace("_", "/")
    padding = len(s) % 4
    if padding:
        s += "=" * (4 - padding)
    return base64.b64decode(s)


def generate_challenge(byte_length: int = 32) -> Tuple[str, bytes]:
    """Generate a cryptographically secure random challenge."""
    raw = secrets.token_bytes(byte_length)
    return urlsafe_b64encode(raw), raw


def create_challenge_token(user_id: int, challenge_b64: str, token_type: str, expires_in: int = 300, is_transfer: bool = False) -> str:
    """Create a tamper-proof signed challenge token valid for 5 minutes."""
    payload = {
        "sub": str(user_id),
        "challenge": challenge_b64,
        "type": token_type,
        "is_transfer": is_transfer,
        "exp": int(time.time()) + expires_in,
    }
    return jwt.encode(payload, WEBAUTHN_SECRET, algorithm=ALGORITHM)


def verify_challenge_token(token: str, expected_type: str) -> Dict[str, Any]:
    """Verify challenge token signature and expiration."""
    try:
        payload = jwt.decode(token, WEBAUTHN_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise ValueError(f"Invalid token type: expected '{expected_type}', got '{payload.get('type')}'")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid or expired challenge token: {str(e)}")


def parse_and_verify_client_data(client_data_json_b64: str, expected_challenge_b64: str, expected_type: str) -> Dict[str, Any]:
    """Decode and verify clientDataJSON fields."""
    raw_json = urlsafe_b64decode(client_data_json_b64)
    try:
        client_data = json.loads(raw_json.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"Malformed clientDataJSON: {str(e)}")

    if client_data.get("type") != expected_type:
        raise ValueError(f"Expected clientData type '{expected_type}', got '{client_data.get('type')}'")

    received_challenge = client_data.get("challenge", "")
    # Normalize challenge comparisons
    norm_received = received_challenge.rstrip("=")
    norm_expected = expected_challenge_b64.rstrip("=")
    if norm_received != norm_expected:
        raise ValueError("Challenge in clientDataJSON does not match expected challenge")

    return client_data


def parse_attestation(attestation_object_b64: str) -> Tuple[str, str, Optional[str]]:
    """Parse WebAuthn attestationObject to extract credentialId, public_key (in base64url COSE format), and aaguid.

    Returns:
        (credential_id_b64, public_key_b64, aaguid_str)
    """
    raw_attestation = urlsafe_b64decode(attestation_object_b64)
    att_obj = AttestationObject(raw_attestation)
    auth_data = att_obj.auth_data

    credential_data = auth_data.credential_data
    if not credential_data:
        raise ValueError("Attestation does not contain credential data")

    credential_id_b64 = urlsafe_b64encode(credential_data.credential_id)
    public_key_bytes = cbor_encode(credential_data.public_key)
    public_key_b64 = urlsafe_b64encode(public_key_bytes)

    aaguid_bytes = credential_data.aaguid
    aaguid_str = aaguid_bytes.hex() if aaguid_bytes else None

    return credential_id_b64, public_key_b64, aaguid_str


def verify_assertion_signature(
    public_key_b64: str,
    authenticator_data_b64: str,
    client_data_json_b64: str,
    signature_b64: str,
) -> int:
    """Verify the WebAuthn authentication assertion signature with the stored public key.

    Returns:
        sign_count (int): Counter reported by the authenticator.
    """
    auth_data_bytes = urlsafe_b64decode(authenticator_data_b64)
    client_data_bytes = urlsafe_b64decode(client_data_json_b64)
    sig_bytes = urlsafe_b64decode(signature_b64)
    public_key_bytes = urlsafe_b64decode(public_key_b64)

    # 1. Parse Authenticator Data
    if len(auth_data_bytes) < 37:
        raise ValueError("Authenticator data is too short")

    # flags are at byte 32
    flags = auth_data_bytes[32]
    user_present = bool(flags & 0x01)
    if not user_present:
        raise ValueError("User Present flag (UP) is not set")

    # counter is big-endian uint32 at bytes 33:37
    sign_count = struct.unpack(">I", auth_data_bytes[33:37])[0]

    # 2. Reconstruct signed data = authData + SHA256(clientDataJSON)
    client_data_hash = hashlib.sha256(client_data_bytes).digest()
    signed_data = auth_data_bytes + client_data_hash

    # 3. Reconstruct public key and verify signature
    cose_dict = cbor_decode(public_key_bytes)
    cose_key = CoseKey.parse(cose_dict)

    try:
        cose_key.verify(signed_data, sig_bytes)
    except Exception as e:
        raise ValueError(f"Cryptographic signature verification failed: {str(e)}")

    return sign_count
