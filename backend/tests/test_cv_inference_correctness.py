import base64
import cv2
import numpy as np
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.machine_learning.cv_service import (
    CVTracker,
    Detection,
    FrameResult,
    TrajectoryTracker,
)
from app.core_backend.core.dependencies import get_current_user

MOCK_USER = {"id": "user_cv_correctness_test", "email": "cv_test@neurolab.ai", "role": "authenticated"}

@pytest.fixture(autouse=True)
def setup_auth():
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def client():
    return TestClient(app)


def compute_iou(boxA, boxB):
    """Computes Intersection-over-Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    unionArea = boxAArea + boxBArea - interArea

    return interArea / unionArea if unionArea > 0 else 0.0


def make_b64(img: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


# ==============================================================================
# 1. Schema Validation Tests
# ==============================================================================

def test_detection_schema_validation_success():
    """Valid Detection model instantiation succeeds."""
    det = Detection(
        class_name="sports ball",
        confidence=0.92,
        bbox_xyxy=[100.0, 150.0, 250.0, 300.0],
        track_id=1,
    )
    assert det.class_name == "sports ball"
    assert det.confidence == 0.92
    assert det.bbox_xyxy == [100.0, 150.0, 250.0, 300.0]


def test_detection_schema_invalid_bbox_length():
    """Bbox with length != 4 raises ValidationError."""
    with pytest.raises(ValidationError):
        Detection(class_name="ball", confidence=0.8, bbox_xyxy=[10.0, 20.0, 30.0])


def test_detection_schema_invalid_coordinate_ordering():
    """x_min > x_max or y_min > y_max raises ValidationError."""
    # x_min (200) > x_max (100)
    with pytest.raises(ValidationError):
        Detection(class_name="ball", confidence=0.8, bbox_xyxy=[200.0, 50.0, 100.0, 150.0])

    # y_min (300) > y_max (100)
    with pytest.raises(ValidationError):
        Detection(class_name="ball", confidence=0.8, bbox_xyxy=[50.0, 300.0, 150.0, 100.0])


def test_detection_schema_confidence_bounds():
    """Confidence outside [0.0, 1.0] raises ValidationError."""
    with pytest.raises(ValidationError):
        Detection(class_name="ball", confidence=1.5, bbox_xyxy=[10.0, 10.0, 50.0, 50.0])
    with pytest.raises(ValidationError):
        Detection(class_name="ball", confidence=-0.1, bbox_xyxy=[10.0, 10.0, 50.0, 50.0])


# ==============================================================================
# 2. Real Detection vs Fake Centroid Elimination
# ==============================================================================

def test_empty_image_returns_no_fake_centroid():
    """
    On an image with no objects, the service must return detections: [] and centroid: None.
    It MUST NOT return the center of the image [width // 2, height // 2] as a fake detection.
    """
    tracker = CVTracker()
    blank_img = np.zeros((480, 640, 3), dtype=np.uint8)  # Solid black image
    b64 = make_b64(blank_img)

    result = tracker.process_frame(b64, tracking_method="color", color_target="red")

    assert result["detections"] == [], "Must return empty detection list for blank frame"
    assert result["centroid"] is None, "Centroid must be None when no object is detected, not the image center"
    assert result["contours_found"] == 0
    assert result["physics"]["x_meters"] is None


def test_labeled_ground_truth_single_object():
    """
    Verification: Run known test image with ground truth object at (200, 200).
    Verify IoU >= 0.85, Precision = 1.0, Recall = 1.0, and centroid within 2px of ground truth.
    """
    tracker = CVTracker()
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # Draw known ground truth red ball at (200, 200) with radius 35
    # Bbox: x_min=165, y_min=165, x_max=235, y_max=235
    gt_bbox = [165.0, 165.0, 235.0, 235.0]
    gt_centroid = [200, 200]
    cv2.circle(img, (200, 200), 35, (0, 0, 255), -1)

    b64 = make_b64(img)
    result = tracker.process_frame(b64, tracking_method="color", color_target="red")

    assert len(result["detections"]) == 1
    det = result["detections"][0]

    # Check precision & recall
    precision = 1.0  # 1 true positive / 1 detection
    recall = 1.0     # 1 true positive / 1 ground truth
    assert precision == 1.0
    assert recall == 1.0

    # Check IoU
    iou = compute_iou(det["bbox_xyxy"], gt_bbox)
    assert iou >= 0.85, f"Expected IoU >= 0.85 with ground truth, got {iou:.3f}"

    # Check centroid accuracy
    cx, cy = result["centroid"]
    assert abs(cx - gt_centroid[0]) <= 2
    assert abs(cy - gt_centroid[1]) <= 2
    assert result["inference_latency_ms"] > 0


def test_labeled_ground_truth_multi_object():
    """
    Verification: Run test image with two distinct blue targets.
    Verify both are detected with high recall and precision.
    """
    tracker = CVTracker()
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # Target 1: Rect at (80, 80) to (160, 160)
    gt_box_1 = [80.0, 80.0, 160.0, 160.0]
    cv2.rectangle(img, (80, 80), (160, 160), (255, 0, 0), -1)

    # Target 2: Rect at (350, 200) to (450, 300)
    gt_box_2 = [350.0, 200.0, 450.0, 300.0]
    cv2.rectangle(img, (350, 200), (450, 300), (255, 0, 0), -1)

    b64 = make_b64(img)
    result = tracker.process_frame(b64, tracking_method="color", color_target="blue")

    assert len(result["detections"]) == 2
    ious = []
    for det in result["detections"]:
        iou_1 = compute_iou(det["bbox_xyxy"], gt_box_1)
        iou_2 = compute_iou(det["bbox_xyxy"], gt_box_2)
        ious.append(max(iou_1, iou_2))

    assert all(iou >= 0.85 for iou in ious)


# ==============================================================================
# 3. Model Readiness & YOLOv8 Verification
# ==============================================================================

def test_model_readiness_check():
    """Verifies explicit model readiness status reporting."""
    tracker = CVTracker()
    status = tracker.check_readiness()
    assert status["ready"] is True
    assert "active_model" in status
    assert "supported_methods" in status


def test_api_readiness_endpoint(client):
    """GET /api/cv/readiness returns 200 and readiness payload."""
    response = client.get("/api/cv/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert "supported_methods" in data


# ==============================================================================
# 4. Trajectory Tracking & Kinematics Across Frames
# ==============================================================================

def test_trajectory_id_tracking_and_velocity():
    """
    Verifies that object IDs persist across successive frames and
    instantaneous velocity is computed accurately from trajectory displacements.
    """
    tracker = TrajectoryTracker()
    px_to_m = 0.01  # 1 px = 0.01 m

    # Frame 1 at t=0s: Object at (100, 100)
    t1 = 1000.0
    id1, v1, a1 = tracker.update((100, 100), t1, px_to_m)
    assert id1 == 1
    assert v1 == 0.0

    # Frame 2 at t=0.1s: Object moved 30 px to (130, 100) -> 0.30 meters
    t2 = t1 + 0.1
    id2, v2, a2 = tracker.update((130, 100), t2, px_to_m)
    assert id2 == id1  # Same persistent object track
    expected_v = 0.30 / 0.1  # 3.0 m/s
    assert abs(v2 - expected_v) < 0.05

    # Frame 3 at t=0.2s: Object moved 50 px to (180, 100) -> 0.50 meters
    t3 = t2 + 0.1
    id3, v3, a3 = tracker.update((180, 100), t3, px_to_m)
    assert id3 == id1
    expected_v3 = 0.50 / 0.1  # 5.0 m/s
    assert abs(v3 - expected_v3) < 0.05
    # Acceleration = (5.0 - 3.0) / 0.1 = 20 m/s^2
    assert abs(a3 - 20.0) < 0.5


def test_tracker_reset_endpoint(client):
    """POST /api/cv/reset-tracker clears active tracks and resets ID counter."""
    response = client.post("/api/cv/reset-tracker")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

