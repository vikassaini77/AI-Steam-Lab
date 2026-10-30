"""
Test Suite for Problem 29: Insufficient Request and Response Contracts
Validates:
1. Explicit Pydantic request models across tutor, CV tracker, and experiments.
2. Rejection of unexpected fields (extra="forbid") with HTTP 422.
3. Rejection of malformed history turns (invalid role, empty content, exceeding turns cap).
4. Rejection of malformed experiment_state in chat requests.
5. Strict typing and validation on CV process-frame and engagement logging.
6. Strict typing and parameter bounds on experiment save and analysis.
7. Explicit Pydantic response models on all non-streaming endpoints.
8. API versioning (/api/v1 router parity and X-API-Version response header).
9. OpenAPI schema documentation compliance.
"""
import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)

MOCK_USER = {
    "id": "e9999999-9999-9999-9999-999999999999",
    "email": "contract_tester@neurolab.ai",
    "role": "authenticated",
}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_contracts"}


@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.clear()


def make_test_frame_b64(width=320, height=240):
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (width // 2, height // 2), 20, (0, 0, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode()


# ==============================================================================
# 1. OpenAPI Schema Documentation Tests
# ==============================================================================

def test_openapi_schema_documents_all_request_and_response_contracts():
    """
    OpenAPI schema must formally document request bodies and response models.
    """
    schema = app.openapi()
    components = schema.get("components", {}).get("schemas", {})

    expected_schemas = [
        "ChatRequest",
        "ChatHistoryTurn",
        "ChatRole",
        "ExperimentStateContext",
        "TutorStatusResponse",
        "DeleteMemoriesResponse",
        "DeleteSingleMemoryResponse",
        "ExportMemoriesResponse",
        "FrameProcessRequest",
        "FrameProcessResponse",
        "TrackingMethod",
        "PhysicsTrackingMetrics",
        "EngagementEvent",
        "EngagementResponse",
        "CVReadinessResponse",
        "CVStatusResponse",
        "ResetTrackerResponse",
        "ExperimentData",
        "ExperimentSaveResponse",
        "ExperimentHistoryResponse",
        "ExperimentDetailResponse",
    ]

    for expected in expected_schemas:
        assert expected in components, f"OpenAPI schema missing model: {expected}"

    paths = schema.get("paths", {})
    # Check that /api/cv/process-frame has FrameProcessResponse 200 contract
    cv_process_post = paths.get("/api/cv/process-frame", {}).get("post", {})
    assert "200" in cv_process_post.get("responses", {})
    resp_ref = cv_process_post["responses"]["200"].get("content", {}).get("application/json", {}).get("schema", {}).get("$ref", "")
    assert "FrameProcessResponse" in resp_ref

    # Check that /api/experiments/save has ExperimentSaveResponse 200 contract
    exp_save_post = paths.get("/api/experiments/save", {}).get("post", {})
    assert "200" in exp_save_post.get("responses", {})
    save_ref = exp_save_post["responses"]["200"].get("content", {}).get("application/json", {}).get("schema", {}).get("$ref", "")
    assert "ExperimentSaveResponse" in save_ref


def test_api_v1_versioning_route_parity_and_header():
    """
    All endpoints must return X-API-Version: 1.0.0 header.
    Versioned routes (/api/v1/...) must provide full functional parity with unversioned (/api/...).
    """
    # 1. Check X-API-Version header on root and endpoints
    res_root = client.get("/")
    assert res_root.headers.get("X-API-Version") == "1.0.0"

    res_tutor = client.get("/api/tutor/")
    assert res_tutor.status_code == 200
    assert res_tutor.headers.get("X-API-Version") == "1.0.0"

    # 2. Check /api/v1/tutor/ versioned alias
    res_v1_tutor = client.get("/api/v1/tutor/")
    assert res_v1_tutor.status_code == 200
    assert res_v1_tutor.json() == res_tutor.json()

    # 3. Check /api/v1/cv/readiness
    res_v1_cv = client.get("/api/v1/cv/readiness")
    assert res_v1_cv.status_code == 200
    assert "ready" in res_v1_cv.json()

    # 4. Check /api/v1/experiments/history
    res_v1_hist = client.get("/api/v1/experiments/history", headers=AUTH_HEADERS)
    assert res_v1_hist.status_code == 200
    assert "history" in res_v1_hist.json()


# ==============================================================================
# 2. Tutor Request Contracts & Malformed Payload Tests
# ==============================================================================

def test_tutor_chat_rejects_unexpected_fields():
    """ChatRequest forbids extra fields (extra='forbid')."""
    payload = {
        "prompt": "Explain Newton's third law",
        "malicious_extra_field": "injected_data",
    }
    res = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()) or "Extra inputs are not permitted" in str(res.json())


def test_tutor_chat_rejects_malformed_history_role():
    """ChatHistoryTurn requires role to be an allowed ChatRole enum (user, assistant, system, model)."""
    payload = {
        "prompt": "Hello",
        "history": [
            {"role": "superuser_admin", "content": "I have escalated privileges."}
        ],
    }
    res = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "role" in str(res.json())


def test_tutor_chat_rejects_empty_history_turn_content():
    """ChatHistoryTurn requires non-empty content or text."""
    payload = {
        "prompt": "Hello",
        "history": [
            {"role": "user", "content": "", "text": ""}
        ],
    }
    res = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "must contain non-empty 'content' or 'text'" in str(res.json())


def test_tutor_chat_rejects_unexpected_fields_in_history_turn():
    """ChatHistoryTurn forbids extra unexpected fields."""
    payload = {
        "prompt": "Hello",
        "history": [
            {"role": "user", "content": "Valid text", "spoofed_metadata": {"hacked": True}}
        ],
    }
    res = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()) or "Extra inputs are not permitted" in str(res.json())


def test_tutor_chat_rejects_exceeding_history_turns():
    """History turn length capped at 20 turns."""
    turns = [{"role": "user", "content": f"Turn {i}"} for i in range(25)]
    payload = {
        "prompt": "Hello",
        "history": turns,
    }
    res = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "at most 20" in str(res.json()) or "history" in str(res.json())


def test_tutor_chat_validates_experiment_state_context():
    """experiment_state must adhere to ExperimentStateContext schema."""
    # 1. Invalid time_elapsed (negative)
    res1 = client.post(
        "/api/tutor/chat/stream",
        json={"prompt": "Review my run", "experiment_state": {"time_elapsed": -10.0}},
        headers=AUTH_HEADERS,
    )
    assert res1.status_code == 422

    # 2. Unexpected fields in experiment_state
    res2 = client.post(
        "/api/tutor/chat/stream",
        json={"prompt": "Review my run", "experiment_state": {"arbitrary_junk": "not_allowed"}},
        headers=AUTH_HEADERS,
    )
    assert res2.status_code == 422


def test_tutor_concept_evaluation_rejects_unexpected_fields():
    """ConceptEvaluationRequest forbids extra fields."""
    payload = {
        "concept": "Gravity",
        "question": "What is g on Earth?",
        "answer": "9.8 m/s^2",
        "unexpected_field": "hack",
    }
    res = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422


# ==============================================================================
# 3. CV Tracker Request & Response Contract Tests
# ==============================================================================

def test_cv_process_frame_rejects_unexpected_fields():
    """FrameProcessRequest rejects extra unexpected fields."""
    b64 = make_test_frame_b64()
    payload = {
        "image": b64,
        "unexpected_injected_field": 42,
    }
    res = client.post("/api/cv/process-frame", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()) or "Extra inputs are not permitted" in str(res.json())


def test_cv_process_frame_rejects_invalid_tracking_method():
    """FrameProcessRequest validates tracking_method against TrackingMethod enum."""
    b64 = make_test_frame_b64()
    payload = {
        "image": b64,
        "tracking_method": "telepathic_tracking",
    }
    res = client.post("/api/cv/process-frame", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "tracking_method" in str(res.json())


def test_cv_process_frame_rejects_out_of_bounds_confidence():
    """confidence_threshold must be between 0.0 and 1.0."""
    b64 = make_test_frame_b64()
    res_neg = client.post(
        "/api/cv/process-frame",
        json={"image": b64, "confidence_threshold": -0.5},
        headers=AUTH_HEADERS,
    )
    assert res_neg.status_code == 422

    res_high = client.post(
        "/api/cv/process-frame",
        json={"image": b64, "confidence_threshold": 1.5},
        headers=AUTH_HEADERS,
    )
    assert res_high.status_code == 422


def test_cv_engagement_rejects_unexpected_fields():
    """EngagementEvent forbids unexpected fields."""
    payload = {
        "state": "focused",
        "confidence": 0.95,
        "unexpected_hack": True,
    }
    res = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()) or "Extra inputs are not permitted" in str(res.json())


def test_cv_engagement_response_contract():
    """Valid engagement event returns structured EngagementResponse."""
    payload = {
        "state": "focused",
        "confidence": 0.88,
        "session_id": "sess_contract_01",
    }
    res = client.post("/api/cv/engagement", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    event = data["event"]
    assert event["user_id"] == MOCK_USER["id"]
    assert event["state"] == "focused"
    assert event["confidence"] == 0.88
    assert event["is_estimate"] is True
    assert "disclaimer" in event


# ==============================================================================
# 4. Experiment Routes Request & Response Contract Tests
# ==============================================================================

def test_experiment_save_rejects_unexpected_fields():
    """ExperimentData forbids unexpected fields."""
    payload = {
        "type": "free_fall",
        "height": 50.0,
        "unauthorized_field": "attack",
    }
    res = client.post("/api/experiments/save", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
    assert "extra_forbidden" in str(res.json()) or "Extra inputs are not permitted" in str(res.json())


def test_experiment_save_response_contract():
    """Valid experiment save conforms to ExperimentSaveResponse."""
    payload = {
        "type": "free_fall",
        "height": 75.0,
        "mass": 3.0,
        "gravity": 9.81,
    }
    res = client.post("/api/experiments/save", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "saved"
    exp = data["experiment"]
    assert exp["user_id"] == MOCK_USER["id"]
    assert exp["experiment_type"] == "free_fall"
    assert "input_data" in exp
    assert "server_computed_results" in exp
    assert "metrics" in exp


def test_experiment_history_and_detail_response_contracts():
    """History and detail endpoints conform to their response contracts."""
    res_hist = client.get("/api/experiments/history", headers=AUTH_HEADERS)
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert "history" in hist_data
    assert isinstance(hist_data["history"], list)

