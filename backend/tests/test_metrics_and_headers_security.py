import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TEST_METRICS_TOKEN = "test_metrics_secret_key_123"


@pytest.fixture(autouse=True)
def setup_metrics_env(monkeypatch):
    """Setup clean test environment for metrics and security headers."""
    monkeypatch.setenv("METRICS_TOKEN", TEST_METRICS_TOKEN)
    monkeypatch.setenv("METRICS_ALLOW_INTERNAL_NETWORKS", "true")
    monkeypatch.setenv("METRICS_REQUIRE_AUTH", "false")
    monkeypatch.delenv("ENABLE_HSTS", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def test_public_unauthenticated_metrics_access_rejected(monkeypatch):
    """
    Public unauthenticated requests from untrusted external IPs must be rejected with 401.
    """
    # Simulate an external public IP coming through reverse proxy
    headers = {"X-Forwarded-For": "198.51.100.45"}
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"] or "restricted" in response.json()["detail"].lower()


def test_invalid_metrics_token_rejected(monkeypatch):
    """
    Requests with an invalid Bearer token must be rejected with 401.
    """
    headers = {
        "Authorization": "Bearer completely_wrong_token",
        "X-Forwarded-For": "198.51.100.45",
    }
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_valid_metrics_token_granted(monkeypatch):
    """
    Requests with a valid monitoring Bearer token must be granted 200 OK.
    """
    headers = {
        "Authorization": f"Bearer {TEST_METRICS_TOKEN}",
        "X-Forwarded-For": "198.51.100.45",
    }
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 200
    assert "process_cpu_seconds_total" in response.text or "python_gc_objects_collected_total" in response.text or "# HELP" in response.text


def test_valid_metrics_api_key_header_granted(monkeypatch):
    """
    Requests with a valid X-Metrics-Key header must also be granted 200 OK.
    """
    headers = {
        "X-Metrics-Key": TEST_METRICS_TOKEN,
        "X-Forwarded-For": "198.51.100.45",
    }
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 200


def test_internal_monitoring_network_granted(monkeypatch):
    """
    Requests originating from whitelisted internal networks (e.g. 10.0.0.0/8) are permitted.
    """
    headers = {"X-Forwarded-For": "10.244.0.15"}
    response = client.get("/metrics", headers=headers)
    assert response.status_code == 200


def test_metrics_strict_auth_mode_rejects_unauthenticated_localhost(monkeypatch):
    """
    When METRICS_REQUIRE_AUTH is true, even localhost/internal traffic requires a token.
    """
    monkeypatch.setenv("METRICS_REQUIRE_AUTH", "true")
    response = client.get("/metrics")
    assert response.status_code == 401
    assert "requires authentication token" in response.json()["detail"].lower()


def test_security_headers_present_on_response():
    """
    Verifies that all required modern browser security headers are present.
    """
    response = client.get("/")
    assert response.status_code == 200

    # 1. Content Type Options
    assert response.headers.get("X-Content-Type-Options") == "nosniff"

    # 2. Referrer Policy
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # 3. Permissions Policy (Camera allowed for CV tracker, others restricted)
    perm_policy = response.headers.get("Permissions-Policy", "")
    assert "camera=(self)" in perm_policy
    assert "microphone=()" in perm_policy

    # 4. Content Security Policy & Frame Ancestors
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'self' https://huggingface.co https://*.huggingface.co https://ai-steam-lab.vercel.app" in csp
    assert "connect-src" in csp
    assert "https://*.supabase.co" in csp

    # 5. Obsolete header removed
    assert "X-XSS-Protection" not in response.headers


def test_hsts_omitted_on_plain_http():
    """
    Strict-Transport-Security must be omitted on plain HTTP to prevent local dev browser issues.
    """
    response = client.get("http://testserver/")
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_enforced_over_https():
    """
    Strict-Transport-Security must be sent when requests arrive over HTTPS edge.
    """
    response = client.get("/", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    hsts = response.headers.get("Strict-Transport-Security")
    assert hsts is not None
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts

