"""
Tests for Supabase Multi-Factor Authentication (MFA / TOTP) Endpoints.
Verifies enrollment, verification, factor listing, unenrollment, and auth guards.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

AUTH_HEADER = {"Authorization": "Bearer mock-test-token-valid-sub"}


@pytest.fixture(autouse=True)
def bypass_jwt_for_mfa(monkeypatch):
    """Mocks JWT decode to return a valid canonical test user."""
    from app.core_backend.core.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"id": "test_user_mfa_123", "email": "mfa@neurolab.test"}
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_mfa_endpoints_require_authentication():
    """MFA endpoints must reject unauthenticated requests with 401 Unauthorized."""
    res_enroll = client.post("/api/auth/mfa/enroll")
    assert res_enroll.status_code == 401

    res_verify = client.post("/api/auth/mfa/verify", json={"factor_id": "fac_123", "code": "123456"})
    assert res_verify.status_code == 401

    res_factors = client.get("/api/auth/mfa/factors")
    assert res_factors.status_code == 401

    res_unenroll = client.delete("/api/auth/mfa/factors/fac_123")
    assert res_unenroll.status_code == 401


def test_mfa_list_factors_empty():
    """Listing factors for a user without MFA returns empty list."""
    mock_supabase = MagicMock()
    mock_supabase.auth.mfa.list_factors.return_value = MagicMock(all=[])

    with patch("app.core_backend.routes.auth.get_supabase_client", return_value=mock_supabase):
        res = client.get("/api/auth/mfa/factors", headers=AUTH_HEADER)
        assert res.status_code == 200
        data = res.json()
        assert data["factors"] == []
        assert data["has_verified_factor"] is False


def test_mfa_enrollment_success():
    """Enrolling MFA generates factor ID, QR code, and secret."""
    mock_supabase = MagicMock()
    mock_res = MagicMock()
    mock_res.id = "factor_test_abc"
    mock_res.type = "totp"
    mock_res.totp.qr_code = "data:image/svg+xml;utf8,<svg></svg>"
    mock_res.totp.secret = "JBSWY3DPEHPK3PXP"
    mock_res.totp.uri = "otpauth://totp/NeuroLab%20AI:student?secret=JBSWY3DPEHPK3PXP"
    mock_supabase.auth.mfa.enroll.return_value = mock_res

    with patch("app.core_backend.routes.auth.get_supabase_client", return_value=mock_supabase):
        res = client.post("/api/auth/mfa/enroll", headers=AUTH_HEADER, json={"issuer": "NeuroLab AI"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["id"] == "factor_test_abc"
        assert data["totp"]["secret"] == "JBSWY3DPEHPK3PXP"
        assert "<svg>" in data["totp"]["qr_code"]


def test_mfa_verify_success():
    """Submitting valid 6-digit TOTP code verifies the challenge and factor."""
    mock_supabase = MagicMock()
    mock_supabase.auth.mfa.challenge_and_verify.return_value = MagicMock()

    with patch("app.core_backend.routes.auth.get_supabase_client", return_value=mock_supabase):
        res = client.post(
            "/api/auth/mfa/verify",
            headers=AUTH_HEADER,
            json={"factor_id": "factor_test_abc", "code": "654321"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "verified"
        assert data["factor_id"] == "factor_test_abc"


def test_mfa_unenroll_success():
    """Un-enrolling removes the factor."""
    mock_supabase = MagicMock()
    mock_supabase.auth.mfa.unenroll.return_value = MagicMock()

    with patch("app.core_backend.routes.auth.get_supabase_client", return_value=mock_supabase):
        res = client.delete("/api/auth/mfa/factors/factor_test_abc", headers=AUTH_HEADER)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["factor_id"] == "factor_test_abc"

