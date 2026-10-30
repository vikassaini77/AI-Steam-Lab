import time
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional, Dict, Any, List
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import limiter
from app.machine_learning.cv_service import (
    CVTracker,
    Detection,
    FrameResult,
    InvalidImageError,
    PayloadTooLargeError,
    DimensionLimitExceededError,
)
from app.logger import logger

router = APIRouter()
cv_tracker = CVTracker()
_cv_concurrency_semaphore = asyncio.Semaphore(10)

MAX_FRAME_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MiB


def check_frame_payload_limit(request: Request):
    """Early content-length inspection before request body parsing."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FRAME_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large: Video frame payload exceeds 5MB limit.",
        )


class TrackingMethod(str, Enum):
    COLOR = "color"
    OPTICAL_FLOW = "optical_flow"
    YOLO = "yolo"


class FrameProcessRequest(BaseModel):
    image: Optional[str] = Field(
        None,
        max_length=7_000_000,
        description="Base64 encoded video frame",
    )
    frame: Optional[str] = Field(
        None,
        max_length=7_000_000,
        description="Alternative key for base64 encoded frame",
    )
    tracking_method: Optional[TrackingMethod] = Field(
        default=TrackingMethod.COLOR,
        description="Tracking algorithm (color, optical_flow, yolo)",
    )
    color_target: Optional[str] = Field(
        default="red",
        max_length=50,
        description="Color target for HSV tracking (red, green, blue)",
    )
    px_to_meters: Optional[float] = Field(
        default=0.005,
        gt=0.0,
        le=10.0,
        description="Pixel to meters conversion scale factor",
    )
    confidence_threshold: Optional[float] = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score threshold",
    )
    nms_threshold: Optional[float] = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Non-maximum suppression threshold",
    )

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="after")
    def validate_image_present(self):
        img = self.image or self.frame
        if not img or not img.strip():
            raise ValueError("Missing image data: payload must include 'image' or 'frame' string.")
        return self


class EngagementEvent(BaseModel):
    user_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional client-provided user ID (verified against authenticated identity)",
    )
    state: Literal[
        "focused",
        "confused",
        "leaning_forward",
        "disengaged",
    ]
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated confidence score bounded between 0.0 and 1.0",
    )
    session_id: Optional[str] = Field(None, max_length=100)
    model_version: Optional[str] = Field(default="v1.0.0-cv-heuristics", max_length=50)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
    }


# Response Models
class CVStatusResponse(BaseModel):
    status: str = Field(..., description="Service status message")


class CVReadinessResponse(BaseModel):
    ready: bool = Field(..., description="Whether CV model inference is ready")
    active_model: str = Field(..., description="Name of the active detection model")
    yolo_loaded: bool = Field(..., description="Whether YOLOv8 weights are loaded")
    classes_count: int = Field(..., ge=0, description="Detectable classes count")
    supported_methods: List[str] = Field(..., description="List of supported tracking methods")


class ResetTrackerResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    message: str = Field(..., description="Status description")


class PhysicsTrackingMetrics(BaseModel):
    x_meters: Optional[float] = Field(None, description="Displacement along x axis in meters")
    y_meters: Optional[float] = Field(None, description="Displacement along y axis in meters")
    velocity_mps: Optional[float] = Field(0.0, description="Estimated velocity in m/s")
    acceleration_mps2: Optional[float] = Field(0.0, description="Estimated acceleration in m/s^2")
    track_id: Optional[int] = Field(None, description="Persistent tracking ID")


class FrameProcessResponse(BaseModel):
    timestamp_ms: int = Field(..., description="Timestamp of the frame in milliseconds")
    detections: List[Detection] = Field(default_factory=list, description="List of validated detections")
    centroid: Optional[List[int]] = Field(None, description="Centroid [x, y] of primary object or None")
    contours_found: int = Field(0, description="Number of contours / candidates found")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    physics: Optional[PhysicsTrackingMetrics] = Field(None, description="Extracted kinematics and trajectory physics")
    model_name: str = Field(..., description="Inference model or detector used")
    inference_latency_ms: float = Field(..., description="Inference execution duration in milliseconds")
    user_id: Optional[str] = Field(None, description="Authenticated user ID who submitted the frame")

    model_config = {"extra": "allow"}


class EngagementRecord(BaseModel):
    user_id: str = Field(..., description="User ID")
    state: str = Field(..., description="Engagement classification state")
    confidence: float = Field(..., description="Confidence score")
    timestamp: float = Field(..., description="Epoch timestamp in seconds")
    recorded_at: str = Field(..., description="ISO 8601 recorded timestamp")
    model_version: str = Field(..., description="Model version")
    session_id: Optional[str] = Field(None, description="Session ID")
    is_estimate: bool = Field(True, description="Indicates this is an estimated heuristic")
    disclaimer: str = Field(..., description="Heuristic disclaimer")


class EngagementResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    event: EngagementRecord = Field(..., description="Recorded engagement event")


@router.get("/", response_model=CVStatusResponse)
def get_cv_tracker_status():
    return {"status": "CV Tracker endpoint is active."}


@router.get("/readiness", response_model=CVReadinessResponse)
def check_cv_readiness():
    """
    Explicit model-loading and readiness verification endpoint.
    Reports active detection model, weights loaded, and supported inference modes.
    """
    return cv_tracker.check_readiness()


@router.post("/reset-tracker", response_model=ResetTrackerResponse)
def reset_cv_tracker(current_user: dict = Depends(get_current_user)):
    """
    Resets object trajectory tracking history and clears persistent IDs.
    """
    cv_tracker.reset_tracker()
    return {"status": "success", "message": "Object trajectory tracker reset."}


@router.post(
    "/process-frame",
    response_model=FrameProcessResponse,
    dependencies=[Depends(check_frame_payload_limit)],
)
@limiter.limit("120/minute")
async def process_frame(
    request: Request,
    payload: FrameProcessRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Defensively processes webcam video frame for kinematics tracking:
    1. Rejects oversized payloads (>5MB) with 413 before parsing.
    2. Enforces concurrency limit (max 10 parallel frames) and timeouts.
    3. Defensively decodes base64 and verifies cv2.imdecode success.
    4. Enforces resolution limit (max 1920x1080).
    5. Rejects corrupt or invalid images with 422.
    """
    encoded_img = payload.image or payload.frame

    # Concurrency control & execution timeout
    try:
        await asyncio.wait_for(_cv_concurrency_semaphore.acquire(), timeout=1.0)
    except (asyncio.TimeoutError, TimeoutError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="CV processing server busy: Maximum simultaneous frame tasks reached.",
        )

    try:
        tracking_val = (
            payload.tracking_method.value
            if hasattr(payload.tracking_method, "value")
            else str(payload.tracking_method)
        )
        results = await asyncio.wait_for(
            asyncio.to_thread(
                cv_tracker.process_frame,
                base64_img=encoded_img,
                tracking_method=tracking_val,
                color_target=payload.color_target,
                px_to_meters=payload.px_to_meters,
                confidence_threshold=payload.confidence_threshold,
                nms_threshold=payload.nms_threshold,
            ),
            timeout=5.0,
        )
        results["user_id"] = str(current_user["id"])
        return results
    except PayloadTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except (InvalidImageError, DimensionLimitExceededError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except (asyncio.TimeoutError, TimeoutError):
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Frame processing timed out.",
        )
    except Exception as e:
        logger.exception(f"Unexpected error during frame processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error while processing frame.",
        )
    finally:
        _cv_concurrency_semaphore.release()


@router.post("/process-frame-binary", response_model=FrameProcessResponse)
@limiter.limit("120/minute")
async def process_frame_binary(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    Direct binary image upload endpoint.
    Eliminates base64 memory and CPU decoding overhead for high-performance streaming.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FRAME_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large: Binary video frame exceeds 5MB limit.",
        )

    raw_bytes = await request.body()
    try:
        results = cv_tracker.process_binary_frame(raw_bytes)
        results["user_id"] = str(current_user["id"])
        return results
    except PayloadTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        )
    except (InvalidImageError, DimensionLimitExceededError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.post("/engagement", response_model=EngagementResponse)
@limiter.limit("60/minute")
async def log_engagement(
    request: Request,
    event: EngagementEvent,
    current_user: dict = Depends(get_current_user),
):
    """
    Logs CV engagement state with validated bounds, authentication, and rate limiting.
    """
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10_240:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large: Engagement event payload must be under 10KB.",
        )

    canonical_uid = str(current_user["id"])

    if event.user_id and str(event.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot log engagement events on behalf of another user.",
        )

    timestamp = time.time()
    iso_timestamp = datetime.now(timezone.utc).isoformat()

    event_record = {
        "user_id": canonical_uid,
        "state": event.state,
        "confidence": event.confidence,
        "timestamp": timestamp,
        "recorded_at": iso_timestamp,
        "model_version": event.model_version or "v1.0.0-cv-heuristics",
        "session_id": event.session_id,
        "is_estimate": True,
        "disclaimer": "Engagement classification is an estimated heuristic signal, not a definitive psychological judgment of student attention.",
    }

    logger.info(
        f"Engagement estimate logged for user {canonical_uid}: {event.state} "
        f"(confidence: {event.confidence:.2f}, model: {event_record['model_version']})"
    )

    return {
        "status": "success",
        "event": event_record,
    }
