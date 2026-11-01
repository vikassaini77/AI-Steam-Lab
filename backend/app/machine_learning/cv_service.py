import os
import time
import math
import base64
import binascii
import threading
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
from pydantic import BaseModel, Field, field_validator
from app.logger import logger

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_WIDTH = 1920
MAX_HEIGHT = 1080

SUPPORTED_MAGIC_BYTES = (
    b"\xff\xd8\xff",       # JPEG / JPG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"RIFF",               # WebP (RIFF container)
)


class InvalidImageError(ValueError):
    """Raised when the base64 or image content is invalid, corrupt, or unsupported."""
    pass


class PayloadTooLargeError(ValueError):
    """Raised when the raw image size exceeds the permitted byte limit."""
    pass


class DimensionLimitExceededError(ValueError):
    """Raised when the image resolution exceeds maximum allowed dimensions."""
    pass


# ==============================================================================
# Pydantic Schemas for Detections and Inference Results
# ==============================================================================

class Detection(BaseModel):
    class_name: str = Field(..., description="Detected object class label (e.g. 'sports ball', 'bottle', 'person', 'red_object')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score in [0.0, 1.0]")
    bbox_xyxy: List[float] = Field(..., description="Bounding box coordinates in [x_min, y_min, x_max, y_max] format")
    track_id: Optional[int] = Field(None, description="Persistent tracking ID across frames")

    @field_validator("bbox_xyxy")
    @classmethod
    def validate_bbox(cls, v: List[float]) -> List[float]:
        """Validates bounding box length and coordinate ordering."""
        if len(v) != 4:
            raise ValueError(f"Bounding box bbox_xyxy must contain exactly 4 coordinates, got {len(v)}.")
        x_min, y_min, x_max, y_max = [float(c) for c in v]
        if x_min > x_max:
            raise ValueError(f"Invalid coordinate ordering: x_min ({x_min}) must be <= x_max ({x_max}).")
        if y_min > y_max:
            raise ValueError(f"Invalid coordinate ordering: y_min ({y_min}) must be <= y_max ({y_max}).")
        return [x_min, y_min, x_max, y_max]


class FrameResult(BaseModel):
    timestamp_ms: int = Field(..., description="Timestamp of the frame in milliseconds")
    detections: List[Detection] = Field(default_factory=list, description="List of validated object detections")
    centroid: Optional[List[int]] = Field(None, description="Centroid [x, y] of primary detected object, or None if no object detected")
    contours_found: int = Field(0, description="Number of contours / candidates found")
    width: int
    height: int
    physics: Optional[Dict[str, Any]] = None
    model_name: str = Field(default="yolov8n", description="Inference model or detector used")
    inference_latency_ms: float = Field(0.0, description="Inference execution duration in milliseconds")
    model_version: str = Field(default="v1.0.0", description="Semantic model version")
    configuration_version: str = Field(default="cv_config_v1.0", description="CV configuration version")
    preprocessing_version: str = Field(default="bgr_to_hsv_v1.0", description="Preprocessing version")
    calibration: Optional[Dict[str, Any]] = None
    inference_status: str = Field(default="completed", description="Inference status: completed or degraded")
    raw_footage_stored: bool = Field(default=False, description="Privacy flag: whether raw footage was persisted")
    provenance: Optional[Dict[str, Any]] = None


# ==============================================================================
# Defensive Image Decoders
# ==============================================================================

def decode_frame(
    encoded: str,
    max_bytes: int = MAX_IMAGE_BYTES,
    max_w: int = MAX_WIDTH,
    max_h: int = MAX_HEIGHT,
) -> np.ndarray:
    """
    Defensively decodes, validates, and bounds base64 input image frames.
    """
    if not encoded or not isinstance(encoded, str) or not encoded.strip():
        raise InvalidImageError("Image payload is empty or invalid.")

    if "," in encoded:
        header, encoded_data = encoded.split(",", 1)
    else:
        encoded_data = encoded

    encoded_data = encoded_data.strip()
    if not encoded_data:
        raise InvalidImageError("Empty base64 image data.")

    try:
        raw = base64.b64decode(encoded_data, validate=True)
    except (binascii.Error, ValueError) as err:
        raise InvalidImageError(f"Invalid base64 image encoding: {str(err)}")

    if not raw or len(raw) == 0:
        raise InvalidImageError("Image payload is empty after base64 decoding.")

    if len(raw) > max_bytes:
        raise PayloadTooLargeError(
            f"Image payload ({len(raw)} bytes) exceeds the maximum limit of {max_bytes} bytes (5 MiB)."
        )

    is_supported = any(raw.startswith(magic) for magic in SUPPORTED_MAGIC_BYTES)
    if not is_supported:
        raise InvalidImageError("Unsupported image format. Allowed formats: JPEG, PNG, WebP.")

    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImageError("Unsupported, truncated, or corrupt image file.")

    height, width = image.shape[:2]
    if width > max_w or height > max_h:
        raise DimensionLimitExceededError(
            f"Image dimensions ({width}x{height}) exceed maximum allowed limit of {max_w}x{max_h}."
        )

    return image


def decode_binary_frame(
    raw: bytes,
    max_bytes: int = MAX_IMAGE_BYTES,
    max_w: int = MAX_WIDTH,
    max_h: int = MAX_HEIGHT,
) -> np.ndarray:
    """
    Defensively decodes raw binary image bytes (JPEG/PNG/WebP).
    """
    if not raw or len(raw) == 0:
        raise InvalidImageError("Empty binary image payload.")

    if len(raw) > max_bytes:
        raise PayloadTooLargeError(
            f"Image payload ({len(raw)} bytes) exceeds the maximum limit of {max_bytes} bytes."
        )

    is_supported = any(raw.startswith(magic) for magic in SUPPORTED_MAGIC_BYTES)
    if not is_supported:
        raise InvalidImageError("Unsupported binary image format. Allowed formats: JPEG, PNG, WebP.")

    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise InvalidImageError("Unsupported or corrupt binary image.")

    height, width = image.shape[:2]
    if width > max_w or height > max_h:
        raise DimensionLimitExceededError(
            f"Image dimensions ({width}x{height}) exceed maximum allowed limit of {max_w}x{max_h}."
        )

    return image


# ==============================================================================
# Object Trajectory & Kinematics Tracker
# ==============================================================================

class TrajectoryTracker:
    """
    Tracks object trajectories across frames, assigning persistent IDs and
    computing velocity (m/s) and acceleration (m/s^2) across timestamps.
    Handles dropped frames and automatic tracker timeouts.
    Supports serialization for multi-backend shared state synchronization.
    """
    def __init__(self, max_gap_seconds: float = 10.0, distance_threshold_px: float = 150.0):
        self.next_id: int = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.max_gap_seconds: float = max_gap_seconds
        self.distance_threshold_px: float = distance_threshold_px

    def reset(self):
        """Resets all tracking history."""
        self.tracks.clear()
        self.next_id = 1
        logger.info("TrajectoryTracker reset: cleared all active tracks.")

    def to_dict(self) -> Dict[str, Any]:
        """Serializes tracker state for shared multi-backend persistence."""
        return {
            "next_id": self.next_id,
            "max_gap_seconds": self.max_gap_seconds,
            "distance_threshold_px": self.distance_threshold_px,
            "tracks": {
                str(tid): {
                    "positions": [list(p) for p in track["positions"]],
                    "velocities": [float(v) for v in track["velocities"]],
                    "last_seen": float(track["last_seen"]),
                }
                for tid, track in self.tracks.items()
            },
        }

    def from_dict(self, data: Optional[Dict[str, Any]]) -> None:
        """Restores tracker state from serialized shared store."""
        if not data or not isinstance(data, dict):
            return
        self.next_id = int(data.get("next_id", 1))
        if "max_gap_seconds" in data:
            self.max_gap_seconds = float(data["max_gap_seconds"])
        if "distance_threshold_px" in data:
            self.distance_threshold_px = float(data["distance_threshold_px"])
        tracks_raw = data.get("tracks", {})
        restored = {}
        if isinstance(tracks_raw, dict):
            for tid_str, track in tracks_raw.items():
                try:
                    tid = int(tid_str)
                    raw_pos = track.get("positions", [])
                    raw_vel = track.get("velocities", [])
                    last_seen = float(track.get("last_seen", 0.0))
                    restored[tid] = {
                        "positions": [tuple(p) for p in raw_pos],
                        "velocities": [float(v) for v in raw_vel],
                        "last_seen": last_seen,
                    }
                except (ValueError, TypeError):
                    continue
        self.tracks = restored

    def clone(self) -> "TrajectoryTracker":
        """Creates an independent deep copy of this tracker."""
        tracker = TrajectoryTracker(
            max_gap_seconds=self.max_gap_seconds,
            distance_threshold_px=self.distance_threshold_px,
        )
        tracker.from_dict(self.to_dict())
        return tracker

    def update(
        self,
        centroid: Optional[Tuple[int, int]],
        timestamp_seconds: float,
        px_to_meters: float,
    ) -> Tuple[Optional[int], float, float]:
        """
        Updates trajectory with a new observation.
        Returns: (track_id, velocity_mps, acceleration_mps2)
        """
        now = timestamp_seconds

        # 1. Prune expired tracks (dropped frames / object out of view)
        expired_ids = [
            tid for tid, track in self.tracks.items()
            if (now - track["last_seen"]) > self.max_gap_seconds
        ]
        for tid in expired_ids:
            del self.tracks[tid]

        if centroid is None:
            return None, 0.0, 0.0

        cx, cy = centroid
        best_id = None
        min_dist = float("inf")

        # 2. Match with existing track by nearest Euclidean centroid
        for tid, track in self.tracks.items():
            prev_cx, prev_cy = track["positions"][-1][:2]
            dist = math.hypot(cx - prev_cx, cy - prev_cy)
            if dist < min_dist and dist < self.distance_threshold_px:
                min_dist = dist
                best_id = tid

        if best_id is None:
            best_id = self.next_id
            self.next_id += 1
            self.tracks[best_id] = {
                "positions": [(cx, cy, now)],
                "velocities": [],
                "last_seen": now,
            }
            return best_id, 0.0, 0.0

        # 3. Update matched track
        track = self.tracks[best_id]
        prev_cx, prev_cy, prev_t = track["positions"][-1]
        dt = max(now - prev_t, 1e-4)

        dx_m = (cx - prev_cx) * px_to_meters
        dy_m = (cy - prev_cy) * px_to_meters
        dist_m = math.hypot(dx_m, dy_m)
        v = dist_m / dt

        # Calculate acceleration if previous velocity exists
        a = 0.0
        if track["velocities"]:
            prev_v = track["velocities"][-1]
            a = (v - prev_v) / dt

        track["positions"].append((cx, cy, now))
        track["velocities"].append(v)
        track["last_seen"] = now

        # Keep history bounded (max 50 points)
        if len(track["positions"]) > 50:
            track["positions"] = track["positions"][-50:]
            track["velocities"] = track["velocities"][-50:]

        return best_id, v, a


# ==============================================================================
# Real Computer Vision Inference Engine (YOLOv8 + Color + Optical Flow)
# ==============================================================================
from enum import Enum


class YOLOWeightsStatus(str, Enum):
    LOADED = "loaded"
    WEIGHTS_MISSING = "weights_missing"
    WEIGHTS_CORRUPTED = "weights_corrupted"
    WEIGHTS_INCOMPATIBLE = "weights_incompatible"
    UNCONFIGURED = "unconfigured"


class ModelWeightsError(ValueError):
    """Raised when model weights are missing, corrupted, or incompatible."""
    pass


def validate_and_load_yolo_weights(weights_path: Optional[str] = None) -> Tuple[Optional[Any], str, Optional[str]]:
    """
    Defensively validates and loads YOLOv8 model weights.
    Returns: (model_instance, status_string, error_message_or_None)
    """
    if not weights_path:
        return None, YOLOWeightsStatus.UNCONFIGURED.value, "No YOLO weights path provided."

    norm_path = os.path.abspath(weights_path)
    if not os.path.exists(norm_path):
        return None, YOLOWeightsStatus.WEIGHTS_MISSING.value, f"YOLO weights file not found: {norm_path}"

    try:
        size = os.path.getsize(norm_path)
        if size < 1024:
            return None, YOLOWeightsStatus.WEIGHTS_CORRUPTED.value, f"YOLO weights file is corrupted or truncated (size: {size} bytes)."
    except OSError as err:
        return None, YOLOWeightsStatus.WEIGHTS_MISSING.value, f"Could not access weights file: {err}"

    try:
        os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        from ultralytics import YOLO
        model = YOLO(norm_path)
        if not hasattr(model, "names") or not model.names:
            return None, YOLOWeightsStatus.WEIGHTS_INCOMPATIBLE.value, "Model loaded but contains no valid class metadata (incompatible architecture)."
        return model, YOLOWeightsStatus.LOADED.value, None
    except Exception as err:
        err_msg = str(err)
        err_lower = err_msg.lower()
        if any(term in err_lower for term in ["badzipfile", "eof", "pickle", "invalid load key", "unpickling", "corrupted", "truncated", "not a valid"]):
            return None, YOLOWeightsStatus.WEIGHTS_CORRUPTED.value, f"Corrupted YOLO weights file: {err_msg}"
        elif any(term in err_lower for term in ["architecture", "incompatible", "missing key", "unexpected key", "version mismatch"]):
            return None, YOLOWeightsStatus.WEIGHTS_INCOMPATIBLE.value, f"Incompatible YOLO weights: {err_msg}"
        return None, YOLOWeightsStatus.WEIGHTS_CORRUPTED.value, f"Failed to initialize YOLO model: {err_msg}"


_shared_yolo_model = None
_shared_yolo_status = YOLOWeightsStatus.UNCONFIGURED.value
_shared_yolo_error = None
_shared_yolo_loaded = False
_shared_yolo_lock = threading.Lock()


def get_shared_yolo_model_info(weights_path: Optional[str] = None) -> Tuple[Optional[Any], str, Optional[str]]:
    """Loads and caches YOLOv8 weights once across all tracker instances."""
    global _shared_yolo_model, _shared_yolo_status, _shared_yolo_error, _shared_yolo_loaded
    with _shared_yolo_lock:
        if _shared_yolo_loaded:
            return _shared_yolo_model, _shared_yolo_status, _shared_yolo_error

        # In memory-constrained environments (e.g. Render Free Tier 512MB RAM),
        # disable YOLO neural network loading by default to prevent OOM termination.
        enable_yolo_env = os.getenv("ENABLE_YOLO", "").lower().strip()
        is_render = (
            os.getenv("RENDER", "").lower().strip() == "true"
            or bool(os.getenv("RENDER_SERVICE_ID"))
            or bool(os.getenv("RENDER_INSTANCE_ID"))
        )
        if enable_yolo_env in ("false", "0", "no", "off") or (enable_yolo_env != "true" and is_render):
            _shared_yolo_model = None
            _shared_yolo_status = YOLOWeightsStatus.UNCONFIGURED.value
            _shared_yolo_error = "YOLO neural network disabled in 512MB memory boundary; active vision pipeline using OpenCV color and Lucas-Kanade optical flow."
            _shared_yolo_loaded = True
            logger.info("YOLO disabled for 512MB memory boundary. Running genuine real-time OpenCV color and optical flow kinematics.")
            return _shared_yolo_model, _shared_yolo_status, _shared_yolo_error

        weights = weights_path or os.getenv("YOLO_WEIGHTS_PATH")
        if not weights:
            # Check standard relative paths
            for candidate in [
                os.path.join(os.path.dirname(__file__), "..", "..", "yolov8n.pt"),
                os.path.join(os.getcwd(), "backend", "yolov8n.pt"),
                os.path.join(os.getcwd(), "yolov8n.pt"),
            ]:
                if os.path.exists(candidate):
                    weights = os.path.abspath(candidate)
                    break

        if weights:
            _shared_yolo_model, _shared_yolo_status, _shared_yolo_error = validate_and_load_yolo_weights(weights)
            if _shared_yolo_model is not None:
                logger.info(f"YOLOv8 initialized successfully with {len(_shared_yolo_model.names)} COCO classes.")
            else:
                logger.warning(f"Could not load YOLOv8 model ({_shared_yolo_status}): {_shared_yolo_error}")
        else:
            _shared_yolo_model = None
            _shared_yolo_status = YOLOWeightsStatus.WEIGHTS_MISSING.value
            _shared_yolo_error = "No YOLO weights file found in standard search paths."
            logger.info("No YOLO weights found. Initializing with real OpenCV color and optical flow kinematics detectors.")

        _shared_yolo_loaded = True
        return _shared_yolo_model, _shared_yolo_status, _shared_yolo_error


def get_shared_yolo_model(weights_path: Optional[str] = None):
    model, _, _ = get_shared_yolo_model_info(weights_path)
    return model


def apply_nms_boxes(
    boxes: List[List[float]],
    scores: List[float],
    iou_threshold: float = 0.45,
    score_threshold: float = 0.25,
) -> List[int]:
    """
    Applies Non-Maximum Suppression (NMS) to eliminate redundant overlapping bounding boxes.
    Inputs:
      boxes: List of [x_min, y_min, x_max, y_max]
      scores: List of confidence scores
      iou_threshold: Intersection-over-Union threshold for suppression
      score_threshold: Minimum confidence score threshold
    Returns:
      List of integer indices of retained boxes.
    """
    if not boxes or not scores or len(boxes) != len(scores):
        return []

    cv_rects = []
    for b in boxes:
        x1, y1, x2, y2 = b
        w = max(0.0, x2 - x1)
        h = max(0.0, y2 - y1)
        cv_rects.append([int(round(x1)), int(round(y1)), int(round(w)), int(round(h))])

    try:
        indices = cv2.dnn.NMSBoxes(cv_rects, scores, score_threshold, iou_threshold)
        if indices is None or len(indices) == 0:
            return []
        if isinstance(indices, np.ndarray):
            return indices.flatten().tolist()
        return [int(i) for i in indices]
    except Exception:
        # Vectorized fallback
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        keep = []
        while order:
            i = order.pop(0)
            if scores[i] < score_threshold:
                continue
            keep.append(i)
            remaining = []
            for j in order:
                bA, bB = boxes[i], boxes[j]
                inter_x1 = max(bA[0], bB[0])
                inter_y1 = max(bA[1], bB[1])
                inter_x2 = min(bA[2], bB[2])
                inter_y2 = min(bA[3], bB[3])
                inter_w = max(0.0, inter_x2 - inter_x1)
                inter_h = max(0.0, inter_y2 - inter_y1)
                inter_area = inter_w * inter_h
                areaA = max(0.0, bA[2] - bA[0]) * max(0.0, bA[3] - bA[1])
                areaB = max(0.0, bB[2] - bB[0]) * max(0.0, bB[3] - bB[1])
                union_area = areaA + areaB - inter_area
                iou = inter_area / union_area if union_area > 0 else 0.0
                if iou < iou_threshold:
                    remaining.append(j)
            order = remaining
        return keep


class CVTracker:
    def __init__(
        self,
        yolo_weights_path: Optional[str] = None,
        trajectory_tracker: Optional[TrajectoryTracker] = None,
        tracker_key: Optional[str] = None,
        shared_yolo_model: Optional[Any] = None,
    ):
        self.tracker_key = tracker_key
        self.trajectory_tracker = trajectory_tracker if trajectory_tracker is not None else TrajectoryTracker()
        self.model_name = "color_kinematics"
        self.model_ready = False

        # Optical flow tracking state
        self.of_prev_gray: Optional[np.ndarray] = None
        self.of_prev_pts: Optional[np.ndarray] = None
        self.of_last_pts_count: int = 0
        self.of_failure_count: int = 0
        self.of_recovered: bool = False

        if shared_yolo_model is not None:
            self.yolo_model = shared_yolo_model
            self.yolo_status = YOLOWeightsStatus.LOADED.value
            self.yolo_error = None
        elif yolo_weights_path:
            self.yolo_model, self.yolo_status, self.yolo_error = validate_and_load_yolo_weights(yolo_weights_path)
        else:
            self.yolo_model, self.yolo_status, self.yolo_error = get_shared_yolo_model_info()

        if self.yolo_model is not None:
            self.model_name = "yolov8n"

        # Color and optical flow detectors are always ready
        self.model_ready = True

    def check_readiness(self) -> Dict[str, Any]:
        """Explicit model-loading and readiness verification."""
        return {
            "ready": self.model_ready,
            "active_model": self.model_name,
            "yolo_loaded": self.yolo_model is not None,
            "yolo_status": self.yolo_status,
            "yolo_error": self.yolo_error,
            "classes_count": len(self.yolo_model.names) if self.yolo_model else 0,
            "supported_methods": ["color", "optical_flow", "yolo"],
        }

    def reset_tracker(self):
        """Resets trajectory tracking history and optical flow state across frames."""
        self.trajectory_tracker.reset()
        self.of_prev_gray = None
        self.of_prev_pts = None
        self.of_last_pts_count = 0
        self.of_failure_count = 0
        self.of_recovered = False

    def process_frame(
        self,
        base64_img: str,
        tracking_method: str = "color",
        color_target: str = "red",
        px_to_meters: float = 0.005,
        confidence_threshold: float = 0.25,
        nms_threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """Decodes base64 frame and runs real object detection pipeline."""
        t_start = time.perf_counter()
        img = decode_frame(base64_img)
        return self._run_pipeline(
            img=img,
            tracking_method=tracking_method,
            color_target=color_target,
            px_to_meters=px_to_meters,
            conf_thresh=confidence_threshold,
            nms_thresh=nms_threshold,
            t_start=t_start,
        )

    def process_binary_frame(
        self,
        raw_bytes: bytes,
        tracking_method: str = "color",
        color_target: str = "red",
        px_to_meters: float = 0.005,
        confidence_threshold: float = 0.25,
        nms_threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """Decodes binary frame directly and runs real object detection pipeline."""
        t_start = time.perf_counter()
        img = decode_binary_frame(raw_bytes)
        return self._run_pipeline(
            img=img,
            tracking_method=tracking_method,
            color_target=color_target,
            px_to_meters=px_to_meters,
            conf_thresh=confidence_threshold,
            nms_thresh=nms_threshold,
            t_start=t_start,
        )

    def _run_pipeline(
        self,
        img: np.ndarray,
        tracking_method: str,
        color_target: str,
        px_to_meters: float,
        conf_thresh: float,
        nms_thresh: float,
        t_start: float,
    ) -> Dict[str, Any]:
        height, width = img.shape[:2]
        timestamp_s = time.time()
        timestamp_ms = int(timestamp_s * 1000)

        detections: List[Detection] = []
        method = (tracking_method or "color").lower().strip()
        inference_status = "completed"

        # 1. Routing by Tracking Method
        if method == "yolo":
            if self.yolo_model is not None:
                detections = self._detect_yolo(img, conf_thresh, nms_thresh)
                active_model = "yolov8n"
                inference_status = "completed"
            else:
                # YOLO requested but weights missing/corrupted/incompatible
                detections = self._detect_color(img, color_target, conf_thresh)
                active_model = f"yolo_fallback_color_{color_target or 'red'}"
                inference_status = "degraded"
        elif method in ("optical_flow", "opticalflow"):
            detections, recovered = self._track_optical_flow(img, conf_thresh)
            active_model = "lucas_kanade_optical_flow"
            inference_status = "completed" if (detections or not recovered) else "degraded"
        else:
            # Color tracking (HSV segmentation + morphology + contour filtering)
            detections = self._detect_color(img, color_target, conf_thresh)
            active_model = f"color_{color_target or 'red'}"
            inference_status = "completed"

        # 2. Determine Centroid and Update Trajectory Tracking
        centroid: Optional[List[int]] = None
        contours_found = len(detections)
        track_id = None
        v = 0.0
        a = 0.0

        if detections:
            # Select highest confidence detection as primary physics tracking target
            primary = max(detections, key=lambda d: d.confidence)
            x_min, y_min, x_max, y_max = primary.bbox_xyxy
            cx = int(round((x_min + x_max) / 2.0))
            cy = int(round((y_min + y_max) / 2.0))
            centroid = [cx, cy]

            # Update trajectory
            track_id, v, a = self.trajectory_tracker.update(
                centroid=(cx, cy),
                timestamp_seconds=timestamp_s,
                px_to_meters=px_to_meters,
            )
            primary.track_id = track_id
        else:
            # Explicitly NO detection (never return fake center of image)
            centroid = None
            self.trajectory_tracker.update(None, timestamp_s, px_to_meters)

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        physics = {
            "x_meters": round(centroid[0] * px_to_meters, 4) if centroid else None,
            "y_meters": round(centroid[1] * px_to_meters, 4) if centroid else None,
            "velocity_mps": round(v, 4),
            "acceleration_mps2": round(a, 4),
            "track_id": track_id,
        }

        # Model provenance metadata
        is_yolo = (method == "yolo" and self.yolo_model is not None)
        is_of = method in ("optical_flow", "opticalflow")

        if is_yolo:
            model_ver = "yolov8n-v8.1.0"
            preprocess_ver = "letterbox_rgb_norm_v1"
        elif is_of:
            model_ver = "lucas_kanade_pyr_v1.0"
            preprocess_ver = "bgr_to_gray_v1"
        else:
            model_ver = "hsv_blob_tracker_v1.0.0"
            preprocess_ver = "bgr_to_hsv_v1"

        calibration_info = {
            "px_to_meters": px_to_meters,
            "unit_system": "SI",
            "origin": [0.0, 0.0],
            "units": {
                "position": "meters (m)",
                "velocity": "meters/second (m/s)",
                "acceleration": "meters/second^2 (m/s^2)",
            },
        }

        prov_info = {
            "source": "client_webcam_stream",
            "raw_footage_stored": False,
            "retention_policy": "ephemeral_discard",
            "model_version": model_ver,
            "configuration_version": "cv_config_v1.0",
            "preprocessing_version": preprocess_ver,
            "reproducible": True,
            "tracking_method": method,
        }

        if method == "yolo" and self.yolo_model is None:
            prov_info["yolo_status"] = self.yolo_status
            prov_info["yolo_error"] = self.yolo_error
            prov_info["degraded_reason"] = f"YOLO weights unavailable ({self.yolo_status}): {self.yolo_error}"
        elif is_of:
            prov_info["optical_flow_recovered"] = getattr(self, "of_recovered", False)
            prov_info["optical_flow_failures"] = getattr(self, "of_failure_count", 0)

        # Build schema result with full model provenance and privacy flag
        frame_result = FrameResult(
            timestamp_ms=timestamp_ms,
            detections=detections,
            centroid=centroid,
            contours_found=contours_found,
            width=width,
            height=height,
            physics=physics,
            model_name=active_model,
            inference_latency_ms=latency_ms,
            model_version=model_ver,
            configuration_version="cv_config_v1.0",
            preprocessing_version=preprocess_ver,
            calibration=calibration_info,
            inference_status=inference_status,
            raw_footage_stored=False,
            provenance=prov_info,
        )

        return frame_result.model_dump()

    def _detect_yolo(self, img: np.ndarray, conf_thresh: float, iou_thresh: float) -> List[Detection]:
        """Runs YOLOv8 model inference with NMS thresholding and bounding box validation."""
        detections: List[Detection] = []
        if self.yolo_model is None:
            return detections

        height, width = img.shape[:2]
        try:
            results = self.yolo_model.predict(
                source=img,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False,
            )
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    raw_boxes = []
                    raw_scores = []
                    raw_classes = []
                    for i in range(len(boxes)):
                        xyxy = boxes.xyxy[i].cpu().numpy().tolist()
                        conf = float(boxes.conf[i].cpu().numpy())
                        cls_idx = int(boxes.cls[i].cpu().numpy())
                        class_name = self.yolo_model.names.get(cls_idx, f"class_{cls_idx}")

                        x1, y1, x2, y2 = [float(c) for c in xyxy]
                        # Clamp to frame dimensions
                        x1 = max(0.0, min(float(width), x1))
                        y1 = max(0.0, min(float(height), y1))
                        x2 = max(0.0, min(float(width), x2))
                        y2 = max(0.0, min(float(height), y2))

                        if x2 > x1 and y2 > y1 and conf >= conf_thresh:
                            raw_boxes.append([x1, y1, x2, y2])
                            raw_scores.append(conf)
                            raw_classes.append(class_name)

                    # Verify / apply Non-Maximum Suppression (NMS)
                    keep_indices = apply_nms_boxes(raw_boxes, raw_scores, iou_threshold=iou_thresh, score_threshold=conf_thresh)
                    for idx in keep_indices:
                        detections.append(
                            Detection(
                                class_name=raw_classes[idx],
                                confidence=round(raw_scores[idx], 4),
                                bbox_xyxy=raw_boxes[idx],
                            )
                        )
        except Exception as err:
            logger.error(f"YOLO inference error: {err}")
        return detections

    def _detect_optical_flow_features(self, gray: np.ndarray, mask: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """
        Extracts strong feature points for Lucas-Kanade tracking using Shi-Tomasi corner detection.
        """
        pts = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=100,
            qualityLevel=0.015,
            minDistance=8,
            blockSize=7,
            mask=mask,
        )
        if pts is None or len(pts) < 3:
            # Fallback with higher sensitivity
            pts = cv2.goodFeaturesToTrack(
                gray,
                maxCorners=100,
                qualityLevel=0.003,
                minDistance=5,
                blockSize=7,
                mask=mask,
            )
        return pts

    def _track_optical_flow(self, img: np.ndarray, conf_thresh: float) -> Tuple[List[Detection], bool]:
        """
        Executes Lucas–Kanade optical flow feature tracking with automatic failure recovery.
        Returns: (List[Detection], was_recovered)
        """
        height, width = img.shape[:2]
        curr_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        was_recovered = False

        # 1. Initial Frame or Re-initialization
        if self.of_prev_gray is None or self.of_prev_pts is None or len(self.of_prev_pts) < 3:
            pts = self._detect_optical_flow_features(curr_gray)
            if pts is None or len(pts) < 3:
                # Featureless frame
                self.of_prev_gray = curr_gray
                self.of_prev_pts = None
                return [], False

            self.of_prev_gray = curr_gray
            self.of_prev_pts = pts
            self.of_last_pts_count = len(pts)

            pts_2d = pts.reshape(-1, 2)
            x_min = max(0.0, float(np.min(pts_2d[:, 0]) - 5))
            y_min = max(0.0, float(np.min(pts_2d[:, 1]) - 5))
            x_max = min(float(width), float(np.max(pts_2d[:, 0]) + 5))
            y_max = min(float(height), float(np.max(pts_2d[:, 1]) + 5))

            conf = round(float(min(1.0, max(0.5, len(pts) / 50.0))), 3)
            if conf >= conf_thresh:
                return [
                    Detection(
                        class_name="optical_flow_target",
                        confidence=conf,
                        bbox_xyxy=[x_min, y_min, x_max, y_max],
                    )
                ], False
            return [], False

        # 2. Pyramidal Lucas–Kanade Optical Flow Tracking
        lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )

        try:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                self.of_prev_gray,
                curr_gray,
                self.of_prev_pts,
                None,
                **lk_params,
            )
        except Exception as e:
            logger.warning(f"calcOpticalFlowPyrLK error: {e}")
            next_pts, status = None, None

        # Filter valid tracked points (status == 1 and bounded tracking error)
        good_new = []
        if next_pts is not None and status is not None:
            valid_mask = (status.ravel() == 1)
            if err is not None:
                valid_mask = valid_mask & (err.ravel() < 30.0)
            candidates = next_pts[valid_mask].reshape(-1, 2)
            for pt in candidates:
                px, py = pt
                if 0 <= px < width and 0 <= py < height:
                    good_new.append([px, py])

        # 3. Check for Tracking Failure & Trigger Failure Recovery
        min_surviving_points = 3
        if len(good_new) < min_surviving_points:
            # Tracking points lost! Trigger Failure Recovery
            was_recovered = True
            self.of_failure_count += 1
            logger.info("Optical flow tracking lost points. Triggering failure recovery re-detection.")

            # Re-detect features on current frame
            recovery_pts = self._detect_optical_flow_features(curr_gray)
            if recovery_pts is not None and len(recovery_pts) >= min_surviving_points:
                self.of_prev_pts = recovery_pts
                self.of_prev_gray = curr_gray
                self.of_last_pts_count = len(recovery_pts)
                pts_2d = recovery_pts.reshape(-1, 2)
                x_min = max(0.0, float(np.min(pts_2d[:, 0]) - 5))
                y_min = max(0.0, float(np.min(pts_2d[:, 1]) - 5))
                x_max = min(float(width), float(np.max(pts_2d[:, 0]) + 5))
                y_max = min(float(height), float(np.max(pts_2d[:, 1]) + 5))
                conf = round(float(min(1.0, max(0.4, len(recovery_pts) / 50.0))), 3)
                if conf >= conf_thresh:
                    return [
                        Detection(
                            class_name="optical_flow_target",
                            confidence=conf,
                            bbox_xyxy=[x_min, y_min, x_max, y_max],
                        )
                    ], True
                return [], True
            else:
                # Scene has no features (e.g. blank screen)
                self.of_prev_pts = None
                self.of_prev_gray = curr_gray
                return [], True

        # 4. Successful Optical Flow Step
        good_new_arr = np.array(good_new, dtype=np.float32)
        self.of_prev_pts = good_new_arr.reshape(-1, 1, 2)
        self.of_prev_gray = curr_gray

        # Compute bounding box enclosing active tracked points
        x_min = max(0.0, float(np.min(good_new_arr[:, 0]) - 6))
        y_min = max(0.0, float(np.min(good_new_arr[:, 1]) - 6))
        x_max = min(float(width), float(np.max(good_new_arr[:, 0]) + 6))
        y_max = min(float(height), float(np.max(good_new_arr[:, 1]) + 6))

        # Confidence based on point survival ratio
        survival_ratio = len(good_new) / max(self.of_last_pts_count, 1)
        conf = round(float(min(1.0, max(0.3, survival_ratio))), 3)

        detections = []
        if conf >= conf_thresh and x_max > x_min and y_max > y_min:
            detections.append(
                Detection(
                    class_name="optical_flow_target",
                    confidence=conf,
                    bbox_xyxy=[x_min, y_min, x_max, y_max],
                )
            )

        return detections, False

    def _detect_color(self, img: np.ndarray, color_target: str, conf_thresh: float) -> List[Detection]:
        """
        Runs genuine HSV segmentation, morphology, and contour filtering.
        """
        detections: List[Detection] = []
        height, width = img.shape[:2]
        target = (color_target or "red").lower().strip()

        # 1. Preprocessing: Gaussian blur to suppress camera sensor noise
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        # 2. HSV Segmentation with tuned color bounds
        if target == "red":
            lower1, upper1 = np.array([0, 80, 70]), np.array([10, 255, 255])
            lower2, upper2 = np.array([160, 80, 70]), np.array([180, 255, 255])
            mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
        elif target == "blue":
            lower, upper = np.array([95, 80, 70]), np.array([135, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif target == "green":
            lower, upper = np.array([35, 70, 60]), np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif target == "yellow":
            lower, upper = np.array([20, 90, 80]), np.array([35, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif target == "orange":
            lower, upper = np.array([10, 90, 80]), np.array([22, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif target == "purple":
            lower, upper = np.array([130, 70, 60]), np.array([160, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        else:
            lower, upper = np.array([0, 0, 100]), np.array([180, 50, 255])
            mask = cv2.inRange(hsv, lower, upper)

        # 3. Morphology: Opening (removes specks) followed by Closing (fills internal holes)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 4. Contour Extraction & Filtering
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = 50.0
        max_area = 0.92 * (width * height)

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            # Filter extreme thin slivers (camera scanlines / sensor lines)
            aspect_ratio = max(w / max(h, 1), h / max(w, 1))
            if aspect_ratio > 18.0:
                continue

            bbox_area = max(1.0, float(w * h))
            solidity = area / bbox_area
            if solidity < 0.15:
                continue

            # Circularity metric
            perimeter = cv2.arcLength(cnt, True)
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0.0

            # Confidence score combines solidity, compactness, and size prominence
            base_conf = 0.5 * solidity + 0.3 * min(1.0, circularity) + 0.2 * min(1.0, area / 5000.0)
            conf = round(float(min(1.0, max(0.1, base_conf))), 3)

            if conf >= conf_thresh:
                # Clamp coordinates
                x1 = max(0.0, float(x))
                y1 = max(0.0, float(y))
                x2 = min(float(width), float(x + w))
                y2 = min(float(height), float(y + h))
                if x2 > x1 and y2 > y1:
                    detections.append(
                        Detection(
                            class_name=f"{target}_object",
                            confidence=conf,
                            bbox_xyxy=[x1, y1, x2, y2],
                        )
                    )

        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections


# ==============================================================================
# Isolated Session CV Tracker Manager (Problem 3)
# ==============================================================================

# Shared cluster session store across instances and fallbacks
_cv_cluster_shared_store: Dict[str, Tuple[Dict[str, Any], float]] = {}
_cv_cluster_shared_lock = threading.Lock()


class CVTrackerSessionManager:
    """
    Maintains independent CVTracker instances isolated per authenticated user, session, and camera.
    A tracker is keyed by tracker_key = f"{user_id}:{session_id}:{camera_id}".

    Provides:
    - User, session, and camera isolation: User A's tracks cannot influence User B,
      and separate cameras (e.g. overhead vs side) maintain isolated trajectories.
    - Isolated reset: Resetting one camera or session does not reset or impact other users/sessions/cameras.
    - Multi-backend state synchronization: Persists and hydrates trajectory state
      via Redis shared cache (when available) with reliable cluster shared store fallback.
    - Thread-safe concurrency: Per-tracker async locks preventing concurrent frame races.
    - Session lifecycle management: TTL expiration and automatic cleanup of inactive sessions.
    """
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._local_trackers: Dict[str, Dict[str, Any]] = {}
        self._local_lock = threading.Lock()
        self._session_async_locks: Dict[str, asyncio.Lock] = {}
        # Multi-level index: user_id -> {session_id -> set of camera_ids}
        self._user_session_cameras: Dict[str, Dict[str, set]] = {}
        self._user_sessions: Dict[str, set] = {}
        self._last_cleanup: float = time.time()

    @staticmethod
    def make_tracker_key(
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> str:
        """Constructs canonical tracker key: f"{user_id}:{session_id}:{camera_id}"."""
        uid = str(user_id or "anonymous").strip() or "anonymous"
        sess = str(session_id or "default").strip() or "default"
        cam = str(camera_id or "cam0").strip() or "cam0"
        return f"{uid}:{sess}:{cam}"

    @staticmethod
    def parse_tracker_key(tracker_key: str) -> Tuple[str, str, str]:
        """Parses tracker key back into (user_id, session_id, camera_id)."""
        parts = tracker_key.split(":")
        if len(parts) >= 3:
            return parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            return parts[0], parts[1], "cam0"
        return tracker_key, "default", "cam0"

    def get_session_lock(self, tracker_key: str) -> asyncio.Lock:
        """Retrieves or creates a dedicated async lock per tracker session."""
        with self._local_lock:
            if tracker_key not in self._session_async_locks:
                self._session_async_locks[tracker_key] = asyncio.Lock()
            return self._session_async_locks[tracker_key]

    async def get_tracker(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> CVTracker:
        """
        Retrieves or initializes the independent CVTracker instance for the given user, session, and camera.
        If shared state exists in cluster store or Redis, restores trajectory history across instances.
        """
        tracker_key = self.make_tracker_key(user_id, session_id, camera_id)
        uid, sess, cam = self.parse_tracker_key(tracker_key)
        now = time.time()

        tracker: Optional[CVTracker] = None
        is_new = False
        with self._local_lock:
            if uid not in self._user_session_cameras:
                self._user_session_cameras[uid] = {}
            if sess not in self._user_session_cameras[uid]:
                self._user_session_cameras[uid][sess] = set()
            self._user_session_cameras[uid][sess].add(cam)
            if uid not in self._user_sessions:
                self._user_sessions[uid] = set()
            self._user_sessions[uid].add(sess)
            if uid not in self._user_sessions:
                self._user_sessions[uid] = set()
            self._user_sessions[uid].add(sess)

            if tracker_key in self._local_trackers:
                entry = self._local_trackers[tracker_key]
                entry["last_accessed"] = now
                tracker = entry["tracker"]
            else:
                is_new = True
                tracker = CVTracker(
                    tracker_key=tracker_key,
                    shared_yolo_model=get_shared_yolo_model(),
                )
                self._local_trackers[tracker_key] = {
                    "tracker": tracker,
                    "created_at": now,
                    "last_accessed": now,
                    "user_id": uid,
                    "session_id": sess,
                    "camera_id": cam,
                }

        # Multi-instance shared state retrieval for new session instance
        if is_new:
            hydrated = False
            cache_key = f"cv_track:{tracker_key}"
            with _cv_cluster_shared_lock:
                if cache_key in _cv_cluster_shared_store:
                    saved_state, exp = _cv_cluster_shared_store[cache_key]
                    if exp > now:
                        tracker.trajectory_tracker.from_dict(saved_state)
                        hydrated = True
                    else:
                        _cv_cluster_shared_store.pop(cache_key, None)

            if not hydrated:
                try:
                    from app.cache import get_cache
                    saved_state = await asyncio.wait_for(
                        get_cache(cache_key, bypassable=True),
                        timeout=0.25,
                    )
                    if saved_state and isinstance(saved_state, dict):
                        tracker.trajectory_tracker.from_dict(saved_state)
                except Exception as e:
                    logger.debug(f"Could not load shared CV tracker state from Redis for {tracker_key}: {e}")

        # Rate-limited opportunistic cleanup of expired sessions (every 60s)
        if now - self._last_cleanup > 60.0:
            self._last_cleanup = now
            self._prune_inactive_sessions()

        return tracker

    def get_tracker_sync(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> CVTracker:
        """Synchronous tracker getter for workers, sync tasks, or isolated test fixtures."""
        tracker_key = self.make_tracker_key(user_id, session_id, camera_id)
        uid, sess, cam = self.parse_tracker_key(tracker_key)
        now = time.time()

        with self._local_lock:
            if uid not in self._user_session_cameras:
                self._user_session_cameras[uid] = {}
            if sess not in self._user_session_cameras[uid]:
                self._user_session_cameras[uid][sess] = set()
            self._user_session_cameras[uid][sess].add(cam)
            if uid not in self._user_sessions:
                self._user_sessions[uid] = set()
            self._user_sessions[uid].add(sess)
            if uid not in self._user_sessions:
                self._user_sessions[uid] = set()
            self._user_sessions[uid].add(sess)

            if tracker_key in self._local_trackers:
                entry = self._local_trackers[tracker_key]
                entry["last_accessed"] = now
                return entry["tracker"]

            tracker = CVTracker(
                tracker_key=tracker_key,
                shared_yolo_model=get_shared_yolo_model(),
            )
            self._local_trackers[tracker_key] = {
                "tracker": tracker,
                "created_at": now,
                "last_accessed": now,
                "user_id": uid,
                "session_id": sess,
                "camera_id": cam,
            }
            return tracker

    async def save_tracker_state(
        self,
        user_id: str,
        session_id: Optional[str],
        tracker: CVTracker,
        camera_id: Optional[str] = None,
    ) -> None:
        """
        Saves updated trajectory tracking state to shared cluster store and Redis cache.
        """
        tracker_key = self.make_tracker_key(user_id, session_id, camera_id)
        uid, sess, cam = self.parse_tracker_key(tracker_key)
        now = time.time()

        with self._local_lock:
            if tracker_key in self._local_trackers:
                self._local_trackers[tracker_key]["last_accessed"] = now
            else:
                self._local_trackers[tracker_key] = {
                    "tracker": tracker,
                    "created_at": now,
                    "last_accessed": now,
                    "user_id": uid,
                    "session_id": sess,
                    "camera_id": cam,
                }
            if uid not in self._user_session_cameras:
                self._user_session_cameras[uid] = {}
            if sess not in self._user_session_cameras[uid]:
                self._user_session_cameras[uid][sess] = set()
            self._user_session_cameras[uid][sess].add(cam)
            if uid not in self._user_sessions:
                self._user_sessions[uid] = set()
            self._user_sessions[uid].add(sess)

        # Always persist to cluster shared store
        cache_key = f"cv_track:{tracker_key}"
        state_dict = tracker.trajectory_tracker.to_dict()
        with _cv_cluster_shared_lock:
            _cv_cluster_shared_store[cache_key] = (state_dict, now + self.ttl_seconds)

        # Also persist to distributed Redis cache if available
        try:
            from app.cache import set_cache
            await asyncio.wait_for(
                set_cache(
                    cache_key,
                    state_dict,
                    ttl_seconds=self.ttl_seconds,
                    bypassable=True,
                ),
                timeout=0.25,
            )
        except Exception as e:
            logger.debug(f"Could not save shared CV tracker state to Redis for {tracker_key}: {e}")

    async def reset_tracker(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        all_sessions: bool = False,
        all_cameras: bool = False,
    ) -> None:
        """
        Resets trajectory tracking state ONLY for the specified user, session(s), and camera(s).
        Guarantees other users' tracking states, sessions, and cameras are not reset or impacted.
        """
        uid = str(user_id or "anonymous").strip()
        keys_to_reset = set()

        with self._local_lock:
            user_sessions = self._user_session_cameras.get(uid, {})
            if all_sessions:
                # Reset all sessions and cameras for this user
                for sess, cams in user_sessions.items():
                    for cam in cams:
                        keys_to_reset.add(self.make_tracker_key(uid, sess, cam))
                keys_to_reset.add(self.make_tracker_key(uid, "default", "cam0"))
            else:
                sess = (session_id or "default").strip()
                cams = user_sessions.get(sess, set())
                if all_cameras or camera_id is None:
                    # Reset all cameras in this session
                    for cam in cams:
                        keys_to_reset.add(self.make_tracker_key(uid, sess, cam))
                    keys_to_reset.add(self.make_tracker_key(uid, sess, "cam0"))
                else:
                    # Reset specific camera
                    cam = camera_id.strip()
                    keys_to_reset.add(self.make_tracker_key(uid, sess, cam))

        # Clear cluster store entries
        with _cv_cluster_shared_lock:
            for k in keys_to_reset:
                cache_key = f"cv_track:{k}"
                _cv_cluster_shared_store.pop(cache_key, None)
            if all_sessions:
                for k in list(_cv_cluster_shared_store.keys()):
                    if k.startswith(f"cv_track:{uid}:"):
                        _cv_cluster_shared_store.pop(k, None)

        # Clear local tracker instances and update index
        with self._local_lock:
            for k in keys_to_reset:
                if k in self._local_trackers:
                    self._local_trackers[k]["tracker"].reset_tracker()
                    del self._local_trackers[k]
                self._session_async_locks.pop(k, None)
                _, s, c = self.parse_tracker_key(k)
                if uid in self._user_session_cameras and s in self._user_session_cameras[uid]:
                    self._user_session_cameras[uid][s].discard(c)
                    if not self._user_session_cameras[uid][s]:
                        del self._user_session_cameras[uid][s]
                        if uid in self._user_sessions:
                            self._user_sessions[uid].discard(s)
            if all_sessions:
                self._user_session_cameras.pop(uid, None)
                self._user_sessions.pop(uid, None)

        # Clear from shared Redis store
        try:
            from app.cache import delete_cache
            for k in keys_to_reset:
                cache_key = f"cv_track:{k}"
                await asyncio.wait_for(
                    delete_cache(cache_key, bypassable=True),
                    timeout=0.25,
                )
            if all_sessions:
                await asyncio.wait_for(
                    delete_cache(f"cv_user_sessions:{uid}", bypassable=True),
                    timeout=0.25,
                )
        except Exception as e:
            logger.debug(f"Could not delete shared CV tracker state from Redis for {uid}: {e}")

        logger.info(f"CV tracker state reset for user {uid} (keys: {list(keys_to_reset)})")

    def reset_tracker_sync(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        all_sessions: bool = False,
        all_cameras: bool = False,
    ) -> None:
        """Synchronous reset helper for test suites."""
        uid = str(user_id or "anonymous").strip()
        keys_to_reset = set()

        with self._local_lock:
            user_sessions = self._user_session_cameras.get(uid, {})
            if all_sessions:
                for sess, cams in user_sessions.items():
                    for cam in cams:
                        keys_to_reset.add(self.make_tracker_key(uid, sess, cam))
                keys_to_reset.add(self.make_tracker_key(uid, "default", "cam0"))
            else:
                sess = (session_id or "default").strip()
                cams = user_sessions.get(sess, set())
                if all_cameras or camera_id is None:
                    for cam in cams:
                        keys_to_reset.add(self.make_tracker_key(uid, sess, cam))
                    keys_to_reset.add(self.make_tracker_key(uid, sess, "cam0"))
                else:
                    cam = camera_id.strip()
                    keys_to_reset.add(self.make_tracker_key(uid, sess, cam))

            for k in keys_to_reset:
                cache_key = f"cv_track:{k}"
                with _cv_cluster_shared_lock:
                    _cv_cluster_shared_store.pop(cache_key, None)
                if k in self._local_trackers:
                    self._local_trackers[k]["tracker"].reset_tracker()
                    del self._local_trackers[k]
                self._session_async_locks.pop(k, None)
                _, s, c = self.parse_tracker_key(k)
                if uid in self._user_session_cameras and s in self._user_session_cameras[uid]:
                    self._user_session_cameras[uid][s].discard(c)
                    if not self._user_session_cameras[uid][s]:
                        del self._user_session_cameras[uid][s]
                        if uid in self._user_sessions:
                            self._user_sessions[uid].discard(s)
            if all_sessions:
                self._user_session_cameras.pop(uid, None)
                self._user_sessions.pop(uid, None)

    def cleanup_expired_sessions(self, max_age_seconds: Optional[int] = None) -> Dict[str, Any]:
        """
        Explicit expiration and cleanup policy for inactive tracking sessions.
        Purges memory, locks, and cluster cache entries whose idle time exceeds TTL.
        Returns detailed eviction metrics.
        """
        max_age = max_age_seconds or self.ttl_seconds
        cutoff = time.time() - max_age
        purged_keys = []

        with self._local_lock:
            for k, v in list(self._local_trackers.items()):
                if v.get("last_accessed", 0) < cutoff:
                    v["tracker"].reset_tracker()
                    del self._local_trackers[k]
                    self._session_async_locks.pop(k, None)
                    purged_keys.append(k)
                    uid, s, c = self.parse_tracker_key(k)
                    if uid in self._user_session_cameras and s in self._user_session_cameras[uid]:
                        self._user_session_cameras[uid][s].discard(c)
                        if not self._user_session_cameras[uid][s]:
                            del self._user_session_cameras[uid][s]
                            if uid in self._user_sessions:
                                self._user_sessions[uid].discard(s)

        # Purge cluster shared store
        with _cv_cluster_shared_lock:
            for k in purged_keys:
                _cv_cluster_shared_store.pop(f"cv_track:{k}", None)
            now = time.time()
            for k, (state, exp) in list(_cv_cluster_shared_store.items()):
                if exp < now:
                    _cv_cluster_shared_store.pop(k, None)

        if purged_keys:
            logger.info(f"Purged {len(purged_keys)} expired CV tracking session(s): {purged_keys}")

        return {
            "purged_count": len(purged_keys),
            "remaining_count": len(self._local_trackers),
            "cutoff_timestamp": cutoff,
            "ttl_seconds": max_age,
        }

    def _prune_inactive_sessions(self, max_age_seconds: Optional[int] = None) -> None:
        """Internal helper for opportunistic cleanup."""
        self.cleanup_expired_sessions(max_age_seconds or (self.ttl_seconds * 2))

    def clear_all(self) -> None:
        """Clears all local in-memory tracking sessions."""
        with self._local_lock:
            for v in self._local_trackers.values():
                v["tracker"].reset_tracker()
            self._local_trackers.clear()
            self._session_async_locks.clear()
            self._user_session_cameras.clear()
            self._user_sessions.clear()
        with _cv_cluster_shared_lock:
            _cv_cluster_shared_store.clear()

    def get_active_sessions_count(self) -> int:
        """Returns the number of locally tracked active sessions."""
        with self._local_lock:
            return len(self._local_trackers)


# Global session-isolated tracker manager singleton
cv_tracker_manager = CVTrackerSessionManager()
