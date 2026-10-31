"""
Tests for Problem 43: Celery Worker Tasks Implementation, Payloads, Timeouts, Idempotency, and Results.
Verifies:
1. Actual inference and generation tasks (non-stub implementations).
2. Strict payload validation and fast failure on bad inputs.
3. Retries triggered exclusively on transient errors (not client/payload errors).
4. Task IDs and explicit lifecycle states (PENDING, STARTED, PROCESSING, SUCCESS, FAILURE).
5. Durable result storage and retrieval endpoint.
6. Timeouts and task expiration settings.
7. Worker concurrency and memory recycling configuration.
8. Idempotent task execution.
"""
import base64
import cv2
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.worker import (
    celery_app,
    process_heavy_cv_frame,
    generate_ai_tutor_response,
    get_celery_task_status,
    dispatch_async_task,
    check_broker_health,
    CVTaskPayload,
    AITaskPayload,
    TaskBrokerUnavailableError,
)

# Mock authenticated user for API routes
MOCK_USER = {
    "id": "e9999999-9999-9999-9999-999999999999",
    "email": "tester@neurolab.ai",
    "role": "authenticated",
}


@pytest.fixture(autouse=True)
def setup_auth_and_sync():
    """Ensure tests run with authenticated dependency override."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


def create_test_frame_b64(width: int = 640, height: int = 480, draw_circle: bool = True) -> str:
    """Generates a valid test image with a red circle."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    if draw_circle:
        cx, cy = width // 2, height // 2
        radius = min(width, height) // 4
        # Draw red circle in BGR: (0, 0, 255)
        cv2.circle(img, (cx, cy), radius, (0, 0, 255), -1)
    _, buffer = cv2.imencode(".jpg", img)
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


# ==============================================================================
# 1. Real Computer Vision Task Execution
# ==============================================================================

def test_real_cv_frame_task_execution():
    """
    Verification: Submit a real frame with a red circle and confirm:
    - Results correspond to submitted input.
    - Bounding boxes are REAL and non-empty (not the previous stub []).
    - Centroid and physics kinematics are computed.
    - Width and height match the submitted frame.
    """
    b64_img = create_test_frame_b64(width=640, height=480, draw_circle=True)
    payload = {
        "image": b64_img,
        "tracking_method": "color",
        "color_target": "red",
        "px_to_meters": 0.005,
        "confidence_threshold": 0.2,
    }

    result = process_heavy_cv_frame(payload)

    assert result["status"] == "processed"
    assert "task_id" in result
    assert result["width"] == 640
    assert result["height"] == 480

    # Critical verification: Bounding boxes must NOT be empty!
    bounding_boxes = result["bounding_boxes"]
    assert len(bounding_boxes) >= 1, "Expected real non-empty bounding boxes from real CV tracking"
    primary_box = bounding_boxes[0]
    assert len(primary_box) == 4
    x_min, y_min, x_max, y_max = primary_box
    assert x_min < x_max
    assert y_min < y_max

    # Centroid should be approximately near the center (320, 240)
    centroid = result["centroid"]
    assert centroid is not None
    assert abs(centroid[0] - 320) < 50
    assert abs(centroid[1] - 240) < 50

    # Physics kinematics must be populated
    physics = result["physics"]
    assert physics is not None
    assert "velocity_mps" in physics
    assert "acceleration_mps2" in physics


# ==============================================================================
# 2. Real AI Tutor Task Execution
# ==============================================================================

def test_real_ai_tutor_task_execution():
    """
    Verification: Submit a real tutor request (e.g. pendulum period) and confirm:
    - Result corresponds to submitted prompt input.
    - Response is a real pedagogical explanation (not fixed stub).
    - Model and usage statistics are recorded.
    """
    prompt = "Explain how the period of a simple pendulum relates to length and gravity."
    result = generate_ai_tutor_response({"prompt": prompt, "session_id": "test_sess_01"})

    assert result["status"] == "generated"
    assert "task_id" in result
    assert result["prompt"] == prompt

    # Response must correspond to the prompt (mentions pendulum formula or relationship)
    resp_text = result["response"]
    assert len(resp_text) > 20
    assert "pendulum" in resp_text.lower() or "gravity" in resp_text.lower()
    assert resp_text != "AI response generated in background.", "Should not return legacy fixed stub"

    # Usage statistics
    assert "usage" in result
    assert result["usage"]["prompt_tokens_est"] > 0
    assert result["usage"]["completion_tokens_est"] > 0
    assert result["usage"]["duration_seconds"] >= 0.0


def test_ai_tutor_newton_second_law_prompt():
    """Confirms AI tutor task responds accurately to Newton's law prompt."""
    prompt = "What is Newton's second law of motion and the formula for net force?"
    result = generate_ai_tutor_response(prompt)

    assert result["status"] == "generated"
    resp_text = result["response"]
    assert "newton" in resp_text.lower() or "force" in resp_text.lower() or "f = m" in resp_text.lower()


# ==============================================================================
# 3. Payload Validation and Fast Failure
# ==============================================================================

def test_cv_task_rejects_missing_image_immediately():
    """Rejects empty or missing image data without triggering Celery retries."""
    with pytest.raises(ValueError) as exc_info:
        process_heavy_cv_frame({})
    assert "image" in str(exc_info.value).lower()

    with pytest.raises(ValueError) as exc_info2:
        process_heavy_cv_frame({"image": "   \n\t  "})
    assert "image" in str(exc_info2.value).lower()


def test_cv_task_rejects_invalid_types():
    """Rejects non-dict payload immediately."""
    with pytest.raises(ValueError) as exc_info:
        process_heavy_cv_frame("not-a-dict")
    assert "dictionary" in str(exc_info.value).lower()


def test_ai_task_rejects_empty_prompt():
    """Rejects blank prompt immediately without retry."""
    with pytest.raises(ValueError) as exc_info:
        generate_ai_tutor_response("")
    assert "prompt" in str(exc_info.value).lower()

    with pytest.raises(ValueError) as exc_info2:
        generate_ai_tutor_response({"prompt": "   "})
    assert "prompt" in str(exc_info2.value).lower()


# ==============================================================================
# 4. Retries Only on Transient Errors
# ==============================================================================

def test_transient_error_triggers_retry():
    """Confirms transient network errors trigger self.retry with exponential backoff."""
    generate_ai_tutor_response.request.retries = 1
    try:
        with patch.object(generate_ai_tutor_response, "retry", side_effect=RuntimeError("Retry triggered")) as mock_retry:
            with patch("os.getenv", side_effect=lambda k, d=None: "" if k in ("ALLOW_FAKE_VECTORS", "ENVIRONMENT") else ("real-key" if k == "GEMINI_API_KEY" else d)):
                with patch("google.generativeai.GenerativeModel.generate_content", side_effect=TimeoutError("Connection timeout to Gemini")):
                    with pytest.raises(RuntimeError) as exc_info:
                        generate_ai_tutor_response("What is velocity?")
                    assert "Retry triggered" in str(exc_info.value)
                    mock_retry.assert_called_once()
                    # Verify countdown with exponential backoff: 2 ** 1 = 2 seconds
                    call_kwargs = mock_retry.call_args[1]
                    assert call_kwargs["countdown"] == 2
                    assert call_kwargs["max_retries"] == 3
    finally:
        generate_ai_tutor_response.request.retries = 0


def test_non_transient_error_does_not_retry():
    """Confirms non-transient validation errors do NOT trigger self.retry."""
    with patch.object(generate_ai_tutor_response, "retry") as mock_retry:
        with pytest.raises(ValueError):
            generate_ai_tutor_response("")

    mock_retry.assert_not_called()


# ==============================================================================
# 5. Idempotent Task Execution
# ==============================================================================

def test_cv_task_idempotency():
    """Identical idempotency_key returns cached result without re-executing inference."""
    b64_img = create_test_frame_b64(width=320, height=240, draw_circle=True)
    payload = {
        "image": b64_img,
        "tracking_method": "color",
        "color_target": "red",
        "idempotency_key": "idemp_cv_test_001",
    }

    # First run: performs real processing
    res1 = process_heavy_cv_frame(payload)
    assert res1["status"] == "processed"
    assert "cached" not in res1 or not res1["cached"]

    # Second run with same idempotency key: returns cached result
    res2 = process_heavy_cv_frame(payload)
    assert res2["task_id"] == res1["task_id"]
    assert res2.get("cached") is True
    assert res2["bounding_boxes"] == res1["bounding_boxes"]


def test_ai_task_idempotency():
    """Identical idempotency_key returns cached AI tutor response."""
    payload = {
        "prompt": "What is the formula for kinetic energy?",
        "idempotency_key": "idemp_ai_test_002",
    }

    res1 = generate_ai_tutor_response(payload)
    assert res1["status"] == "generated"

    res2 = generate_ai_tutor_response(payload)
    assert res2["task_id"] == res1["task_id"]
    assert res2.get("cached") is True
    assert res2["response"] == res1["response"]


# ==============================================================================
# 6. Task Status and Result Retrieval API
# ==============================================================================

def test_task_status_and_result_retrieval():
    """Verifies get_celery_task_status and GET /api/v1/tasks/{task_id} API endpoint."""
    client = TestClient(app)

    # 1. Execute task to populate result store
    ai_res = generate_ai_tutor_response({"prompt": "Explain conservation of energy."})
    task_id = ai_res["task_id"]

    # 2. Retrieve status via helper function
    status_dict = get_celery_task_status(task_id)
    assert status_dict["task_id"] == task_id
    assert status_dict["state"] == "SUCCESS"
    assert status_dict["status"] == "completed"
    assert status_dict["ready"] is True
    assert status_dict["result"]["response"] == ai_res["response"]

    # 3. Retrieve status via API endpoint
    resp = client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task_id"] == task_id
    assert data["state"] == "SUCCESS"
    assert data["ready"] is True
    assert "energy" in data["result"]["response"].lower()


def test_async_dispatch_endpoints():
    """Verifies POST /api/v1/tasks/cv/process-frame-async and /tutor/generate-async."""
    client = TestClient(app)

    # Test CV async dispatch endpoint
    b64_img = create_test_frame_b64(width=320, height=240, draw_circle=True)
    cv_resp = client.post(
        "/api/v1/tasks/cv/process-frame-async",
        json={"image": b64_img, "tracking_method": "color", "color_target": "red"},
    )
    assert cv_resp.status_code == 200
    cv_data = cv_resp.json()
    assert "task_id" in cv_data
    assert cv_data["status"] in ("queued", "completed")

    # Test AI tutor async dispatch endpoint
    ai_resp = client.post(
        "/api/v1/tasks/tutor/generate-async",
        json={"prompt": "How does gravity work near Earth's surface?"},
    )
    assert ai_resp.status_code == 200
    ai_data = ai_resp.json()
    assert "task_id" in ai_data
    assert ai_data["status"] in ("queued", "completed")


# ==============================================================================
# 7. Celery Worker Concurrency, Timeouts, and Memory Policies
# ==============================================================================

def test_celery_worker_concurrency_and_memory_policies():
    """
    Verifies worker configuration adheres to operational constraints:
    - Bounded worker concurrency.
    - Prefetch multiplier = 1 (no bulk prefetching for heavy tasks).
    - Child process task recycling (preventing memory leaks).
    - Late task acknowledgement.
    - Time limits and result expiration.
    """
    conf = celery_app.conf

    # Concurrency
    assert conf.worker_concurrency >= 1
    assert conf.worker_concurrency <= 8

    # Prefetch multiplier
    assert conf.worker_prefetch_multiplier == 1

    # Memory and child recycling
    assert conf.worker_max_tasks_per_child == 50
    assert conf.worker_max_memory_per_child == 400_000

    # Reliability and persistence
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.result_expires == 3600
    assert conf.task_time_limit >= 30
    assert conf.task_soft_time_limit >= 25
