import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)

AUTH_USER = {"id": "safe_error_student", "email": "error_test@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_errors"}


@pytest.fixture(autouse=True)
def setup_auth_override():
    async def override_user(authorization=None):
        return AUTH_USER

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


def parse_sse_events(response_text: str):
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    return events


def test_model_timeout_returns_safe_message(monkeypatch):
    """
    Verification: Force a model timeout.
    Confirm the client sees only safe messages while internal details are masked.
    """
    from app.core_backend.routes import tutor as tutor_route

    # Mock model to simulate a TimeoutError
    def mock_generate_content(*args, **kwargs):
        raise TimeoutError("Deadline exceeded on upstream host 10.128.0.4:443 after 30000ms")

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = mock_generate_content
    monkeypatch.setattr(tutor_route.tutor_service, "model", mock_model)

    payload = {"prompt": "Explain quantum mechanics"}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    assert len(events) > 0

    error_event = next(e for e in events if "error" in e)
    assert "error" in error_event
    assert "The tutor took too long to respond." in error_event["error"]
    assert "request_id" in error_event
    assert error_event["status"] == "error"

    # CRITICAL: Confirm internal IP, port, or exception details are NOT leaked to the client
    assert "10.128.0.4" not in response.text
    assert "Deadline exceeded" not in response.text


def test_database_exception_is_masked(monkeypatch):
    """
    Verification: Force a database exception during memory retrieval.
    Confirm that internal database connection strings, credentials, or socket errors are NOT leaked.
    """
    from app.core_backend.routes import tutor as tutor_route

    # Force database search to raise an internal database error
    def mock_db_error(*args, **kwargs):
        raise RuntimeError("FATAL: connection to postgresql://postgres:SecretPassword123@10.0.0.12:5432 failed")

    monkeypatch.setattr(tutor_route.tutor_service.db, "search_memories", mock_db_error)

    # Mock model response so tutor continues gracefully
    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Hello! Let's explore physics."
    mock_model.generate_content.return_value = [mock_chunk]
    monkeypatch.setattr(tutor_route.tutor_service, "model", mock_model)

    payload = {"prompt": "What is momentum?"}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200

    # CRITICAL: Ensure internal database password, IP, and postgres string are NOT leaked
    assert "SecretPassword123" not in response.text
    assert "10.0.0.12" not in response.text
    assert "FATAL" not in response.text


def test_unexpected_raw_exception_masked(monkeypatch):
    """
    Verification: Force an unexpected internal exception with sensitive paths/keys.
    Confirm the client receives only a structured, generic message.
    """
    from app.core_backend.routes import tutor as tutor_route

    def mock_fatal_error(*args, **kwargs):
        raise Exception("Internal crash in /var/secrets/api_keys.json: Invalid token AIzaSyDummyKeyXYZ123")

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = mock_fatal_error
    monkeypatch.setattr(tutor_route.tutor_service, "model", mock_model)

    payload = {"prompt": "Tell me about friction"}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    assert len(events) > 0

    error_event = next(e for e in events if "error" in e)
    assert error_event.get("error") == "The tutor is temporarily unavailable."
    assert "request_id" in error_event

    # Confirm sensitive paths and mock keys are NOT exposed
    assert "/var/secrets" not in response.text
    assert "AIzaSyDummyKeyXYZ123" not in response.text

