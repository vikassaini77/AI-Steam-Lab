import os
import time
import math
import base64
import binascii
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
    """
    def __init__(self, max_gap_seconds: float = 1.5, distance_threshold_px: float = 150.0):
        self.next_id: int = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.max_gap_seconds: float = max_gap_seconds
        self.distance_threshold_px: float = distance_threshold_px

    def reset(self):
        """Resets all tracking history."""
        self.tracks.clear()
        self.next_id = 1
        logger.info("TrajectoryTracker reset: cleared all active tracks.")

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
# Real Computer Vision Inference Engine (YOLOv8 + Color Kinematics)
# ==============================================================================

class CVTracker:
    def __init__(self, yolo_weights_path: Optional[str] = None):
        self.yolo_model = None
        self.model_name = "color_kinematics"
        self.model_ready = False
        self.trajectory_tracker = TrajectoryTracker()

        # Locate weights
        weights = yolo_weights_path or os.getenv("YOLO_WEIGHTS_PATH")
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

        if weights and os.path.exists(weights):
            try:
                from ultralytics import YOLO
                logger.info(f"Loading real YOLOv8 weights from: {weights}")
                self.yolo_model = YOLO(weights)
                self.model_name = "yolov8n"
                self.model_ready = True
                logger.info(f"YOLOv8 initialized successfully with {len(self.yolo_model.names)} COCO classes.")
            except Exception as err:
                logger.warning(f"Could not initialize YOLOv8 weights: {err}. Falling back to color kinematics detector.")
                self.yolo_model = None
        else:
            logger.info("No YOLO weights found. Initializing with real OpenCV color-space kinematics detector.")

        # Color detector is always ready
        self.model_ready = True

    def check_readiness(self) -> Dict[str, Any]:
        """Explicit model-loading and readiness verification."""
        return {
            "ready": self.model_ready,
            "active_model": self.model_name,
            "yolo_loaded": self.yolo_model is not None,
            "classes_count": len(self.yolo_model.names) if self.yolo_model else 0,
            "supported_methods": ["color", "yolo"],
        }

    def reset_tracker(self):
        """Resets trajectory tracking history across frames."""
        self.trajectory_tracker.reset()

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
        method = (tracking_method or "color").lower()

        # 1. Run YOLOv8 Detector if requested and available
        if method == "yolo" and self.yolo_model is not None:
            detections = self._detect_yolo(img, conf_thresh, nms_thresh)
            active_model = "yolov8n"
        else:
            # 2. Run real HSV Color Blob Detector
            detections = self._detect_color(img, color_target, conf_thresh)
            active_model = f"color_{color_target or 'red'}"

        # 3. Determine Centroid and Update Trajectory Tracking
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

        # Build schema result
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
        )

        return frame_result.model_dump()

    def _detect_yolo(self, img: np.ndarray, conf_thresh: float, iou_thresh: float) -> List[Detection]:
        """Runs YOLOv8 model inference with NMS thresholding."""
        detections: List[Detection] = []
        try:
            results = self.yolo_model.predict(
                source=img,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False,
            )
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        xyxy = boxes.xyxy[i].cpu().numpy().tolist()
                        conf = float(boxes.conf[i].cpu().numpy())
                        cls_idx = int(boxes.cls[i].cpu().numpy())
                        class_name = self.yolo_model.names.get(cls_idx, f"class_{cls_idx}")

                        # Ensure valid coordinates
                        x1, y1, x2, y2 = [max(0.0, float(c)) for c in xyxy]
                        if x2 >= x1 and y2 >= y1 and conf >= conf_thresh:
                            detections.append(
                                Detection(
                                    class_name=class_name,
                                    confidence=round(conf, 4),
                                    bbox_xyxy=[x1, y1, x2, y2],
                                )
                            )
        except Exception as err:
            logger.error(f"YOLO inference error: {err}")
        return detections

    def _detect_color(self, img: np.ndarray, color_target: str, conf_thresh: float) -> List[Detection]:
        """Runs real color-space contour detection and bounding box extraction."""
        detections: List[Detection] = []
        height, width = img.shape[:2]
        target = (color_target or "red").lower()

        # Preprocessing: bilateral filter / Gaussian blur to reduce camera noise
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        if target == "red":
            lower1, upper1 = np.array([0, 90, 80]), np.array([10, 255, 255])
            lower2, upper2 = np.array([160, 90, 80]), np.array([180, 255, 255])
            mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
        elif target == "blue":
            lower, upper = np.array([95, 90, 80]), np.array([135, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        elif target == "green":
            lower, upper = np.array([35, 80, 70]), np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        else:
            lower, upper = np.array([0, 0, 100]), np.array([180, 50, 255])
            mask = cv2.inRange(hsv, lower, upper)

        # Morphological opening and closing to clean small noise specks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = 50.0  # Minimum pixel area to eliminate stray single-pixel artifacts

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(cnt)
                bbox_area = max(1.0, float(w * h))
                # Solidity/density estimate for confidence score
                solidity = min(1.0, max(0.1, area / bbox_area))
                conf = round(float(solidity), 3)

                if conf >= conf_thresh:
                    detections.append(
                        Detection(
                            class_name=f"{target}_object",
                            confidence=conf,
                            bbox_xyxy=[float(x), float(y), float(x + w), float(y + h)],
                        )
                    )

        # Sort detections descending by area/confidence
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections
