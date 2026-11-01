import asyncio
import base64
import time
import tracemalloc
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.machine_learning.cv_service import cv_tracker_manager

client = TestClient(app)

TEST_USER = {"id": "cv_perf_user_001", "email": "perf@neurolab.ai", "role": "authenticated"}


def get_mock_user():
    return TEST_USER


@pytest.fixture(autouse=True)
def setup_perf_context():
    app.dependency_overrides[get_current_user] = get_mock_user
    cv_tracker_manager.clear_all()
    from app.cache import clear_local_cache
    clear_local_cache()
    yield
    cv_tracker_manager.clear_all()
    clear_local_cache()
    app.dependency_overrides.clear()


def make_test_frame_b64(cx: int = 100, cy: int = 100, width: int = 320, height: int = 240) -> str:
    """Creates a small base64 JPEG frame for fast and reproducible performance testing."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), 20, (0, 0, 255), -1)
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# ==============================================================================
# 1. Maximum Simultaneous Frame Requests & Semaphore Contention
# ==============================================================================

@pytest.mark.asyncio
async def test_maximum_simultaneous_frame_requests_rejection():
    """
    Problem 12: Test behavior when simultaneous frame requests saturate
    the concurrency semaphore (limit = 10). Excess requests waiting longer
    than the 1.0s semaphore acquisition timeout must receive HTTP 429.
    """
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        b64_frame = make_test_frame_b64()

        # Simulate slow inference that holds the semaphore for 1.5 seconds
        original_process = cv_tracker_manager.get_tracker_sync(TEST_USER["id"]).process_frame

        def slow_process(*args, **kwargs):
            time.sleep(1.2)
            return original_process(*args, **kwargs)

        with patch("app.machine_learning.cv_service.CVTracker.process_frame", side_effect=slow_process):
            # Launch 14 concurrent requests simultaneously (semaphore is 10)
            tasks = [
                ac.post(
                    "/api/cv/process-frame",
                    json={"image": b64_frame, "session_id": f"sess_{i}"},
                )
                for i in range(14)
            ]
            responses = await asyncio.gather(*tasks)

            status_codes = [r.status_code for r in responses]
            # Some requests must succeed (HTTP 200), and overflow requests that timed out
            # acquiring the semaphore within 1.0s must receive HTTP 429
            success_count = status_codes.count(200)
            too_many_requests_count = status_codes.count(429)

            assert success_count > 0, "At least some requests must succeed"
            assert too_many_requests_count > 0, "Overflow requests must be rejected with 429 Too Many Requests"

            for r in responses:
                if r.status_code == 429:
                    assert "Maximum simultaneous frame tasks reached" in r.json()["detail"]


# ==============================================================================
# 2. Memory Consumption Under Sustained Traffic
# ==============================================================================

def test_memory_consumption_under_sustained_traffic():
    """
    Problem 12: Verify memory does not grow unbounded under sustained frame traffic.
    Runs 50 sequential frames and asserts memory delta remains strictly bounded.
    """
    tracemalloc.start()
    b64_frame = make_test_frame_b64()

    # Warmup
    for _ in range(5):
        client.post("/api/cv/process-frame", json={"image": b64_frame, "session_id": "sustained_sess"})

    snapshot_before = tracemalloc.take_snapshot()

    # Sustained load of 45 more frames
    for i in range(45):
        x = 50 + (i % 200)
        frame = make_test_frame_b64(cx=x, cy=100)
        res = client.post("/api/cv/process-frame", json={"image": frame, "session_id": "sustained_sess"})
        assert res.status_code == 200

    snapshot_after = tracemalloc.take_snapshot()
    top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_diff_bytes = sum(stat.size_diff for stat in top_stats)
    tracemalloc.stop()

    # Under 45 frames, net memory growth should be less than 15 MB
    # (mostly python internal tracking buffers, no memory leaks in image decoding)
    assert total_diff_bytes < 15 * 1024 * 1024, f"Memory growth too high: {total_diff_bytes / 1024 / 1024:.2f} MiB"


# ==============================================================================
# 3. Slow Inference and Timeout Handling
# ==============================================================================

def test_slow_inference_timeout_handling():
    """
    Problem 12: When CV inference takes longer than the 5.0 second execution timeout,
    the endpoint must return HTTP 408 Request Timeout and release the semaphore.
    """
    b64_frame = make_test_frame_b64()

    def hanging_inference(*args, **kwargs):
        # Hang longer than the 5.0s timeout
        time.sleep(6.0)
        return {}

    with patch("app.machine_learning.cv_service.CVTracker.process_frame", side_effect=hanging_inference):
        res = client.post("/api/cv/process-frame", json={"image": b64_frame, "session_id": "timeout_sess"})
        assert res.status_code == 408, f"Expected 408 Request Timeout, got {res.status_code}"
        assert "timed out" in res.json()["detail"].lower()

    # Crucial test: Ensure semaphore was cleanly released in the finally block!
    # A subsequent normal request must succeed immediately with 200
    res_subsequent = client.post("/api/cv/process-frame", json={"image": b64_frame, "session_id": "timeout_sess"})
    assert res_subsequent.status_code == 200, "Subsequent request failed, indicating semaphore leak!"


# ==============================================================================
# 4. Large Batches of Malformed Frames Resilience
# ==============================================================================

def test_large_batch_of_malformed_frames_resilience():
    """
    Problem 12: Rapid bursts of malformed, corrupt, or adversarial frames
    must be cleanly rejected with 422 or 413, without crashing the server,
    causing memory corruption, or leaking semaphore tokens.
    """
    malformed_payloads = [
        {"image": "not_even_base64_!@#$%^&*()"},
        {"image": base64.b64encode(b"random garbage byte sequence").decode("utf-8")},
        {"image": base64.b64encode(b"\x00" * 1000).decode("utf-8")},
        {"image": ""},
        {"frame": "aW52YWxpZF9qcGVn_header_only"},
    ]

    # Send 25 malformed requests rapidly
    for i in range(25):
        payload = malformed_payloads[i % len(malformed_payloads)]
        res = client.post("/api/cv/process-frame", json=payload)
        assert res.status_code in [422, 400], f"Expected 422/400 for malformed frame, got {res.status_code}"

    # Verify that server is completely healthy and immediately serves a valid frame
    valid_frame = make_test_frame_b64()
    valid_res = client.post("/api/cv/process-frame", json={"image": valid_frame})
    assert valid_res.status_code == 200
    assert valid_res.json()["physics"]["track_id"] is not None


# ==============================================================================
# 5. Oversized Frame Rejection Before Parsing
# ==============================================================================

def test_oversized_payload_rejection_without_decoding():
    """
    Problem 12: Verify frames larger than MAX_FRAME_PAYLOAD_BYTES (5 MiB)
    are rejected with HTTP 413 before base64 or OpenCV decoding.
    """
    # 6 MB of dummy data
    oversized_data = "A" * (6 * 1024 * 1024)
    res = client.post("/api/cv/process-frame", json={"image": oversized_data})
    assert res.status_code == 413
    assert "exceeds 5mb limit" in res.json()["detail"].lower()

