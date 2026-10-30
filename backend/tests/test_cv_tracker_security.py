import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)

AUTH_USER = {"id": "user_cv_test", "email": "cv_student@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_cv"}


@pytest.fixture(autouse=True)
def setup_auth_override():
    async def override_user(authorization=None):
        return AUTH_USER

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


def test_missing_authentication_rejected():
    """
    Verification: Requests with missing authentication must be rejected with 401.
    """
    app.dependency_overrides.clear()
    payload = {"state": "focused", "confidence": 0.9}
    response = client.post("/api/cv/engagement", json=payload)
    assert response.status_code == 401


def test_negative_confidence_rejected():
    """
    Verification: Requests with confidence -1 should be rejected (422).
    """
    payload = {"state": "focused", "confidence": -1.0}
    response = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_excessive_confidence_rejected():
    """
    Verification: Requests with confidence 2.0 should be rejected (422).
    """
    payload = {"state": "focused", "confidence": 2.0}
    response = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_unknown_state_rejected():
    """
    Verification: Requests with unknown states should be rejected (422).
    """
    payload = {"state": "sleeping_at_desk", "confidence": 0.8}
    response = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_valid_states_accepted():
    """
    Verification: All allowed Literal states with valid confidence [0.0, 1.0] are accepted.
    """
    for state in ["focused", "confused", "leaning_forward", "disengaged"]:
        payload = {"state": state, "confidence": 0.75}
        response = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        event = data["event"]
        assert event["state"] == state
        assert event["confidence"] == 0.75
        assert event["user_id"] == AUTH_USER["id"]
        assert event["is_estimate"] is True
        assert "disclaimer" in event
        assert "recorded_at" in event
        assert "model_version" in event


def test_spoofed_user_id_rejected_with_403():
    """
    Verification: A client cannot supply another user's ID in the request body.
    """
    payload = {
        "user_id": "different_victim_user_id",
        "state": "focused",
        "confidence": 0.95,
    }
    response = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 403
    assert "Forbidden" in response.json().get("detail", "")


def test_oversized_payload_rejected():
    """
    Verification: Oversized requests exceeding the size limit should be rejected with 413.
    """
    headers = {**AUTH_HEADERS, "Content-Length": "20000"}
    payload = {"state": "focused", "confidence": 0.85, "metadata": {"blob": "x" * 15000}}
    response = client.post("/api/cv/engagement", json=payload, headers=headers)
    assert response.status_code == 413

