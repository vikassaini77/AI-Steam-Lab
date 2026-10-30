import time
import pytest
from fastapi.testclient import TestClient
import jwt
from app.main import app

client = TestClient(app)


def test_missing_credentials_returns_401():
    """
    Test 1: Try accessing a protected endpoint without credentials -> Expect 401.
    """
    # Test protected /api/auth/me
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json().get("detail", "")

    # Test protected /api/experiments/history
    response = client.get("/api/experiments/history")
    assert response.status_code == 401
    assert "Missing Authorization header" in response.json().get("detail", "")

    # Test malformed Authorization header (no Bearer prefix)
    response = client.get("/api/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401
    assert "Expected 'Bearer <token>'" in response.json().get("detail", "")


def test_invalid_token_returns_401():
    """
    Test 2: Send an invalid token to a protected endpoint -> Expect 401.
    """
    # Completely dummy / malformed token
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer dummy_invalid_token_xyz"})
    assert response.status_code == 401

    # Malformed JWT segments
    response = client.get("/api/experiments/history", headers={"Authorization": "Bearer not.a.real.jwt"})
    assert response.status_code == 401


def test_expired_token_returns_401():
    """
    Test 3: Send an expired token to a protected endpoint -> Expect 401.
    """
    # Create a properly structured JWT with an expired timestamp (exp in the past)
    expired_payload = {
        "sub": "user_12345",
        "email": "student@neurolab.ai",
        "aud": "authenticated",
        "exp": int(time.time()) - 3600,  # 1 hour ago
        "iat": int(time.time()) - 7200,
    }
    expired_jwt = jwt.encode(expired_payload, "some_secret_key_long_enough_for_hs256_32bytes", algorithm="HS256")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_jwt}"})
    assert response.status_code == 401
    assert "expired" in response.json().get("detail", "").lower()


def test_login_with_invalid_credentials_returns_401():
    """
    Test 4: Invalid credentials through Supabase Auth must return 401 (not dummy success).
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent_student_9999@neurolab.ai", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert "Authentication failed" in response.json().get("detail", "")


def test_resource_ownership_enforcement_returns_403():
    """
    Test 5: An authenticated user attempting to modify or access another user's resource
    must receive 403 Forbidden.
    """
    from app.core_backend.core.dependencies import get_current_user

    async def mock_current_user(authorization=None):
        return {"id": "user_alice", "email": "alice@neurolab.ai", "role": "authenticated"}

    app.dependency_overrides[get_current_user] = mock_current_user

    try:
        headers = {"Authorization": "Bearer valid_mock_token"}
        # User Alice tries to view user Bob's history
        response = client.get("/api/experiments/history?user_id=user_bob", headers=headers)
        assert response.status_code == 403
        assert "Forbidden" in response.json().get("detail", "")

        # User Alice tries to award XP to user Bob
        response = client.post(
            "/api/gamification/add-xp",
            json={"user_id": "user_bob", "action": "solve_puzzle", "amount": 100},
            headers=headers,
        )
        assert response.status_code == 403
        assert "Forbidden" in response.json().get("detail", "")

        # User Alice views her own history -> succeeds (200)
        response = client.get("/api/experiments/history?user_id=user_alice", headers=headers)
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
