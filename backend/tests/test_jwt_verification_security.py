"""
Unit and integration security tests for Supabase JWT verification:
1. Strict claim verification (iss, aud, sub, exp, iat).
2. Algorithm enforcement (disallows 'none' and unauthorized algorithms).
3. Multi-secret symmetric key rotation.
4. Asymmetric signing support (RS256).
5. Protected route authentication via get_current_user.
"""
import time
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.core_backend.core.jwt_verifier import SupabaseJWTVerifier
from app.core_backend.core.dependencies import get_current_user, reset_shared_dependencies

client = TestClient(app)

SECRET_PRIMARY = "primary-secret-key-at-least-64-bytes-long-for-all-hmac-sha-algorithms-abc1234567890"
SECRET_SECONDARY = "secondary-secret-key-at-least-64-bytes-long-for-all-hmac-sha-algorithms-xyz1234567890"
EXPECTED_ISSUER = "https://mock-supabase.test/auth/v1"
EXPECTED_AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def clean_verifier():
    reset_shared_dependencies()
    yield
    reset_shared_dependencies()


def create_token(
    payload: dict,
    secret: str = SECRET_PRIMARY,
    algorithm: str = "HS256",
    headers: dict = None,
) -> str:
    """Helper to generate JWTs with sensible defaults."""
    default_payload = {
        "sub": "user_12345",
        "email": "student@neurolab.ai",
        "aud": EXPECTED_AUDIENCE,
        "iss": EXPECTED_ISSUER,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "role": "authenticated",
        "user_metadata": {"full_name": "Test Student"},
    }
    merged = {**default_payload, **payload}
    return jwt.encode(merged, secret, algorithm=algorithm, headers=headers)


def test_valid_token_decodes_successfully():
    """Valid token with all required claims (iss, aud, sub, exp, iat) succeeds."""
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=EXPECTED_AUDIENCE,
        verify_issuer=True,
        verify_audience=True,
    )
    token = create_token({"sub": "student_abc", "email": "alice@neurolab.ai"})
    user = verifier.verify_token(token)

    assert user["id"] == "student_abc"
    assert user["email"] == "alice@neurolab.ai"
    assert user["role"] == "authenticated"
    assert user["metadata"]["full_name"] == "Test Student"


def test_missing_or_blank_sub_claim_rejected():
    """Token missing 'sub' or containing blank whitespace is rejected with 401."""
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=EXPECTED_AUDIENCE,
    )

    # 1. Missing sub claim
    bad_payload = {
        "email": "student@neurolab.ai",
        "aud": EXPECTED_AUDIENCE,
        "iss": EXPECTED_ISSUER,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token_no_sub = jwt.encode(bad_payload, SECRET_PRIMARY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_no_sub)
    assert exc_info.value.status_code == 401
    assert "sub" in exc_info.value.detail.lower()

    # 2. Blank/whitespace sub claim
    token_blank_sub = create_token({"sub": "   "})
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_blank_sub)
    assert exc_info.value.status_code == 401
    assert "sub" in exc_info.value.detail.lower()


def test_invalid_issuer_rejected():
    """Token signed with an unauthorized or spoofed issuer is rejected with 401."""
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        expected_issuer=EXPECTED_ISSUER,
        verify_issuer=True,
    )

    # 1. Mismatched issuer
    token_spoofed_iss = create_token({"iss": "https://malicious-auth.attacker.io/auth/v1"})
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_spoofed_iss)
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower()

    # 2. Missing issuer when verify_issuer=True
    bad_payload = {
        "sub": "user_12345",
        "aud": EXPECTED_AUDIENCE,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token_no_iss = jwt.encode(bad_payload, SECRET_PRIMARY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_no_iss)
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower() or "iss" in exc_info.value.detail.lower()


def test_invalid_audience_rejected():
    """Token with missing or incorrect audience is rejected with 401."""
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        expected_audience="authenticated",
        verify_audience=True,
    )

    # 1. Wrong audience
    token_wrong_aud = create_token({"aud": "public-anonymous"})
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_wrong_aud)
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower()

    # 2. Missing audience
    bad_payload = {
        "sub": "user_12345",
        "iss": EXPECTED_ISSUER,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token_no_aud = jwt.encode(bad_payload, SECRET_PRIMARY, algorithm="HS256")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_no_aud)
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower() or "aud" in exc_info.value.detail.lower()


def test_future_issued_at_rejected():
    """Token issued in the future (iat > now + leeway) is rejected with 401."""
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        leeway=5.0,
    )
    future_iat = int(time.time()) + 120  # 2 minutes in future > 5s leeway
    token_future = create_token({"iat": future_iat, "exp": future_iat + 3600})
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_future)
    assert exc_info.value.status_code == 401
    assert "iat" in exc_info.value.detail.lower() or "future" in exc_info.value.detail.lower()


def test_iat_after_exp_rejected():
    """Token where iat is later than exp is rejected with 401."""
    verifier = SupabaseJWTVerifier(secrets=[SECRET_PRIMARY])
    token_bad_timeline = create_token({"iat": int(time.time()) + 10, "exp": int(time.time()) + 5})
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_bad_timeline)
    assert exc_info.value.status_code == 401
    assert "exp" in exc_info.value.detail.lower() or "iat" in exc_info.value.detail.lower()


def test_algorithm_none_strictly_forbidden():
    """Unsigned tokens ('none' algorithm) are unconditionally rejected."""
    verifier = SupabaseJWTVerifier(secrets=[SECRET_PRIMARY])

    import base64
    import json

    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "attacker", "exp": int(time.time()) + 3600}).encode()).decode().rstrip("=")
    unsigned_token = f"{header}.{payload}."

    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(unsigned_token)
    assert exc_info.value.status_code == 401
    assert "none" in exc_info.value.detail.lower()


def test_disallowed_algorithm_rejected():
    """Tokens signed with algorithms outside the approved whitelist are rejected."""
    # Verifier only permits HS256
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY],
        allowed_algorithms=["HS256"],
    )
    # Generate token with HS384
    token_hs384 = create_token({}, algorithm="HS384")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_hs384)
    assert exc_info.value.status_code == 401
    assert "disallowed" in exc_info.value.detail.lower() or "algorithm" in exc_info.value.detail.lower()


def test_symmetric_key_rotation():
    """
    Validates zero-downtime key rotation:
    Tokens signed with either active or rotated secondary keys are successfully verified.
    Tokens signed with revoked/unknown keys are rejected.
    """
    verifier = SupabaseJWTVerifier(
        secrets=[SECRET_PRIMARY, SECRET_SECONDARY],
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=EXPECTED_AUDIENCE,
    )

    # 1. Token signed with primary (active) secret
    token_primary = create_token({"sub": "student_1"}, secret=SECRET_PRIMARY)
    user1 = verifier.verify_token(token_primary)
    assert user1["id"] == "student_1"

    # 2. Token signed with secondary (older/rotated) secret
    token_secondary = create_token({"sub": "student_2"}, secret=SECRET_SECONDARY)
    user2 = verifier.verify_token(token_secondary)
    assert user2["id"] == "student_2"

    # 3. Token signed with unknown/revoked secret
    token_revoked = create_token({"sub": "student_3"}, secret="revoked-secret-key-32-chars-000000")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_revoked)
    assert exc_info.value.status_code == 401
    assert "signature" in exc_info.value.detail.lower()


def test_key_rotation_with_kid_header():
    """Validates key selection and verification when 'kid' is specified in header."""
    keys_by_kid = {
        "key-2026-01": SECRET_PRIMARY,
        "key-2025-12": SECRET_SECONDARY,
    }
    verifier = SupabaseJWTVerifier(
        keys_by_kid=keys_by_kid,
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=EXPECTED_AUDIENCE,
    )

    token_v1 = create_token({"sub": "kid_user_1"}, secret=SECRET_PRIMARY, headers={"kid": "key-2026-01"})
    assert verifier.verify_token(token_v1)["id"] == "kid_user_1"

    token_v2 = create_token({"sub": "kid_user_2"}, secret=SECRET_SECONDARY, headers={"kid": "key-2025-12"})
    assert verifier.verify_token(token_v2)["id"] == "kid_user_2"


def test_asymmetric_rs256_verification():
    """Validates RS256 token signing and verification using public keys."""
    # Generate RSA keypair for testing
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    verifier = SupabaseJWTVerifier(
        public_keys=[public_pem],
        allowed_algorithms=["RS256"],
        expected_issuer=EXPECTED_ISSUER,
        expected_audience=EXPECTED_AUDIENCE,
    )

    token_rs256 = create_token({"sub": "rsa_user_1"}, secret=private_pem, algorithm="RS256")
    user = verifier.verify_token(token_rs256)
    assert user["id"] == "rsa_user_1"

    # Mismatched RSA key should fail
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    token_mismatched_rsa = create_token({"sub": "rsa_user_2"}, secret=other_pem, algorithm="RS256")
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify_token(token_mismatched_rsa)
    assert exc_info.value.status_code == 401


def test_fastapi_protected_route_integration(monkeypatch):
    """Integration test: FastAPI /api/auth/me accepts valid tokens and rejects invalid ones."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET_PRIMARY)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", EXPECTED_ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", EXPECTED_AUDIENCE)
    monkeypatch.setenv("SUPABASE_JWT_VERIFY_ISSUER", "true")
    reset_shared_dependencies()

    # 1. Valid token succeeds with 200
    valid_token = create_token({"sub": "e2e_student_99", "email": "e2e@neurolab.ai"})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["id"] == "e2e_student_99"
    assert data["user"]["email"] == "e2e@neurolab.ai"

    # 2. Token with wrong issuer fails with 401
    bad_iss_token = create_token({"iss": "https://wrong-issuer.com"})
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad_iss_token}"})
    assert res.status_code == 401
    assert "issuer" in res.json().get("detail", "").lower()

    # 3. Token with missing sub fails with 401
    bad_payload = {
        "email": "e2e@neurolab.ai",
        "aud": EXPECTED_AUDIENCE,
        "iss": EXPECTED_ISSUER,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    no_sub_token = jwt.encode(bad_payload, SECRET_PRIMARY, algorithm="HS256")
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {no_sub_token}"})
    assert res.status_code == 401
    assert "sub" in res.json().get("detail", "").lower()
