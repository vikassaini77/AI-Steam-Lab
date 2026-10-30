import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user

# Mock authenticated user
MOCK_USER = {
    "id": "e9999999-9999-9999-9999-999999999999",
    "email": "student@neurolab.ai",
    "role": "authenticated",
}


def mock_get_current_user():
    return MOCK_USER


@pytest.fixture(autouse=True)
def setup_auth_override():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def create_test_image(width: int, height: int, format: str = ".jpg") -> bytes:
    """Helper to create dummy in-memory image bytes."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Draw a colored red circle to trigger color tracker
    cv2.circle(img, (width // 2, height // 2), min(width, height) // 4, (0, 0, 255), -1)
    _, buffer = cv2.imencode(format, img)
    return buffer.tobytes()


def test_corrupt_base64_returns_422(client):
    """Corrupt base64 string should be rejected with 422 Unprocessable Entity."""
    response = client.post(
        "/api/cv/process-frame",
        json={"image": "not-valid-base64-%%%$$$"},
    )
    assert response.status_code == 422
    assert "Invalid base64" in response.json()["detail"] or "invalid" in response.json()["detail"].lower()


def test_empty_image_payload_returns_422(client):
    """Empty image string or missing field returns 422."""
    response1 = client.post("/api/cv/process-frame", json={"image": ""})
    assert response1.status_code == 422

    response2 = client.post("/api/cv/process-frame", json={})
    assert response2.status_code == 422


def test_corrupt_image_bytes_returns_422(client):
    """Valid base64 containing non-image random bytes returns 422."""
    fake_b64 = base64.b64encode(b"This is just random text, not a real JPEG or PNG file!").decode()
    response = client.post("/api/cv/process-frame", json={"image": fake_b64})
    assert response.status_code == 422
    assert "Unsupported image format" in response.json()["detail"] or "corrupt" in response.json()["detail"].lower()


def test_oversized_resolution_image_returns_422(client):
    """Image exceeding 1920x1080 resolution returns 422."""
    large_img_bytes = create_test_image(2000, 1200, ".jpg")
    b64_str = base64.b64encode(large_img_bytes).decode()

    response = client.post("/api/cv/process-frame", json={"image": b64_str})
    assert response.status_code == 422
    assert "Image dimensions" in response.json()["detail"] or "exceed" in response.json()["detail"]


def test_oversized_http_payload_returns_413(client):
    """Payloads exceeding the 5MB ceiling return 413 Content Too Large."""
    # 6MB dummy content length simulation
    six_mb = 6 * 1024 * 1024
    response = client.post(
        "/api/cv/process-frame",
        json={"image": "dummy"},
        headers={"Content-Length": str(six_mb)},
    )
    assert response.status_code == 413
    assert "Payload too large" in response.json()["detail"]


def test_valid_image_frame_returns_200(client):
    """Valid JPEG frame (640x480) successfully processes and returns 200 OK."""
    valid_bytes = create_test_image(640, 480, ".jpg")
    b64_str = base64.b64encode(valid_bytes).decode()

    response = client.post(
        "/api/cv/process-frame",
        json={
            "image": f"data:image/jpeg;base64,{b64_str}",
            "tracking_method": "color",
            "color_target": "red",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "centroid" in data
    assert "physics" in data
    assert data["user_id"] == MOCK_USER["id"]


def test_process_frame_binary_endpoint(client):
    """Binary upload endpoint accepts raw JPEG bytes and rejects corrupt data."""
    valid_bytes = create_test_image(320, 240, ".jpg")
    response = client.post(
        "/api/cv/process-frame-binary",
        content=valid_bytes,
        headers={"Content-Type": "image/jpeg"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "centroid" in data

    # Test corrupt binary bytes
    corrupt_response = client.post(
        "/api/cv/process-frame-binary",
        content=b"not-an-image-header-bytes",
        headers={"Content-Type": "image/jpeg"},
    )
    assert corrupt_response.status_code == 422
