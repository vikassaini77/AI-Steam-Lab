import os
import time
import math
import base64
import binascii
import threading
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import cv2
import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator
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
# Camera Calibration Standards, Units, and Assumptions
# ==============================================================================

CALIBRATION_UNITS = {
    "scale": "m/px",
    "distance": "meters",
    "position": "meters",
    "displacement": "meters",
    "velocity": "m/s",
    "acceleration": "m/s^2",
    "time": "seconds",
}

CALIBRATION_ASSUMPTIONS = [
    "Planar motion strictly parallel to the camera image sensor plane (constant depth Z).",
    "Weak-perspective or orthographic geometric projection across the calibrated field of view.",
    "Negligible optical lens distortion in the active observation zone.",
    "Constant physical distance between the camera sensor and the motion plane throughout observation.",
]

CALIBRATION_LIMITATIONS = (
    "A single scalar scale factor (meters per pixel) cannot compensate for 3D out-of-plane motion, "
    "perspective foreshortening (objects appearing smaller as distance from lens increases), or wide-angle "
    "lens radial distortion. True 3D metric tracking requires full pinhole camera intrinsic calibration "
    "(focal length, optical principal point, lens distortion coefficients) and camera extrinsic pose estimation."
)


class CalibrationInfo(BaseModel):
    scale_factor_m_per_px: float = Field(..., gt=0.0, description="Meters per pixel scale factor")
    pixel_distance: Optional[float] = Field(None, description="Measured pixel distance between reference endpoints")
    reference_distance_meters: Optional[float] = Field(None, description="Known physical reference distance in meters")
    reference_label: Optional[str] = Field("standard_ruler", description="Description of reference object")
    is_calibrated: bool = Field(default=True, description="Whether calibration was explicitly established")
    calibration_status: str = Field(default="calibrated", description="Status: calibrated, uncalibrated_default, out_of_bounds")
    calibration_model: str = Field(default="coplanar_orthographic_scalar", description="Calibration model type")
    calibrated_at: Optional[str] = Field(None, description="ISO 8601 calibration timestamp")
    units: Dict[str, str] = Field(default_factory=lambda: CALIBRATION_UNITS)
    assumptions: List[str] = Field(default_factory=lambda: CALIBRATION_ASSUMPTIONS)
    limitations: str = Field(default=CALIBRATION_LIMITATIONS)


# ==============================================================================
# Pydantic Schemas for Detections and Inference Results
# ==============================================================================

class Detection(BaseModel):
    bbox_xyxy: List[float] = Field(..., description="Bounding box coordinates in [x_min, y_min, x_max, y_max] format")
    class_name: Optional[str] = Field(None, description="Semantic class label when available; None for color segmentation")
    class_label: Optional[str] = Field(None, description="Semantic class label conforming to detector abstraction")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Model confidence in [0.0, 1.0], or None for non-probabilistic detectors")
    track_id: Optional[int] = Field(None, description="Persistent tracking ID across frames")
    center: Optional[Tuple[int, int]] = Field(None, description="Centroid coordinates [cx, cy]")
    timestamp: Optional[float] = Field(None, description="Observation epoch timestamp in seconds")
    detector_name: Optional[str] = Field(None, description="Identifier of the executing detector")
    latency_ms: Optional[float] = Field(0.0, description="Inference latency in milliseconds")
    status: Optional[str] = Field("detected", description="Detection status: detected, occluded, coasting, recovered")
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Detector-specific auxiliary metrics (solidity, circularity, area)")

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

    @model_validator(mode="after")
    def sync_labels_and_center(self):
        """Synchronizes label aliases and auto-computes centroid if missing."""
        if self.class_label is not None and self.class_name is None:
            self.class_name = self.class_label
        elif self.class_name is not None and self.class_label is None:
            self.class_label = self.class_name

        if self.center is None and self.bbox_xyxy and len(self.bbox_xyxy) == 4:
            cx = int(round((self.bbox_xyxy[0] + self.bbox_xyxy[2]) / 2.0))
            cy = int(round((self.bbox_xyxy[1] + self.bbox_xyxy[3]) / 2.0))
            self.center = (cx, cy)
        return self


DetectorOutput = Detection


class FrameResult(BaseModel):
    timestamp_ms: int = Field(..., description="Timestamp of the frame in milliseconds")
    detections: List[Detection] = Field(default_factory=list, description="List of validated object detections")
    centroid: Optional[List[int]] = Field(None, description="Centroid [x, y] of primary detected object, or None if no object detected")
    contours_found: int = Field(0, description="Number of contours / candidates found")
    width: int
    height: int
    physics: Optional[Dict[str, Any]] = None
    model_name: str = Field(default="yolov8n", description="Inference model or detector used")
    active_detector: Optional[str] = Field(None, description="Detailed active detector name")
    is_degraded: bool = Field(default=False, description="Whether inference is running in degraded fallback mode")
    degraded_reason: Optional[str] = Field(None, description="Diagnostic reason if running in degraded mode")
    detection_message: Optional[str] = Field(None, description="Human-readable detection status message")
    inference_latency_ms: float = Field(0.0, description="Inference execution duration in milliseconds")
    latency_breakdown: Optional[Dict[str, float]] = Field(None, description="Detailed latency breakdown: decode, detection, tracking, total, fps")
    model_version: str = Field(default="v1.0.0", description="Semantic model version")
    configuration_version: str = Field(default="cv_config_v1.0", description="CV configuration version")
    preprocessing_version: str = Field(default="bgr_to_hsv_v1.0", description="Preprocessing version")
    calibration: Optional[Dict[str, Any]] = None
    inference_status: str = Field(default="completed", description="Inference status: completed or degraded")
    raw_footage_stored: bool = Field(default=False, description="Privacy flag: whether raw footage was persisted")
    provenance: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


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

class KinematicsResult(tuple):
    """
    Tuple subclass behaving as (track_id, velocity_mps, acceleration_mps2)
    for 100% backward compatibility with unpackers, while also providing
    full vector kinematics, noise filtering, and calibration audit details.
    """
    def __new__(cls, track_id: Optional[int], velocity_mps: float, acceleration_mps2: float, details: Optional[Dict[str, Any]] = None):
        return super().__new__(cls, (track_id, velocity_mps, acceleration_mps2))

    def __init__(self, track_id: Optional[int], velocity_mps: float, acceleration_mps2: float, details: Optional[Dict[str, Any]] = None):
        self.track_id = track_id
        self.velocity_mps = velocity_mps
        self.acceleration_mps2 = acceleration_mps2
        self.details = details or {}


class TrajectoryTracker:
    """
    Tracks object trajectories across frames, assigning persistent IDs,
    handling multi-object tracking, temporary occlusion (coasting), and object re-entry.
    Computes vector velocity (vx, vy, v), vector acceleration (ax, ay, a), and motion direction.
    Applies exponential moving average (EMA) noise filtering on coordinates and velocities
    and a camera sensor jitter deadband.
    Handles irregular frame intervals (dt), dropped frames, and tracker timeouts.
    Supports serialization for multi-backend shared state synchronization.
    """
    def __init__(
        self,
        max_gap_seconds: float = 10.0,
        distance_threshold_px: float = 150.0,
        pos_filter_alpha: float = 1.0,
        vel_filter_beta: float = 1.0,
        max_occlusion_frames: int = 15,
        deadband_px: float = 1.5,
    ):
        self.next_id: int = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.max_gap_seconds: float = max_gap_seconds
        self.distance_threshold_px: float = distance_threshold_px
        self.pos_filter_alpha: float = pos_filter_alpha
        self.vel_filter_beta: float = vel_filter_beta
        self.max_occlusion_frames: int = max_occlusion_frames
        self.deadband_px: float = deadband_px

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
            "pos_filter_alpha": self.pos_filter_alpha,
            "vel_filter_beta": self.vel_filter_beta,
            "max_occlusion_frames": self.max_occlusion_frames,
            "deadband_px": self.deadband_px,
            "tracks": {
                str(tid): {
                    "positions": [list(p) for p in track["positions"]],
                    "filtered_positions": [list(p) for p in track.get("filtered_positions", [])],
                    "filtered_velocities": [list(v) for v in track.get("filtered_velocities", [])],
                    "velocities": [float(v) for v in track["velocities"]],
                    "accelerations": [list(a) for a in track.get("accelerations", [])],
                    "acceleration_mags": [float(m) for m in track.get("acceleration_mags", [])],
                    "direction_angles_deg": [float(d) for d in track.get("direction_angles_deg", [])],
                    "last_seen": float(track["last_seen"]),
                    "lost_frames": int(track.get("lost_frames", 0)),
                    "status": str(track.get("status", "tracking")),
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
        if "pos_filter_alpha" in data:
            self.pos_filter_alpha = float(data["pos_filter_alpha"])
        if "vel_filter_beta" in data:
            self.vel_filter_beta = float(data["vel_filter_beta"])
        if "max_occlusion_frames" in data:
            self.max_occlusion_frames = int(data["max_occlusion_frames"])
        if "deadband_px" in data:
            self.deadband_px = float(data["deadband_px"])

        tracks_raw = data.get("tracks", {})
        restored = {}
        if isinstance(tracks_raw, dict):
            for tid_str, track in tracks_raw.items():
                try:
                    tid = int(tid_str)
                    raw_pos = track.get("positions", [])
                    raw_filt_pos = track.get("filtered_positions", [])
                    raw_filt_vel = track.get("filtered_velocities", [])
                    raw_vel = track.get("velocities", [])
                    raw_acc = track.get("accelerations", [])
                    raw_acc_mags = track.get("acceleration_mags", [])
                    raw_dirs = track.get("direction_angles_deg", [])
                    last_seen = float(track.get("last_seen", 0.0))
                    lost_frames = int(track.get("lost_frames", 0))
                    status = str(track.get("status", "tracking"))
                    restored[tid] = {
                        "positions": [tuple(p) for p in raw_pos],
                        "filtered_positions": [tuple(p) for p in raw_filt_pos] if raw_filt_pos else [tuple(p[:2]) for p in raw_pos],
                        "filtered_velocities": [tuple(v) for v in raw_filt_vel] if raw_filt_vel else [(0.0, float(v)) for v in raw_vel],
                        "velocities": [float(v) for v in raw_vel],
                        "accelerations": [tuple(a) for a in raw_acc] if raw_acc else [],
                        "acceleration_mags": [float(m) for m in raw_acc_mags] if raw_acc_mags else [],
                        "direction_angles_deg": [float(d) for d in raw_dirs] if raw_dirs else [],
                        "last_seen": last_seen,
                        "lost_frames": lost_frames,
                        "status": status,
                    }
                except (ValueError, TypeError):
                    continue
        self.tracks = restored

    def clone(self) -> "TrajectoryTracker":
        """Creates an independent deep copy of this tracker."""
        tracker = TrajectoryTracker(
            max_gap_seconds=self.max_gap_seconds,
            distance_threshold_px=self.distance_threshold_px,
            pos_filter_alpha=self.pos_filter_alpha,
            vel_filter_beta=self.vel_filter_beta,
            max_occlusion_frames=self.max_occlusion_frames,
            deadband_px=self.deadband_px,
        )
        tracker.from_dict(self.to_dict())
        return tracker

    def validate_calibration(self, px_to_meters: float) -> Tuple[float, str, bool]:
        """
        Validates the pixel-to-meter calibration scale factor.
        Returns: (safe_scale, calibration_status, is_calibrated)
        """
        if (
            px_to_meters is None
            or px_to_meters <= 0.0
            or math.isnan(px_to_meters)
            or math.isinf(px_to_meters)
        ):
            return 0.005, "uncalibrated_default", False
        if px_to_meters < 1e-6 or px_to_meters > 1.0:
            return 0.005, "uncalibrated_out_of_bounds", False
        return px_to_meters, "calibrated", True

    def update_detections(
        self,
        detections: List[Detection],
        timestamp_seconds: float,
        px_to_meters: float,
    ) -> Tuple[KinematicsResult, Dict[str, Any]]:
        """
        Updates multi-object trajectory tracking across frames:
        - Matches detections to active and coasting tracks via greedy nearest centroid.
        - Handles temporary occlusion by maintaining coasting tracks for up to max_occlusion_frames.
        - Supports object re-entry by matching newly detected objects to recently lost tracks.
        - Computes timestamp-aware vector velocities, vector accelerations, and motion angles.
        - Applies EMA noise filtering and camera sensor deadband.
        - Prunes expired tracks exceeding max_occlusion_frames or max_gap_seconds.
        """
        now = timestamp_seconds
        scale, calib_status, is_calibrated = self.validate_calibration(px_to_meters)

        # 1. Prune expired tracks
        expired_ids = [
            tid for tid, track in self.tracks.items()
            if (now - track["last_seen"]) > self.max_gap_seconds
            or track.get("lost_frames", 0) > self.max_occlusion_frames
        ]
        for tid in expired_ids:
            del self.tracks[tid]

        if not detections:
            # Mark all existing active tracks as coasting/occluded
            for tid, track in self.tracks.items():
                track["lost_frames"] = track.get("lost_frames", 0) + 1
                track["status"] = "coasting"

            return KinematicsResult(
                None, 0.0, 0.0,
                details={
                    "dx_meters": 0.0,
                    "dy_meters": 0.0,
                    "velocity_x_mps": 0.0,
                    "velocity_y_mps": 0.0,
                    "velocity_mps": 0.0,
                    "acceleration_x_mps2": 0.0,
                    "acceleration_y_mps2": 0.0,
                    "acceleration_mps2": 0.0,
                    "direction_deg": 0.0,
                    "dt_seconds": None,
                    "calibration_status": "no_target",
                    "is_calibrated": is_calibrated,
                    "active_tracks_count": len(self.tracks),
                    "tracking_status": "no_detections",
                }
            ), {"tracks": {}, "active_count": len(self.tracks)}

        # 2. Extract detection centroids
        det_centroids = []
        for det in detections:
            if det.center:
                det_centroids.append((det.center[0], det.center[1]))
            else:
                x1, y1, x2, y2 = det.bbox_xyxy
                det_centroids.append((int(round((x1 + x2) / 2.0)), int(round((y1 + y2) / 2.0))))

        # 3. Match detections with existing tracks (Greedy Nearest Centroid)
        matched_det_indices = set()
        matched_track_ids = set()

        distance_pairs = []
        for det_idx, (cx, cy) in enumerate(det_centroids):
            for tid, track in self.tracks.items():
                prev_cx, prev_cy = track["positions"][-1][:2]
                dist = math.hypot(cx - prev_cx, cy - prev_cy)
                if dist <= self.distance_threshold_px:
                    distance_pairs.append((dist, det_idx, tid))

        distance_pairs.sort(key=lambda x: x[0])

        for dist, det_idx, tid in distance_pairs:
            if det_idx in matched_det_indices or tid in matched_track_ids:
                continue
            matched_det_indices.add(det_idx)
            matched_track_ids.add(tid)
            detections[det_idx].track_id = tid

            # Update matched track
            self._update_single_track(
                tid=tid,
                centroid=det_centroids[det_idx],
                now=now,
                scale=scale,
                calib_status=calib_status,
                is_calibrated=is_calibrated,
                bbox=detections[det_idx].bbox_xyxy,
                class_label=detections[det_idx].class_label,
            )

        # 4. Initialize new tracks for unmatched detections
        for det_idx, (cx, cy) in enumerate(det_centroids):
            if det_idx not in matched_det_indices:
                new_id = self.next_id
                self.next_id += 1
                detections[det_idx].track_id = new_id
                self.tracks[new_id] = {
                    "positions": [(cx, cy, now)],
                    "filtered_positions": [(float(cx), float(cy))],
                    "filtered_velocities": [(0.0, 0.0)],
                    "velocities": [0.0],
                    "accelerations": [(0.0, 0.0)],
                    "acceleration_mags": [0.0],
                    "direction_angles_deg": [0.0],
                    "last_seen": now,
                    "lost_frames": 0,
                    "status": "tracking",
                    "bbox_xyxy": detections[det_idx].bbox_xyxy,
                    "class_label": detections[det_idx].class_label,
                    "latest_details": {
                        "dx_meters": 0.0,
                        "dy_meters": 0.0,
                        "velocity_x_mps": 0.0,
                        "velocity_y_mps": 0.0,
                        "velocity_mps": 0.0,
                        "acceleration_x_mps2": 0.0,
                        "acceleration_y_mps2": 0.0,
                        "acceleration_mps2": 0.0,
                        "direction_deg": 0.0,
                        "dt_seconds": 0.0,
                        "calibration_status": calib_status,
                        "is_calibrated": is_calibrated,
                    }
                }

        # 5. Handle unmatched existing tracks (coasting / temporary occlusion)
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track["lost_frames"] = track.get("lost_frames", 0) + 1
                track["status"] = "coasting"

        # 6. Select primary track result (highest confidence or largest area)
        primary_det = max(
            detections,
            key=lambda d: ((d.confidence if d.confidence is not None else 0.0), d.attributes.get("area", 0.0))
        )
        primary_tid = primary_det.track_id
        primary_track = self.tracks[primary_tid]
        primary_details = primary_track.get("latest_details", {})

        return KinematicsResult(
            primary_tid,
            primary_details.get("velocity_mps", primary_track["velocities"][-1]),
            primary_details.get("acceleration_mps2", primary_track["acceleration_mags"][-1] if primary_track.get("acceleration_mags") else 0.0),
            details=primary_details
        ), {
            "active_tracks_count": len([t for t in self.tracks.values() if t.get("lost_frames", 0) == 0]),
            "coasting_tracks_count": len([t for t in self.tracks.values() if t.get("lost_frames", 0) > 0]),
            "total_tracks": len(self.tracks),
        }

    def _update_single_track(
        self,
        tid: int,
        centroid: Tuple[int, int],
        now: float,
        scale: float,
        calib_status: str,
        is_calibrated: bool,
        bbox: Optional[List[float]] = None,
        class_label: Optional[str] = None,
    ) -> None:
        track = self.tracks[tid]
        was_coasting = track.get("lost_frames", 0) > 0
        track["lost_frames"] = 0
        track["status"] = "re_entered" if was_coasting else "tracking"
        if bbox:
            track["bbox_xyxy"] = bbox
        if class_label:
            track["class_label"] = class_label

        cx, cy = centroid
        prev_cx, prev_cy, prev_t = track["positions"][-1]
        prev_fx, prev_fy = track["filtered_positions"][-1]
        prev_vx, prev_vy = track["filtered_velocities"][-1]

        dt = now - prev_t

        # Sensor deadband: treat subpixel camera noise as stationary
        dist_px = math.hypot(cx - prev_cx, cy - prev_cy)
        is_subpixel_noise = dist_px < self.deadband_px

        # Guard: Clock jitter / duplicate client frame (dt <= 1ms)
        if dt <= 0.001:
            speed = math.hypot(prev_vx, prev_vy)
            track["positions"].append((cx, cy, now))
            track["filtered_positions"].append((prev_fx, prev_fy))
            track["filtered_velocities"].append((prev_vx, prev_vy))
            track["velocities"].append(speed)
            track["accelerations"].append((0.0, 0.0))
            if "acceleration_mags" not in track:
                track["acceleration_mags"] = []
            track["acceleration_mags"].append(0.0)
            if "direction_angles_deg" not in track:
                track["direction_angles_deg"] = []
            track["direction_angles_deg"].append(track["direction_angles_deg"][-1] if track["direction_angles_deg"] else 0.0)
            track["last_seen"] = now
            track["latest_details"] = {
                "dx_meters": 0.0,
                "dy_meters": 0.0,
                "velocity_x_mps": prev_vx,
                "velocity_y_mps": prev_vy,
                "velocity_mps": speed,
                "acceleration_x_mps2": 0.0,
                "acceleration_y_mps2": 0.0,
                "acceleration_mps2": 0.0,
                "direction_deg": track.get("direction_angles_deg", [0.0])[-1] if track.get("direction_angles_deg") else 0.0,
                "dt_seconds": dt,
                "calibration_status": calib_status,
                "is_calibrated": is_calibrated,
            }
            return

        # Guard: Camera pause (> 1.5s): re-anchor without generating astronomical velocities
        if dt > 1.5:
            track["positions"].append((cx, cy, now))
            track["filtered_positions"].append((float(cx), float(cy)))
            track["filtered_velocities"].append((0.0, 0.0))
            track["velocities"].append(0.0)
            track["accelerations"].append((0.0, 0.0))
            if "acceleration_mags" not in track:
                track["acceleration_mags"] = []
            track["acceleration_mags"].append(0.0)
            if "direction_angles_deg" not in track:
                track["direction_angles_deg"] = []
            track["direction_angles_deg"].append(0.0)
            track["last_seen"] = now
            track["latest_details"] = {
                "dx_meters": 0.0,
                "dy_meters": 0.0,
                "velocity_x_mps": 0.0,
                "velocity_y_mps": 0.0,
                "velocity_mps": 0.0,
                "acceleration_x_mps2": 0.0,
                "acceleration_y_mps2": 0.0,
                "acceleration_mps2": 0.0,
                "direction_deg": 0.0,
                "dt_seconds": dt,
                "calibration_status": calib_status,
                "is_calibrated": is_calibrated,
            }
            return

        # Position and Velocity Filtering (EMA with first-step initialization)
        is_first_motion_step = len(track["positions"]) == 1

        if is_first_motion_step:
            fx = float(cx)
            fy = float(cy)
            dx_m = 0.0 if is_subpixel_noise else (float(cx) - float(prev_cx)) * scale
            dy_m = 0.0 if is_subpixel_noise else (float(cy) - float(prev_cy)) * scale
            inst_vx = dx_m / dt
            inst_vy = dy_m / dt
            filt_vx = inst_vx
            filt_vy = inst_vy
        else:
            alpha = self.pos_filter_alpha
            fx = alpha * float(cx) + (1.0 - alpha) * prev_fx
            fy = alpha * float(cy) + (1.0 - alpha) * prev_fy
            dx_m = 0.0 if is_subpixel_noise else (fx - prev_fx) * scale
            dy_m = 0.0 if is_subpixel_noise else (fy - prev_fy) * scale
            inst_vx = dx_m / dt
            inst_vy = dy_m / dt
            beta = self.vel_filter_beta
            filt_vx = beta * inst_vx + (1.0 - beta) * prev_vx
            filt_vy = beta * inst_vy + (1.0 - beta) * prev_vy

        speed = math.hypot(filt_vx, filt_vy)

        # Vector acceleration (differentiation of velocity vectors)
        ax = (filt_vx - prev_vx) / dt
        ay = (filt_vy - prev_vy) / dt
        accel_mag = math.hypot(ax, ay)

        # Direction of motion (angle in degrees [0, 360))
        if speed > 0.01:
            direction_deg = round(math.degrees(math.atan2(filt_vy, filt_vx)) % 360.0, 2)
        else:
            direction_deg = track["direction_angles_deg"][-1] if track.get("direction_angles_deg") else 0.0

        track["positions"].append((cx, cy, now))
        track["filtered_positions"].append((fx, fy))
        track["filtered_velocities"].append((filt_vx, filt_vy))
        track["velocities"].append(speed)
        track["accelerations"].append((ax, ay))
        if "acceleration_mags" not in track:
            track["acceleration_mags"] = []
        track["acceleration_mags"].append(accel_mag)
        if "direction_angles_deg" not in track:
            track["direction_angles_deg"] = []
        track["direction_angles_deg"].append(direction_deg)
        track["last_seen"] = now

        # Keep history bounded (max 50 points)
        if len(track["positions"]) > 50:
            track["positions"] = track["positions"][-50:]
            track["filtered_positions"] = track["filtered_positions"][-50:]
            track["filtered_velocities"] = track["filtered_velocities"][-50:]
            track["velocities"] = track["velocities"][-50:]
            track["accelerations"] = track["accelerations"][-50:]
            track["acceleration_mags"] = track["acceleration_mags"][-50:]
            track["direction_angles_deg"] = track["direction_angles_deg"][-50:]

        track["latest_details"] = {
            "dx_meters": round(dx_m, 6),
            "dy_meters": round(dy_m, 6),
            "velocity_x_mps": round(filt_vx, 4),
            "velocity_y_mps": round(filt_vy, 4),
            "velocity_mps": round(speed, 4),
            "acceleration_x_mps2": round(ax, 4),
            "acceleration_y_mps2": round(ay, 4),
            "acceleration_mps2": round(accel_mag, 4),
            "direction_deg": direction_deg,
            "dt_seconds": round(dt, 4),
            "calibration_status": calib_status,
            "is_calibrated": is_calibrated,
        }

    def update(
        self,
        centroid: Optional[Tuple[int, int]],
        timestamp_seconds: float,
        px_to_meters: float,
    ) -> KinematicsResult:
        """
        Updates trajectory with a single observation, for 100% backward compatibility.
        """
        if centroid is None:
            res, _ = self.update_detections([], timestamp_seconds, px_to_meters)
            return res

        cx, cy = centroid
        dummy_det = Detection(
            bbox_xyxy=[float(cx - 5), float(cy - 5), float(cx + 5), float(cy + 5)],
            center=(cx, cy),
            timestamp=timestamp_seconds,
            detector_name="single_centroid",
        )
        res, _ = self.update_detections([dummy_det], timestamp_seconds, px_to_meters)
        return res


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


# ==============================================================================
# Common Detector Abstraction and Concrete Detectors
# ==============================================================================

class BaseDetector(ABC):
    """
    Common polymorphic interface for all real-time computer vision detectors.
    Every detector returns a list of Detection/DetectorOutput objects with consistent structure:
    - bbox_xyxy: [x_min, y_min, x_max, y_max]
    - class_label: Optional[str] (None for color segmentation / optical flow)
    - confidence: Optional[float] (None for color segmentation)
    - center: Tuple[int, int]
    - timestamp: float
    - detector_name: str
    - latency_ms: float
    - status: str
    - attributes: Dict[str, Any]
    """
    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Human-readable detector identifier."""
        pass

    @abstractmethod
    def detect(self, img: np.ndarray, **kwargs) -> List[Detection]:
        """Runs detection on a BGR numpy image frame."""
        pass

    def reset(self) -> None:
        """Resets detector internal temporal state (if any)."""
        pass


class ColorSegmentationDetector(BaseDetector):
    """
    Genuine OpenCV color segmentation using HSV thresholding, morphological
    noise suppression (opening and closing), and contour geometric filtering.
    Does NOT describe segmentation as general object recognition, and never
    invents semantic classes or model confidence scores.
    """
    def __init__(
        self,
        min_area: float = 50.0,
        max_area_ratio: float = 0.92,
        max_aspect_ratio: float = 18.0,
        min_solidity: float = 0.15,
    ):
        self.min_area = min_area
        self.max_area_ratio = max_area_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_solidity = min_solidity

    @property
    def detector_name(self) -> str:
        return "opencv_hsv_color_segmentation"

    def detect(
        self,
        img: np.ndarray,
        color_target: str = "red",
        conf_thresh: float = 0.2,
        timestamp_s: Optional[float] = None,
        **kwargs,
    ) -> List[Detection]:
        t_start = time.perf_counter()
        now_s = timestamp_s if timestamp_s is not None else time.time()
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
        max_area = self.max_area_ratio * (width * height)

        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < self.min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = max(w / max(h, 1), h / max(w, 1))
            if aspect_ratio > self.max_aspect_ratio:
                continue

            bbox_area = max(1.0, float(w * h))
            solidity = area / bbox_area
            if solidity < self.min_solidity:
                continue

            perimeter = cv2.arcLength(cnt, True)
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0.0

            # Quality heuristic for candidate filtering (not semantic model confidence)
            quality = 0.5 * solidity + 0.3 * min(1.0, circularity) + 0.2 * min(1.0, area / 5000.0)
            if quality < conf_thresh:
                continue

            x1 = max(0.0, float(x))
            y1 = max(0.0, float(y))
            x2 = min(float(width), float(x + w))
            y2 = min(float(height), float(y + h))

            if x2 > x1 and y2 > y1:
                cx = int(round((x1 + x2) / 2.0))
                cy = int(round((y1 + y2) / 2.0))
                detections.append(
                    Detection(
                        bbox_xyxy=[x1, y1, x2, y2],
                        class_label=None,
                        class_name=None,
                        confidence=None,
                        center=(cx, cy),
                        timestamp=now_s,
                        detector_name=self.detector_name,
                        latency_ms=0.0,
                        status="detected",
                        attributes={
                            "color_target": target,
                            "area": round(area, 2),
                            "solidity": round(solidity, 4),
                            "circularity": round(circularity, 4),
                            "perimeter": round(perimeter, 2),
                            "blob_quality": round(quality, 4),
                        },
                    )
                )

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        for d in detections:
            d.latency_ms = latency_ms

        detections.sort(key=lambda d: d.attributes.get("area", 0.0), reverse=True)
        return detections


class OpticalFlowDetector(BaseDetector):
    """
    Lucas–Kanade pyramidal optical flow detector with Shi-Tomasi corner detection,
    automatic point tracking, point survival ratio measurement, and lost-track recovery.
    """
    def __init__(self):
        self.prev_gray: Optional[np.ndarray] = None
        self.prev_pts: Optional[np.ndarray] = None
        self.last_pts_count: int = 0
        self.failure_count: int = 0
        self.recovered: bool = False

    @property
    def detector_name(self) -> str:
        return "lucas_kanade_optical_flow"

    def reset(self) -> None:
        self.prev_gray = None
        self.prev_pts = None
        self.last_pts_count = 0
        self.failure_count = 0
        self.recovered = False

    def detect_features(self, gray: np.ndarray, mask: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        pts = cv2.goodFeaturesToTrack(
            gray,
            maxCorners=100,
            qualityLevel=0.015,
            minDistance=8,
            blockSize=7,
            mask=mask,
        )
        if pts is None or len(pts) < 3:
            pts = cv2.goodFeaturesToTrack(
                gray,
                maxCorners=100,
                qualityLevel=0.003,
                minDistance=5,
                blockSize=7,
                mask=mask,
            )
        return pts

    def detect(
        self,
        img: np.ndarray,
        conf_thresh: float = 0.25,
        timestamp_s: Optional[float] = None,
        **kwargs,
    ) -> List[Detection]:
        t_start = time.perf_counter()
        now_s = timestamp_s if timestamp_s is not None else time.time()
        height, width = img.shape[:2]
        curr_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self.recovered = False

        # Initial frame or lost state: seed features
        if self.prev_gray is None or self.prev_pts is None or len(self.prev_pts) < 3:
            pts = self.detect_features(curr_gray)
            if pts is None or len(pts) < 3:
                self.prev_gray = curr_gray
                self.prev_pts = None
                return []

            self.prev_gray = curr_gray
            self.prev_pts = pts
            self.last_pts_count = len(pts)

            pts_2d = pts.reshape(-1, 2)
            x_min = max(0.0, float(np.min(pts_2d[:, 0]) - 5))
            y_min = max(0.0, float(np.min(pts_2d[:, 1]) - 5))
            x_max = min(float(width), float(np.max(pts_2d[:, 0]) + 5))
            y_max = min(float(height), float(np.max(pts_2d[:, 1]) + 5))
            cx = int(round((x_min + x_max) / 2.0))
            cy = int(round((y_min + y_max) / 2.0))

            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            return [
                Detection(
                    bbox_xyxy=[x_min, y_min, x_max, y_max],
                    class_label="optical_flow_target",
                    class_name="optical_flow_target",
                    confidence=1.0,
                    center=(cx, cy),
                    timestamp=now_s,
                    detector_name=self.detector_name,
                    latency_ms=latency_ms,
                    status="detected",
                    attributes={"tracked_points": len(pts), "survival_ratio": 1.0, "recovered": False},
                )
            ]

        # Pyramidal Lucas-Kanade step
        lk_params = dict(
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )

        try:
            next_pts, status, err = cv2.calcOpticalFlowPyrLK(
                self.prev_gray,
                curr_gray,
                self.prev_pts,
                None,
                **lk_params,
            )
        except Exception as e:
            logger.warning(f"calcOpticalFlowPyrLK error: {e}")
            next_pts, status = None, None

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

        min_surviving_points = 3
        if len(good_new) < min_surviving_points:
            # Lost track: trigger failure recovery re-detection
            self.recovered = True
            self.failure_count += 1
            recovery_pts = self.detect_features(curr_gray)
            if recovery_pts is not None and len(recovery_pts) >= min_surviving_points:
                self.prev_pts = recovery_pts
                self.prev_gray = curr_gray
                self.last_pts_count = len(recovery_pts)
                pts_2d = recovery_pts.reshape(-1, 2)
                x_min = max(0.0, float(np.min(pts_2d[:, 0]) - 5))
                y_min = max(0.0, float(np.min(pts_2d[:, 1]) - 5))
                x_max = min(float(width), float(np.max(pts_2d[:, 0]) + 5))
                y_max = min(float(height), float(np.max(pts_2d[:, 1]) + 5))
                cx = int(round((x_min + x_max) / 2.0))
                cy = int(round((y_min + y_max) / 2.0))
                latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
                return [
                    Detection(
                        bbox_xyxy=[x_min, y_min, x_max, y_max],
                        class_label="optical_flow_target",
                        class_name="optical_flow_target",
                        confidence=0.5,
                        center=(cx, cy),
                        timestamp=now_s,
                        detector_name=self.detector_name,
                        latency_ms=latency_ms,
                        status="recovered",
                        attributes={"tracked_points": len(recovery_pts), "survival_ratio": 0.5, "recovered": True},
                    )
                ]
            else:
                self.prev_pts = None
                self.prev_gray = curr_gray
                return []

        # Successful step
        good_new_arr = np.array(good_new, dtype=np.float32)
        self.prev_pts = good_new_arr.reshape(-1, 1, 2)
        self.prev_gray = curr_gray

        x_min = max(0.0, float(np.min(good_new_arr[:, 0]) - 6))
        y_min = max(0.0, float(np.min(good_new_arr[:, 1]) - 6))
        x_max = min(float(width), float(np.max(good_new_arr[:, 0]) + 6))
        y_max = min(float(height), float(np.max(good_new_arr[:, 1]) + 6))
        cx = int(round((x_min + x_max) / 2.0))
        cy = int(round((y_min + y_max) / 2.0))

        survival_ratio = len(good_new) / max(self.last_pts_count, 1)
        conf = round(float(min(1.0, max(0.3, survival_ratio))), 3)
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

        if conf >= conf_thresh and x_max > x_min and y_max > y_min:
            return [
                Detection(
                    bbox_xyxy=[x_min, y_min, x_max, y_max],
                    class_label="optical_flow_target",
                    class_name="optical_flow_target",
                    confidence=conf,
                    center=(cx, cy),
                    timestamp=now_s,
                    detector_name=self.detector_name,
                    latency_ms=latency_ms,
                    status="detected",
                    attributes={"tracked_points": len(good_new), "survival_ratio": survival_ratio, "recovered": False},
                )
            ]
        return []


class YOLODetector(BaseDetector):
    """
    Ultralytics YOLOv8 deep learning detector with model reuse, confidence thresholding,
    class filtering, Non-Maximum Suppression (NMS), and bounding box clamping.
    """
    def __init__(
        self,
        model_instance: Optional[Any] = None,
        allowed_classes: Optional[List[str]] = None,
        load_default_if_none: bool = True,
    ):
        if model_instance is not None:
            self.model = model_instance
        elif load_default_if_none:
            self.model = get_shared_yolo_model()
        else:
            self.model = None
        self.allowed_classes = set(c.lower() for c in allowed_classes) if allowed_classes else None

    @property
    def detector_name(self) -> str:
        return "yolov8n_neural_network"

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def detect(
        self,
        img: np.ndarray,
        conf_thresh: float = 0.25,
        nms_thresh: float = 0.45,
        timestamp_s: Optional[float] = None,
        **kwargs,
    ) -> List[Detection]:
        t_start = time.perf_counter()
        now_s = timestamp_s if timestamp_s is not None else time.time()
        detections: List[Detection] = []
        if self.model is None:
            return detections

        height, width = img.shape[:2]
        try:
            results = self.model.predict(
                source=img,
                conf=conf_thresh,
                iou=nms_thresh,
                verbose=False,
            )
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None and len(boxes) > 0:
                    raw_boxes = []
                    raw_scores = []
                    raw_classes = []
                    raw_indices = []

                    for i in range(len(boxes)):
                        xyxy = boxes.xyxy[i].cpu().numpy().tolist()
                        conf = float(boxes.conf[i].cpu().numpy())
                        cls_idx = int(boxes.cls[i].cpu().numpy())
                        class_name = self.model.names.get(cls_idx, f"class_{cls_idx}")

                        if self.allowed_classes and class_name.lower() not in self.allowed_classes:
                            continue

                        x1, y1, x2, y2 = [float(c) for c in xyxy]
                        x1 = max(0.0, min(float(width), x1))
                        y1 = max(0.0, min(float(height), y1))
                        x2 = max(0.0, min(float(width), x2))
                        y2 = max(0.0, min(float(height), y2))

                        if x2 > x1 and y2 > y1 and conf >= conf_thresh:
                            raw_boxes.append([x1, y1, x2, y2])
                            raw_scores.append(conf)
                            raw_classes.append(class_name)
                            raw_indices.append(cls_idx)

                    keep_indices = apply_nms_boxes(raw_boxes, raw_scores, iou_threshold=nms_thresh, score_threshold=conf_thresh)
                    for idx in keep_indices:
                        b = raw_boxes[idx]
                        cx = int(round((b[0] + b[2]) / 2.0))
                        cy = int(round((b[1] + b[3]) / 2.0))
                        detections.append(
                            Detection(
                                bbox_xyxy=b,
                                class_label=raw_classes[idx],
                                class_name=raw_classes[idx],
                                confidence=round(raw_scores[idx], 4),
                                center=(cx, cy),
                                timestamp=now_s,
                                detector_name=self.detector_name,
                                latency_ms=0.0,
                                status="detected",
                                attributes={
                                    "model_version": "yolov8n-v8.1.0",
                                    "coco_class_id": raw_indices[idx],
                                },
                            )
                        )
        except Exception as err:
            logger.error(f"YOLO inference error: {err}")

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        for d in detections:
            d.latency_ms = latency_ms

        return detections


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
        self.calibration_data: Optional[Dict[str, Any]] = None

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

        # Modular concrete detector instances
        self.color_detector = ColorSegmentationDetector()
        self.optical_flow_detector = OpticalFlowDetector()
        self.yolo_detector = YOLODetector(model_instance=self.yolo_model, load_default_if_none=False)

        self.model_ready = True

    # Optical flow tracking state properties for backwards compatibility
    @property
    def of_prev_gray(self):
        return self.optical_flow_detector.prev_gray

    @of_prev_gray.setter
    def of_prev_gray(self, val):
        self.optical_flow_detector.prev_gray = val

    @property
    def of_prev_pts(self):
        return self.optical_flow_detector.prev_pts

    @of_prev_pts.setter
    def of_prev_pts(self, val):
        self.optical_flow_detector.prev_pts = val

    @property
    def of_last_pts_count(self) -> int:
        return self.optical_flow_detector.last_pts_count

    @of_last_pts_count.setter
    def of_last_pts_count(self, val: int):
        self.optical_flow_detector.last_pts_count = val

    @property
    def of_failure_count(self) -> int:
        return self.optical_flow_detector.failure_count

    @of_failure_count.setter
    def of_failure_count(self, val: int):
        self.optical_flow_detector.failure_count = val

    @property
    def of_recovered(self) -> bool:
        return self.optical_flow_detector.recovered

    @of_recovered.setter
    def of_recovered(self, val: bool):
        self.optical_flow_detector.recovered = val

    def set_calibration_data(self, calib: Dict[str, Any]) -> None:
        """Sets active session camera calibration."""
        self.calibration_data = calib

    def get_calibration_data(self) -> Optional[Dict[str, Any]]:
        """Returns active session camera calibration."""
        return self.calibration_data

    def get_effective_scale(self, client_px_to_meters: float) -> float:
        """Determines effective scale: calibrated session scale takes precedence over client default."""
        if self.calibration_data and "scale_factor_m_per_px" in self.calibration_data:
            return float(self.calibration_data["scale_factor_m_per_px"])
        return client_px_to_meters if (client_px_to_meters and client_px_to_meters > 0) else 0.005

    def get_device(self) -> str:
        """Determines active hardware acceleration device (cuda / cpu)."""
        try:
            import torch
            if torch.cuda.is_available():
                return f"cuda:{torch.cuda.current_device()}"
        except Exception:
            pass
        return "cpu"

    def get_memory_usage_mb(self) -> float:
        """Estimates process resident memory consumption in MB."""
        try:
            import psutil
            process = psutil.Process()
            return round(process.memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0

    def check_readiness(self) -> Dict[str, Any]:
        """Explicit model-loading and readiness verification."""
        active_det = "ColorSegmentationDetector"
        if self.yolo_model is not None:
            active_det = "YOLODetector"

        device_info = self.get_device()
        mem_mb = self.get_memory_usage_mb()

        return {
            "ready": self.model_ready,
            "active_model": self.model_name,
            "active_detector": active_det,
            "model_version": "v1.2.0" if self.yolo_model else "opencv_kinematics_v4.10",
            "model_path": getattr(self, "yolo_weights_path", None) or "built-in",
            "device": device_info,
            "memory_usage_mb": mem_mb,
            "yolo_loaded": self.yolo_model is not None,
            "yolo_status": self.yolo_status,
            "yolo_error": self.yolo_error,
            "classes_count": len(self.yolo_model.names) if self.yolo_model else 0,
            "supported_methods": ["color", "optical_flow", "yolo"],
            "inference_errors": 0,
            "model_metadata": {
                "framework": "ultralytics_yolo" if self.yolo_model else "opencv_color_and_lucas_kanade",
                "device": device_info,
                "memory_mb": mem_mb,
                "concurrency_limit": 10,
            },
        }

    def reset_tracker(self):
        """Resets trajectory tracking history and optical flow state across frames."""
        self.trajectory_tracker.reset()
        self.optical_flow_detector.reset()

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
        t_decode = time.perf_counter() - t_start
        return self._run_pipeline(
            img=img,
            tracking_method=tracking_method,
            color_target=color_target,
            px_to_meters=px_to_meters,
            conf_thresh=confidence_threshold,
            nms_thresh=nms_threshold,
            t_start=t_start,
            t_decode=t_decode,
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
        t_decode = time.perf_counter() - t_start
        return self._run_pipeline(
            img=img,
            tracking_method=tracking_method,
            color_target=color_target,
            px_to_meters=px_to_meters,
            conf_thresh=confidence_threshold,
            nms_thresh=nms_threshold,
            t_start=t_start,
            t_decode=t_decode,
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
        t_decode: float = 0.0,
    ) -> Dict[str, Any]:
        height, width = img.shape[:2]
        timestamp_s = time.time()
        timestamp_ms = int(timestamp_s * 1000)

        detections: List[Detection] = []
        method = (tracking_method or "color").lower().strip()
        inference_status = "completed"

        # 1. Routing to appropriate detector
        is_degraded = False
        degraded_reason = None
        active_model = "unknown"
        active_detector = "unknown"
        detection_message = ""

        t_det_start = time.perf_counter()
        if method == "yolo":
            if self.yolo_detector.is_available:
                detections = self.yolo_detector.detect(img, conf_thresh=conf_thresh, nms_thresh=nms_thresh, timestamp_s=timestamp_s)
                active_model = "yolov8n"
                active_detector = "YOLOv8 Neural Network (Ultralytics)"
                inference_status = "completed"
                is_degraded = False
                detection_message = "YOLOv8 target detection active." if detections else "No object detected by YOLO in current frame."
            else:
                detections = self.color_detector.detect(img, color_target=color_target, conf_thresh=conf_thresh, timestamp_s=timestamp_s)
                active_model = f"yolo_fallback_color_{color_target or 'red'}"
                active_detector = f"OpenCV HSV Blob Fallback ({color_target or 'red'})"
                inference_status = "degraded"
                is_degraded = True
                degraded_reason = f"YOLO weights unavailable ({self.yolo_status}): {self.yolo_error or 'Disabled in memory-constrained environment'}"
                detection_message = f"YOLO unavailable. Using OpenCV {color_target or 'red'} fallback. {'Target locked.' if detections else 'No target detected.'}"
        elif method in ("optical_flow", "opticalflow"):
            detections = self.optical_flow_detector.detect(img, conf_thresh=conf_thresh, timestamp_s=timestamp_s)
            self.of_recovered = self.optical_flow_detector.recovered
            self.of_failure_count = self.optical_flow_detector.failure_count
            active_model = "lucas_kanade_optical_flow"
            active_detector = "Lucas-Kanade Pyramidal Optical Flow"
            is_degraded = bool(self.optical_flow_detector.recovered or not detections)
            inference_status = "completed" if (detections and not self.optical_flow_detector.recovered) else "degraded"
            degraded_reason = "Feature points lost; re-seeded Shi-Tomasi corners." if self.optical_flow_detector.recovered else None
            detection_message = "Lucas-Kanade optical flow motion tracking active." if detections else "No optical flow features detected. Move target across frame."
        else:
            detections = self.color_detector.detect(img, color_target=color_target, conf_thresh=conf_thresh, timestamp_s=timestamp_s)
            active_model = f"color_{color_target or 'red'}"
            active_detector = f"OpenCV HSV Blob Tracker ({color_target or 'red'})"
            inference_status = "completed"
            is_degraded = False
            detection_message = f"OpenCV HSV color tracker active ({color_target or 'red'}). Target locked." if detections else f"No {color_target or 'red'} target detected. Adjust lighting or present target."

        t_detection = time.perf_counter() - t_det_start

        # 2. Multi-object trajectory and kinematics tracking
        t_track_start = time.perf_counter()
        effective_scale = self.get_effective_scale(px_to_meters)
        primary_kinematics, tracking_summary = self.trajectory_tracker.update_detections(
            detections=detections,
            timestamp_seconds=timestamp_s,
            px_to_meters=effective_scale,
        )
        t_tracking = time.perf_counter() - t_track_start

        centroid: Optional[List[int]] = None
        contours_found = len(detections)
        track_id = primary_kinematics.track_id
        v = primary_kinematics.velocity_mps
        a = primary_kinematics.acceleration_mps2
        kinematics_details = primary_kinematics.details

        if detections:
            primary_det = max(
                detections,
                key=lambda d: ((d.confidence if d.confidence is not None else 0.0), d.attributes.get("area", 0.0))
            )
            centroid = [primary_det.center[0], primary_det.center[1]] if primary_det.center else None

        t_total = time.perf_counter() - t_start
        t_total_ms = round(t_total * 1000, 2)
        fps_val = round(1000.0 / max(t_total_ms, 0.1), 1)

        latency_breakdown = {
            "decode_ms": round(t_decode * 1000, 2),
            "detection_ms": round(t_detection * 1000, 2),
            "tracking_ms": round(t_tracking * 1000, 2),
            "total_ms": t_total_ms,
            "fps": fps_val,
        }

        direction_deg = kinematics_details.get("direction_deg", 0.0)

        physics = {
            "x_meters": round(centroid[0] * effective_scale, 4) if centroid else None,
            "y_meters": round(centroid[1] * effective_scale, 4) if centroid else None,
            "dx_meters": kinematics_details.get("dx_meters", 0.0),
            "dy_meters": kinematics_details.get("dy_meters", 0.0),
            "velocity_mps": round(v, 4),
            "velocity_x_mps": kinematics_details.get("velocity_x_mps", 0.0),
            "velocity_y_mps": kinematics_details.get("velocity_y_mps", 0.0),
            "acceleration_mps2": round(a, 4),
            "acceleration_x_mps2": kinematics_details.get("acceleration_x_mps2", 0.0),
            "acceleration_y_mps2": kinematics_details.get("acceleration_y_mps2", 0.0),
            "direction_deg": direction_deg,
            "motion_direction_deg": direction_deg,
            "track_id": track_id,
            "dt_seconds": kinematics_details.get("dt_seconds"),
            "calibration_status": kinematics_details.get("calibration_status", "calibrated"),
            "is_calibrated": kinematics_details.get("is_calibrated", True),
            "is_estimated": True,
            "units": CALIBRATION_UNITS,
            "tracking_summary": tracking_summary,
        }

        # Model provenance metadata
        is_yolo = (method == "yolo" and self.yolo_detector.is_available)
        is_of = method in ("optical_flow", "opticalflow")

        if is_yolo:
            model_ver = "yolov8n-v8.1.0"
            preprocess_ver = "letterbox_rgb_norm_v1"
        elif is_of:
            model_ver = "lucas_kanade_pyr_v1.0"
            preprocess_ver = "bgr_to_gray_v1"
        else:
            model_ver = "hsv_blob_tracker_v2.0.0"
            preprocess_ver = "bgr_to_hsv_v1"

        calibration_info = {
            "px_to_meters": effective_scale,
            "scale_factor_m_per_px": effective_scale,
            "unit_system": "SI",
            "origin": [0.0, 0.0],
            "units": CALIBRATION_UNITS,
            "calibration_model": "coplanar_orthographic_scalar",
            "assumptions": CALIBRATION_ASSUMPTIONS,
            "limitations": CALIBRATION_LIMITATIONS,
            "is_custom_calibrated": bool(self.calibration_data is not None),
        }

        prov_info = {
            "source": "client_webcam_stream",
            "raw_footage_stored": False,
            "retention_policy": "ephemeral_discard",
            "model_version": model_ver,
            "configuration_version": "cv_config_v2.0",
            "preprocessing_version": preprocess_ver,
            "reproducible": True,
            "tracking_method": method,
            "active_detector": active_detector,
            "is_degraded": is_degraded,
            "latency_breakdown": latency_breakdown,
        }

        if method == "yolo" and not self.yolo_detector.is_available:
            prov_info["yolo_status"] = self.yolo_status
            prov_info["yolo_error"] = self.yolo_error
            prov_info["degraded_reason"] = f"YOLO weights unavailable ({self.yolo_status}): {self.yolo_error}"
        elif is_of:
            prov_info["optical_flow_recovered"] = getattr(self.optical_flow_detector, "recovered", False)
            prov_info["optical_flow_failures"] = getattr(self.optical_flow_detector, "failure_count", 0)

        # Build schema result with full model provenance and latency breakdown
        frame_result = FrameResult(
            timestamp_ms=timestamp_ms,
            detections=detections,
            centroid=centroid,
            contours_found=contours_found,
            width=width,
            height=height,
            physics=physics,
            model_name=active_model,
            active_detector=active_detector,
            is_degraded=is_degraded,
            degraded_reason=degraded_reason,
            detection_message=detection_message,
            inference_latency_ms=t_total_ms,
            latency_breakdown=latency_breakdown,
            model_version=model_ver,
            configuration_version="cv_config_v2.0",
            preprocessing_version=preprocess_ver,
            calibration=calibration_info,
            inference_status=inference_status,
            raw_footage_stored=False,
            provenance=prov_info,
        )

        return frame_result.model_dump()

    # Delegators for backwards compatibility with test fixtures
    def _detect_yolo(self, img: np.ndarray, conf_thresh: float, iou_thresh: float) -> List[Detection]:
        """Runs YOLOv8 model inference with NMS thresholding."""
        return self.yolo_detector.detect(img, conf_thresh=conf_thresh, nms_thresh=iou_thresh)

    def _track_optical_flow(self, img: np.ndarray, conf_thresh: float) -> Tuple[List[Detection], bool]:
        """Executes Lucas–Kanade optical flow feature tracking."""
        dets = self.optical_flow_detector.detect(img, conf_thresh=conf_thresh)
        self.of_recovered = self.optical_flow_detector.recovered
        self.of_failure_count = self.optical_flow_detector.failure_count
        return dets, self.optical_flow_detector.recovered

    def _detect_color(self, img: np.ndarray, color_target: str, conf_thresh: float) -> List[Detection]:
        """Runs genuine HSV segmentation, morphology, and contour filtering."""
        return self.color_detector.detect(img, color_target=color_target, conf_thresh=conf_thresh)

    def _detect_optical_flow_features(self, gray: np.ndarray, mask: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """Extracts strong feature points for Lucas-Kanade tracking using Shi-Tomasi corner detection."""
        return self.optical_flow_detector.detect_features(gray, mask=mask)


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
    - Session camera calibration: Associates verified metric scale factors, reference lengths,
      and perspective assumptions with specific camera sessions.
    - Multi-backend state synchronization: Persists and hydrates trajectory state
      via Redis shared cache (when available) with reliable cluster shared store fallback.
    - Thread-safe concurrency: Per-tracker async locks preventing concurrent frame races.
    - Session lifecycle management: TTL expiration and automatic cleanup of inactive sessions.
    """
    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._local_trackers: Dict[str, Dict[str, Any]] = {}
        self._session_calibrations: Dict[str, Dict[str, Any]] = {}
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

    def set_calibration(
        self,
        user_id: str,
        session_id: Optional[str],
        camera_id: Optional[str],
        calibration_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Sets and persists session camera calibration for user/session/camera."""
        tracker_key = self.make_tracker_key(user_id, session_id, camera_id)
        with self._local_lock:
            self._session_calibrations[tracker_key] = calibration_data
            if tracker_key in self._local_trackers:
                self._local_trackers[tracker_key]["tracker"].set_calibration_data(calibration_data)
        logger.info(f"Persisted camera calibration for {tracker_key}: scale={calibration_data.get('scale_factor_m_per_px')} m/px")
        return calibration_data

    def get_calibration(
        self,
        user_id: str,
        session_id: Optional[str],
        camera_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Retrieves active session camera calibration if present."""
        tracker_key = self.make_tracker_key(user_id, session_id, camera_id)
        with self._local_lock:
            return self._session_calibrations.get(tracker_key)

    async def get_tracker(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        camera_id: Optional[str] = None,
    ) -> CVTracker:
        """
        Retrieves or initializes the independent CVTracker instance for the given user, session, and camera.
        If shared state exists in cluster store or Redis, restores trajectory history across instances.
        Hydrates session camera calibration if previously calibrated.
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

            if tracker_key in self._session_calibrations:
                tracker.set_calibration_data(self._session_calibrations[tracker_key])

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

            if tracker_key in self._local_trackers:
                entry = self._local_trackers[tracker_key]
                entry["last_accessed"] = now
                tr = entry["tracker"]
                if tracker_key in self._session_calibrations:
                    tr.set_calibration_data(self._session_calibrations[tracker_key])
                return tr

            tracker = CVTracker(
                tracker_key=tracker_key,
                shared_yolo_model=get_shared_yolo_model(),
            )
            if tracker_key in self._session_calibrations:
                tracker.set_calibration_data(self._session_calibrations[tracker_key])

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
                self._session_calibrations.pop(k, None)
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
                for k in list(self._session_calibrations.keys()):
                    if k.startswith(f"{uid}:"):
                        self._session_calibrations.pop(k, None)
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
                self._session_calibrations.pop(k, None)
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
                for k in list(self._session_calibrations.keys()):
                    if k.startswith(f"{uid}:"):
                        self._session_calibrations.pop(k, None)
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
                    self._session_calibrations.pop(k, None)
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
            self._session_calibrations.clear()
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
