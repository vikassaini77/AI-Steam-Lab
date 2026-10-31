import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import get_user_or_ip_identifier, limiter

client = TestClient(app)

TEST_USER = {"id": "rate_limited_student_1", "email": "ratelimit@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_rate_limit"}


@pytest.fixture(autouse=True)
def setup_auth_and_clean_limits():
    async def override_user(authorization=None):
        return TEST_USER

    app.dependency_overrides[get_current_user] = override_user
    limiter.reset()
    yield
    app.dependency_overrides.clear()
    limiter.reset()


def test_excessive_prompt_length_rejected():
    """
    Verification: Prompt length capped at 2,000 characters.
    Requests with prompts exceeding 2,000 chars must be rejected with 422.
    """
    huge_prompt = "What is gravity? " * 200  # > 3,000 characters
    payload = {"prompt": huge_prompt}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_rate_limit_exceeded_returns_429(monkeypatch):
    """
    Verification: Load test demonstrating that excessive requests to an expensive endpoint
    are rejected with 429 Too Many Requests without exhausting resources.
    """
    from app.core_backend.routes import auth as auth_route
    from unittest.mock import MagicMock

    # Mock supabase client so tests do not rely on external network calls
    mock_sb = MagicMock()
    mock_sb.auth.sign_up.return_value = MagicMock(user=MagicMock(id="123", email="test@test.com"), session=None)
    monkeypatch.setattr(auth_route, "get_supabase_client", lambda: mock_sb)

    url = "/api/auth/register"
    payload = {"email": "spam_register@neurolab.ai", "password": "Password123!"}

    statuses = []
    # Fire 10 rapid requests (limit is 5/minute)
    for _ in range(10):
        res = client.post(url, json=payload)
        statuses.append(res.status_code)

    # Confirm that at least one of the requests was throttled with 429
    assert 429 in statuses, f"Expected 429 Too Many Requests, got statuses: {statuses}"


def test_daily_tutor_budget_exceeded_returns_429():
    """
    Verification: Enforces daily request budgets per user.
    When daily quota is exceeded, returns 429 Too Many Requests.
    """
    from app.core_backend.routes.tutor import db
    from app.core_backend.database.supabase_db import db_lock

    # Artificially set user's daily usage to maximum (100)
    user_id = TEST_USER["id"]
    import time
    today_key = time.strftime("%Y-%m-%d", time.gmtime())
    with db_lock:
        data = db._read_local()
        if "daily_usage" not in data:
            data["daily_usage"] = {}
        data["daily_usage"][user_id] = {today_key: 100}
        db._write_local(data)

    payload = {"prompt": "What is inertia?"}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 429
    assert "Daily AI tutor request quota exceeded" in response.json().get("detail", "")


def test_trusted_proxy_ip_handling_security():
    """
    Verification: Reverse proxy handling.
    Ensure get_user_or_ip_identifier ignores spoofed headers from untrusted clients
    and respects trusted proxy forwards.
    """
    from starlette.datastructures import Headers
    from unittest.mock import MagicMock

    # 1. Untrusted client attempting to spoof X-Forwarded-For
    untrusted_req = MagicMock()
    untrusted_req.headers = Headers({"x-forwarded-for": "1.1.1.1, 2.2.2.2"})
    untrusted_req.client = MagicMock(host="203.0.113.50")  # Public untrusted IP

    ident = get_user_or_ip_identifier(untrusted_req)
    assert ident == "ip:203.0.113.50", "Must NOT trust X-Forwarded-For from untrusted remote host"

    # 2. Trusted internal proxy (e.g. 127.0.0.1 or Nginx docker subnet)
    trusted_req = MagicMock()
    trusted_req.headers = Headers({"x-forwarded-for": "198.51.100.25, 127.0.0.1"})
    trusted_req.client = MagicMock(host="127.0.0.1")  # Trusted localhost proxy

    ident_trusted = get_user_or_ip_identifier(trusted_req)
    assert ident_trusted == "ip:198.51.100.25", "Must extract real client IP when forwarded by trusted proxy"
