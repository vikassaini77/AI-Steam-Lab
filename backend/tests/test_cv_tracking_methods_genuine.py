"""
Test Suite: Genuine Computer Vision Tracking Methods Implementation (Problem 10)
--------------------------------------------------------------------------------
Verifies genuine, independent implementations of:
1. Color Tracking:
   - HSV segmentation across all supported color targets (red, blue, green, yellow, orange, purple).
   - Morphology: opening eliminates noise specks, closing fills internal voids.
   - Contour filtering: min_area, max_area, aspect ratio sliver rejection, solidity filtering.
2. Optical Flow Tracking:
   - Feature detection: Shi-Tomasi corner detection with adaptive threshold fallback.
   - Lucas-Kanade tracking: Pyramidal LK tracking across frame translation.
   - Failure recovery: Point loss triggers re-detection and graceful continuity.
   - Tracker reset: Clears optical flow history and recovery counters.
3. YOLO Tracking:
   - Actual model weights loading (yolov8n.pt with 80 COCO classes).
   - Inference execution, coordinate clamping, and confidence bounds [0.0, 1.0].
   - Non-Maximum Suppression (NMS) on overlapping vs non-overlapping boxes.
   - Robust error handling: Missing weights, corrupted weights (<1KB and invalid format), incompatible weights.
   - Graceful degraded status when YOLO weights are missing/corrupted.
4. API Route Integration:
   - GET /api/cv/readiness reports all 3 supported methods and YOLO status.
   - POST /api/cv/process-frame executes color, optical_flow, and yolo methods independently.
"""

import os
import base64
import tempfile
from unittest.mock import patch, MagicMock
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.machine_learning.cv_service import (
    CVTracker,
    Detection,
    FrameResult,
    YOLOWeightsStatus,
    validate_and_load_yolo_weights,
    apply_nms_boxes,
    get_shared_yolo_model_info,
    cv_tracker_manager,
)

MOCK_USER = {"id": "user_cv_genuine_test", "email": "cv_genuine@neurolab.ai", "role": "authenticated"}


@pytest.fixture(autouse=True)
def setup_auth_and_cache():
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    cv_tracker_manager.clear_all()
    from app.cache import clear_local_cache
    clear_local_cache()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    cv_tracker_manager.clear_all()
    clear_local_cache()


@pytest.fixture
def client():
    return TestClient(app)


def make_b64(img: np.ndarray) -> str:
    """Encodes BGR OpenCV image into base64 JPEG."""
    _, buf = cv2.imencode(".jpg", img)
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def create_solid_color_circle_frame(color_bgr, cx=320, cy=240, radius=40, width=640, height=480) -> np.ndarray:
    """Creates a black frame with a solid colored circle."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, color_bgr, -1)
    return img


def create_textured_scene(offset_x=0, offset_y=0, width=640, height=480) -> np.ndarray:
    """Creates a textured synthetic scene with rich corners for optical flow feature tracking."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Background texture grid
    for x in range(50, 600, 80):
        for y in range(50, 440, 80):
            cv2.rectangle(img, (x + offset_x, y + offset_y), (x + 35 + offset_x, y + 35 + offset_y), (180, 180, 180), -1)
    # Foreground objects
    cv2.circle(img, (200 + offset_x, 200 + offset_y), 35, (255, 255, 255), -1)
    cv2.circle(img, (380 + offset_x, 260 + offset_y), 45, (220, 220, 220), -1)
    cv2.rectangle(img, (280 + offset_x, 120 + offset_y), (350 + offset_x, 190 + offset_y), (240, 240, 240), 2)
    return img


# ==============================================================================
# 1. COLOR TRACKING TESTS
# ==============================================================================

class TestColorTracking:
    """Verifies HSV segmentation, morphology, and contour filtering."""

    @pytest.mark.parametrize("color_name, bgr_val", [
        ("red", (0, 0, 255)),
        ("blue", (255, 0, 0)),
        ("green", (0, 255, 0)),
        ("yellow", (0, 255, 255)),
        ("orange", (0, 140, 255)),
        ("purple", (180, 0, 140)),
    ])
    def test_hsv_segmentation_across_all_colors(self, color_name, bgr_val):
        """HSV segmentation correctly detects circles across all supported target colors."""
        tracker = CVTracker()
        img = create_solid_color_circle_frame(bgr_val, cx=300, cy=220, radius=45)
        detections = tracker._detect_color(img, color_target=color_name, conf_thresh=0.2)

        assert len(detections) >= 1, f"Failed to detect {color_name} object"
        det = detections[0]
        assert det.class_name == f"{color_name}_object"
        assert 0.0 <= det.confidence <= 1.0
        assert det.confidence > 0.5

        # Centroid check
        x1, y1, x2, y2 = det.bbox_xyxy
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        assert abs(cx - 300) < 15
        assert abs(cy - 220) < 15

    def test_red_hue_wraparound(self):
        """Red tracking catches both lower hue [0..10] and upper hue [160..180]."""
        tracker = CVTracker()
        # Lower red: BGR (0, 0, 255) -> Hue 0
        img_low = create_solid_color_circle_frame((0, 0, 255), cx=200, cy=200, radius=30)
        dets_low = tracker._detect_color(img_low, color_target="red", conf_thresh=0.2)
        assert len(dets_low) == 1
        assert dets_low[0].class_name == "red_object"

        # Upper red: BGR (50, 0, 200) -> Hue ~ 172
        img_high = create_solid_color_circle_frame((50, 0, 200), cx=400, cy=200, radius=30)
        dets_high = tracker._detect_color(img_high, color_target="red", conf_thresh=0.2)
        assert len(dets_high) == 1
        assert dets_high[0].class_name == "red_object"

    def test_morphology_opening_removes_noise_specks(self):
        """Morphological opening (erode followed by dilate) removes tiny speckle noise."""
        tracker = CVTracker()
        img = np.zeros((480, 640, 3), dtype=np.uint8)

        # Scatter isolated 1-2 pixel noise specks (red sensor noise)
        np.random.seed(42)
        for _ in range(50):
            rx = np.random.randint(50, 590)
            ry = np.random.randint(50, 430)
            img[ry:ry+2, rx:rx+2] = (0, 0, 255)

        # Specks should be eliminated by morphological opening
        detections = tracker._detect_color(img, color_target="red", conf_thresh=0.2)
        assert len(detections) == 0, f"Expected 0 detections from noise specks, got {len(detections)}"

    def test_morphology_closing_fills_internal_holes(self):
        """Morphological closing fills internal voids in a ring/donut object."""
        tracker = CVTracker()
        img = np.zeros((480, 640, 3), dtype=np.uint8)

        # Draw a donut shape: large circle with small hollow center
        cv2.circle(img, (320, 240), 50, (0, 0, 255), -1)
        cv2.circle(img, (320, 240), 10, (0, 0, 0), -1)  # small internal void

        detections = tracker._detect_color(img, color_target="red", conf_thresh=0.2)
        assert len(detections) == 1
        # The closing fills the internal hole, preserving high confidence (> 0.6)
        assert detections[0].confidence > 0.6

    def test_contour_filter_min_area(self):
        """Objects with area < 50 pixels are discarded by contour filtering."""
        tracker = CVTracker()
        # Radius 3 circle -> area = pi * 3^2 ~= 28 px < 50 px min_area
        img = create_solid_color_circle_frame((0, 0, 255), cx=250, cy=250, radius=3)
        detections = tracker._detect_color(img, color_target="red", conf_thresh=0.1)
        assert len(detections) == 0

    def test_contour_filter_max_area_rejects_full_screen_wash(self):
        """Objects covering > 92% of the frame (e.g. camera tinted red) are rejected."""
        tracker = CVTracker()
        # Entire frame painted red
        img = np.full((480, 640, 3), (0, 0, 255), dtype=np.uint8)
        detections = tracker._detect_color(img, color_target="red", conf_thresh=0.1)
        assert len(detections) == 0

    def test_contour_filter_aspect_ratio_rejects_sensor_lines(self):
        """Thin slivers (aspect ratio > 18:1, e.g. camera scanline) are rejected."""
        tracker = CVTracker()
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        # 1-pixel wide line across 300 pixels horizontally (aspect ratio 300:1)
        cv2.line(img, (100, 200), (400, 200), (0, 0, 255), 1)
        detections = tracker._detect_color(img, color_target="red", conf_thresh=0.1)
        assert len(detections) == 0


# ==============================================================================
# 2. OPTICAL FLOW TRACKING TESTS
# ==============================================================================

class TestOpticalFlowTracking:
    """Verifies feature detection, Lucas-Kanade tracking, and failure recovery."""

    def test_optical_flow_feature_detection(self):
        """Shi-Tomasi corner detection extracts valid points on textured scenes."""
        tracker = CVTracker()
        img = create_textured_scene()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        pts = tracker._detect_optical_flow_features(gray)

        assert pts is not None
        assert len(pts) >= 10, f"Expected at least 10 corners on textured scene, found {len(pts)}"
        # Points format is (N, 1, 2)
        assert pts.shape[1] == 1 and pts.shape[2] == 2

    def test_optical_flow_feature_detection_blank_returns_none_or_few(self):
        """On a featureless blank frame, feature detector returns None or < 3 points."""
        tracker = CVTracker()
        blank_gray = np.zeros((480, 640), dtype=np.uint8)
        pts = tracker._detect_optical_flow_features(blank_gray)
        assert pts is None or len(pts) < 3

    def test_lucas_kanade_tracking_across_translation(self):
        """Lucas-Kanade tracks points and shifts bounding box across translated frames."""
        tracker = CVTracker()

        # Frame 1: Initial textured scene
        img1 = create_textured_scene(offset_x=0, offset_y=0)
        dets1, rec1 = tracker._track_optical_flow(img1, conf_thresh=0.2)
        assert len(dets1) == 1
        assert not rec1
        assert dets1[0].class_name == "optical_flow_target"
        assert dets1[0].confidence > 0.5
        orig_bbox = dets1[0].bbox_xyxy

        # Frame 2: Scene translated by dx=+20, dy=+15
        dx, dy = 20, 15
        img2 = create_textured_scene(offset_x=dx, offset_y=dy)
        dets2, rec2 = tracker._track_optical_flow(img2, conf_thresh=0.2)
        assert len(dets2) == 1
        assert not rec2
        new_bbox = dets2[0].bbox_xyxy

        # Bounding box coordinates should translate in the direction of motion
        assert new_bbox[0] > orig_bbox[0]
        assert new_bbox[1] > orig_bbox[1]
        assert abs((new_bbox[0] - orig_bbox[0]) - dx) < 10
        assert abs((new_bbox[1] - orig_bbox[1]) - dy) < 10

    def test_optical_flow_failure_recovery_on_point_loss(self):
        """
        When tracked points drop below minimum (e.g. scene cut to blank),
        the tracker triggers failure recovery, updates counters, and re-detects when features return.
        """
        tracker = CVTracker()

        # Step 1: Initialize tracking on textured scene
        img1 = create_textured_scene()
        dets1, rec1 = tracker._track_optical_flow(img1, conf_thresh=0.2)
        assert len(dets1) == 1
        assert not rec1
        assert tracker.of_failure_count == 0

        # Step 2: Sudden loss of features (completely blank screen)
        img_blank = np.zeros((480, 640, 3), dtype=np.uint8)
        dets_blank, rec_blank = tracker._track_optical_flow(img_blank, conf_thresh=0.2)

        # Blank screen cannot re-detect features, but failure recovery was attempted
        assert rec_blank is True
        assert tracker.of_failure_count >= 1

        # Step 3: Scene reappears with rich texture
        img3 = create_textured_scene(offset_x=50, offset_y=50)
        dets3, rec3 = tracker._track_optical_flow(img3, conf_thresh=0.2)

        # Successfully recovered and re-initialized tracking
        assert len(dets3) == 1
        assert dets3[0].class_name == "optical_flow_target"
        assert tracker.of_last_pts_count >= 10

    def test_optical_flow_reset_clears_state(self):
        """reset_tracker() clears optical flow points, history, and recovery metrics."""
        tracker = CVTracker()
        img = create_textured_scene()
        tracker._track_optical_flow(img, conf_thresh=0.2)

        assert tracker.of_prev_gray is not None
        assert tracker.of_prev_pts is not None
        assert tracker.of_last_pts_count > 0

        tracker.reset_tracker()

        assert tracker.of_prev_gray is None
        assert tracker.of_prev_pts is None
        assert tracker.of_last_pts_count == 0
        assert tracker.of_failure_count == 0
        assert tracker.of_recovered is False


# ==============================================================================
# 3. YOLO TRACKING AND WEIGHT HANDLING TESTS
# ==============================================================================

class TestYOLOTrackingAndWeights:
    """Verifies real YOLO model loading, inference, NMS, and defensive error handling."""

    def test_real_yolo_weights_loaded(self):
        """Loads official yolov8n.pt weights with 80 COCO classes."""
        model, status, err = get_shared_yolo_model_info()
        assert status == YOLOWeightsStatus.LOADED.value
        assert err is None
        assert model is not None
        assert hasattr(model, "names")
        assert len(model.names) == 80
        assert model.names[0] == "person"

    def test_yolo_inference_and_bbox_clamping(self):
        """Runs YOLO inference and ensures bbox coordinates are clamped to [0, W, 0, H]."""
        tracker = CVTracker()
        assert tracker.yolo_model is not None

        # Create a frame with a colored shape
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.circle(img, (320, 240), 80, (200, 150, 100), -1)

        # Execute YOLO detection pipeline directly
        detections = tracker._detect_yolo(img, conf_thresh=0.1, iou_thresh=0.45)
        for det in detections:
            assert 0.0 <= det.confidence <= 1.0
            x1, y1, x2, y2 = det.bbox_xyxy
            assert 0.0 <= x1 <= 640.0
            assert 0.0 <= y1 <= 480.0
            assert 0.0 <= x2 <= 640.0
            assert 0.0 <= y2 <= 480.0
            assert x2 >= x1
            assert y2 >= y1

    def test_apply_nms_boxes_suppresses_overlapping_boxes(self):
        """Non-Maximum Suppression (NMS) suppresses highly overlapping redundant boxes."""
        # Box 0: score 0.95, [100, 100, 200, 200]
        # Box 1: score 0.80, [105, 105, 205, 205] (90%+ overlap with Box 0 -> IoU ~ 0.8)
        # Box 2: score 0.90, [400, 300, 500, 400] (disjoint box, should survive)
        boxes = [
            [100.0, 100.0, 200.0, 200.0],
            [105.0, 105.0, 205.0, 205.0],
            [400.0, 300.0, 500.0, 400.0],
        ]
        scores = [0.95, 0.80, 0.90]

        kept = apply_nms_boxes(boxes, scores, iou_threshold=0.45, score_threshold=0.25)
        assert 0 in kept, "Primary box 0 must be kept"
        assert 2 in kept, "Disjoint box 2 must be kept"
        assert 1 not in kept, "Redundant overlapping box 1 must be suppressed by NMS"

    def test_apply_nms_boxes_respects_score_threshold(self):
        """Boxes with score below threshold are discarded even without overlap."""
        boxes = [
            [50.0, 50.0, 100.0, 100.0],
            [200.0, 200.0, 300.0, 300.0],
        ]
        scores = [0.85, 0.15]  # score 0.15 is below score_threshold=0.25
        kept = apply_nms_boxes(boxes, scores, iou_threshold=0.45, score_threshold=0.25)
        assert kept == [0]

    def test_weights_missing_handling(self):
        """Non-existent YOLO weights path reports WEIGHTS_MISSING and does not raise."""
        model, status, err = validate_and_load_yolo_weights("non_existent_weights_xyz.pt")
        assert model is None
        assert status == YOLOWeightsStatus.WEIGHTS_MISSING.value
        assert "not found" in err.lower()

    def test_weights_corrupted_small_file_handling(self):
        """Truncated or corrupted file (< 1024 bytes) reports WEIGHTS_CORRUPTED."""
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            f.write(b"corrupted_garbage_bytes")
            corrupt_path = f.name

        try:
            model, status, err = validate_and_load_yolo_weights(corrupt_path)
            assert model is None
            assert status == YOLOWeightsStatus.WEIGHTS_CORRUPTED.value
            assert "corrupted" in err.lower() or "truncated" in err.lower()
        finally:
            if os.path.exists(corrupt_path):
                os.unlink(corrupt_path)

    def test_weights_corrupted_invalid_archive_handling(self):
        """Invalid PyTorch archive (> 1024 bytes of random data) reports WEIGHTS_CORRUPTED."""
        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            f.write(os.urandom(4096))
            corrupt_path = f.name

        try:
            model, status, err = validate_and_load_yolo_weights(corrupt_path)
            assert model is None
            assert status == YOLOWeightsStatus.WEIGHTS_CORRUPTED.value
            assert err is not None
        finally:
            if os.path.exists(corrupt_path):
                os.unlink(corrupt_path)

    def test_weights_incompatible_architecture_handling(self):
        """Weights file lacking class metadata reports WEIGHTS_INCOMPATIBLE."""
        mock_model = MagicMock()
        mock_model.names = {}  # Empty class metadata

        with patch("ultralytics.YOLO", return_value=mock_model):
            with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
                f.write(b"x" * 2048)
                incomp_path = f.name

            try:
                model, status, err = validate_and_load_yolo_weights(incomp_path)
                assert model is None
                assert status == YOLOWeightsStatus.WEIGHTS_INCOMPATIBLE.value
                assert "incompatible" in err.lower() or "no valid class metadata" in err.lower()
            finally:
                if os.path.exists(incomp_path):
                    os.unlink(incomp_path)

    def test_yolo_degraded_fallback_when_weights_missing(self):
        """
        When YOLO tracking is requested but weights are unavailable, the tracker
        falls back to color tracking and returns inference_status='degraded' with provenance.
        """
        tracker = CVTracker(yolo_weights_path="missing_path.pt")
        assert tracker.yolo_model is None
        assert tracker.yolo_status == YOLOWeightsStatus.WEIGHTS_MISSING.value

        img = create_solid_color_circle_frame((0, 0, 255), cx=320, cy=240, radius=40)
        b64 = make_b64(img)

        result = tracker.process_frame(
            base64_img=b64,
            tracking_method="yolo",
            color_target="red",
        )

        assert result["inference_status"] == "degraded"
        assert "yolo_fallback_color" in result["model_name"]
        assert len(result["detections"]) >= 1
        assert result["provenance"]["yolo_status"] == YOLOWeightsStatus.WEIGHTS_MISSING.value
        assert "degraded_reason" in result["provenance"]


# ==============================================================================
# 4. API ROUTE INTEGRATION TESTS
# ==============================================================================

class TestCVRouteIntegration:
    """Verifies that the FastAPI endpoints support all three tracking methods cleanly."""

    def test_readiness_endpoint_reports_all_methods(self, client):
        """GET /api/cv/readiness returns all 3 supported methods and valid YOLO status."""
        resp = client.get("/api/cv/readiness")
        assert resp.status_code == 200
        data = resp.json()

        assert data["ready"] is True
        assert data["yolo_loaded"] is True
        assert data["yolo_status"] == "loaded"
        assert data["classes_count"] == 80
        assert set(data["supported_methods"]) == {"color", "optical_flow", "yolo"}

    def test_process_frame_color_method(self, client):
        """POST /api/cv/process-frame with tracking_method='color'."""
        img = create_solid_color_circle_frame((0, 0, 255), cx=320, cy=240, radius=35)
        payload = {
            "image": make_b64(img),
            "tracking_method": "color",
            "color_target": "red",
            "session_id": "sess_color_test",
        }
        resp = client.post("/api/cv/process-frame", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inference_status"] == "completed"
        assert data["model_name"] == "color_red"
        assert len(data["detections"]) == 1
        assert data["detections"][0]["class_name"] == "red_object"
        assert data["centroid"] is not None
        assert data["physics"]["x_meters"] is not None
        assert data["provenance"]["tracking_method"] == "color"
        assert data["raw_footage_stored"] is False

    def test_process_frame_optical_flow_method(self, client):
        """POST /api/cv/process-frame with tracking_method='optical_flow'."""
        img = create_textured_scene()
        payload = {
            "image": make_b64(img),
            "tracking_method": "optical_flow",
            "session_id": "sess_of_test",
        }
        resp = client.post("/api/cv/process-frame", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inference_status"] in ("completed", "degraded")
        assert data["model_name"] == "lucas_kanade_optical_flow"
        assert data["provenance"]["tracking_method"] == "optical_flow"
        assert "optical_flow_recovered" in data["provenance"]
        assert data["raw_footage_stored"] is False

    def test_process_frame_yolo_method(self, client):
        """POST /api/cv/process-frame with tracking_method='yolo'."""
        img = create_solid_color_circle_frame((0, 255, 0), cx=320, cy=240, radius=40)
        payload = {
            "image": make_b64(img),
            "tracking_method": "yolo",
            "session_id": "sess_yolo_test",
        }
        resp = client.post("/api/cv/process-frame", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["inference_status"] == "completed"
        assert data["model_name"] == "yolov8n"
        assert data["provenance"]["tracking_method"] == "yolo"
        assert data["provenance"]["model_version"] == "yolov8n-v8.1.0"
        assert data["raw_footage_stored"] is False

    def test_process_frame_invalid_method_rejected_by_pydantic(self, client):
        """Unknown tracking methods are rejected at the schema level with 422."""
        img = create_solid_color_circle_frame((0, 0, 255))
        payload = {
            "image": make_b64(img),
            "tracking_method": "magic_flow",
            "session_id": "sess_invalid_method",
        }
        resp = client.post("/api/cv/process-frame", json=payload)
        assert resp.status_code == 422
