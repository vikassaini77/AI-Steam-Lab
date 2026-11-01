"""
Unit and integration security tests for Problem 5:
Logout Session Revocation & Error Observability.

Verifies:
1. Logout requires a valid, authenticated Bearer token (rejects missing/invalid tokens with 401).
2. Logout passes the caller's specific JWT access token to Supabase Auth revocation operation.
3. Session revocation is verified and recorded locally in token revocation registry.
4. Subsequent requests using the revoked token are immediately rejected with 401.
5. Logout failures are not silently swallowed: recorded in structured logs and trigger alerts.
"""
import time
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import jwt
from supabase_auth.errors import AuthApiError

from app.main import app
from app.core_backend.core.dependencies import reset_shared_dependencies
from app.core_backend.core.token_revocation import is_token_revoked, clear_revoked_tokens
from app.core_backend.core.observability import alert_manager
from app.core_backend.routes import auth as auth_route

client = TestClient(app)

SECRET_KEY = "test-mock-jwt-secret-at-least-32-chars-long"
ISSUER = "https://mock-supabase.test/auth/v1"
AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def clean_auth_state(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET_KEY)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("SUPABASE_JWT_VERIFY_ISSUER", "true")
    reset_shared_dependencies()
    clear_revoked_tokens()
    alert_manager.clear()
    yield
    reset_shared_dependencies()
    clear_revoked_tokens()
    alert_manager.clear()


def generate_test_token(user_id: str = "user_student_123", email: str = "student@neurolab.ai") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "role": "authenticated",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def test_logout_without_token_returns_401():
    """Unauthenticated requests to /logout must be rejected with 401."""
    res = client.post("/api/auth/logout")
    assert res.status_code == 401
    assert "Authorization header" in res.json().get("detail", "")


def test_logout_with_invalid_token_returns_401():
    """Requests to /logout with malformed tokens must be rejected with 401."""
    res = client.post("/api/auth/logout", headers={"Authorization": "Bearer invalid.fake.token"})
    assert res.status_code == 401


def test_logout_passes_caller_token_to_supabase_sign_out(monkeypatch):
    """
    Validates that logout invokes Supabase Auth revocation operation
    with the exact authenticated caller's access token.
    """
    mock_sb = MagicMock()
    mock_sb.auth.admin.sign_out.return_value = None
    mock_sb.auth.get_user.side_effect = Exception("Session revoked")
    monkeypatch.setattr(auth_route, "get_supabase_client", lambda: mock_sb)

    token = generate_test_token("user_alice_456", "alice@neurolab.ai")
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["session_revoked"] is True

    # Confirm admin.sign_out was called with the caller's JWT token
    mock_sb.auth.admin.sign_out.assert_called_once_with(jwt=token, scope="global")


def test_revoked_session_token_is_rejected_on_subsequent_requests(monkeypatch):
    """
    Verifies that after successful logout:
    1. Token is marked revoked in registry.
    2. Any subsequent protected request using that token is rejected with 401.
    """
    mock_sb = MagicMock()
    mock_sb.auth.admin.sign_out.return_value = None
    mock_sb.auth.get_user.side_effect = Exception("Session revoked")
    monkeypatch.setattr(auth_route, "get_supabase_client", lambda: mock_sb)

    token = generate_test_token("user_bob_789", "bob@neurolab.ai")
    auth_header = {"Authorization": f"Bearer {token}"}

    # Step 1: User accesses protected route successfully before logout
    res_before = client.get("/api/auth/me", headers=auth_header)
    assert res_before.status_code == 200
    assert res_before.json()["user"]["id"] == "user_bob_789"

    # Step 2: User logs out
    res_logout = client.post("/api/auth/logout", headers=auth_header)
    assert res_logout.status_code == 200
    assert is_token_revoked(token) is True

    # Step 3: Subsequent request with the same token must be rejected with 401
    res_after = client.get("/api/auth/me", headers=auth_header)
    assert res_after.status_code == 401
    assert "revoked" in res_after.json().get("detail", "").lower()


def test_logout_failure_is_recorded_and_not_silently_swallowed(monkeypatch):
    """
    Verifies that upstream Supabase revocation failures are NOT silently swallowed:
    1. Error is logged and triggers an alert.
    2. Endpoint returns 502 reporting failure rather than dummy success.
    """
    mock_sb = MagicMock()
    # Simulate upstream network/provider failure
    mock_sb.auth.admin.sign_out.side_effect = Exception("Connection refused by auth provider")
    monkeypatch.setattr(auth_route, "get_supabase_client", lambda: mock_sb)

    token = generate_test_token("user_charlie_111", "charlie@neurolab.ai")
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # Must NOT return 200 dummy success
    assert res.status_code == 502
    assert "revocation failed" in res.json().get("detail", "").lower()

    # Confirms alert was recorded in alert_manager
    assert alert_manager.is_alert_active("AUTH_LOGOUT_REVOCATION_FAILURE") is True
    alert = alert_manager.get_active_alerts()[0]
    assert alert["name"] == "AUTH_LOGOUT_REVOCATION_FAILURE"
    assert "Connection refused" in alert["message"]


def test_logout_handles_already_expired_session_gracefully(monkeypatch):
    """
    When the session was already expired/terminated on provider,
    logout logs the information and ensures local token blacklist without crashing.
    """
    mock_sb = MagicMock()
    # Supabase AuthApiError indicating session not found
    api_error = AuthApiError(message="session not found or already terminated", status=404, code="session_not_found")
    mock_sb.auth.admin.sign_out.side_effect = api_error
    monkeypatch.setattr(auth_route, "get_supabase_client", lambda: mock_sb)

    token = generate_test_token("user_dan_222", "dan@neurolab.ai")
    res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert is_token_revoked(token) is True
