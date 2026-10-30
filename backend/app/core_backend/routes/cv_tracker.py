import time
import asyncio
from datetime import datetime, timezone
from typing import Literal, Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel, Field
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


class FrameProcessRequest(BaseModel):
    image: Optional[str] = Field(None, description="Base64 encoded frame")
    frame: Optional[str] = Field(None, description="Alternative key for base64 frame")
    tracking_method: Optional[str] = "color"
    color_target: Optional[str] = "red"
    px_to_meters: Optional[float] = 0.005
    confidence_threshold: Optional[float] = Field(0.25, ge=0.0, le=1.0)
    nms_threshold: Optional[float] = Field(0.45, ge=0.0, le=1.0)


class EngagementEvent(BaseModel):
    user_id: Optional[str] = Field(
        None,
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


@router.get("/")
def get_cv_tracker_status():
    return {"status": "CV Tracker endpoint is active."}


@router.get("/readiness")
def check_cv_readiness():
    """
    Explicit model-loading and readiness verification endpoint.
    Reports active detection model, weights loaded, and supported inference modes.
    """
    return cv_tracker.check_readiness()


@router.post("/reset-tracker")
def reset_cv_tracker(current_user: dict = Depends(get_current_user)):
    """
    Resets object trajectory tracking history and clears persistent IDs.
    """
    cv_tracker.reset_tracker()
    return {"status": "success", "message": "Object trajectory tracker reset."}


@router.post("/process-frame")
@limiter.limit("120/minute")
async def process_frame(
    request: Request,
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
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FRAME_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large: Video frame payload exceeds 5MB limit.",
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON payload format.",
        )

    encoded_img = data.get("image") or data.get("frame")
    if not encoded_img:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing image data: payload must include 'image' or 'frame' string.",
        )

    # Concurrency control & execution timeout
    try:
        await asyncio.wait_for(_cv_concurrency_semaphore.acquire(), timeout=1.0)
    except (asyncio.TimeoutError, TimeoutError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="CV processing server busy: Maximum simultaneous frame tasks reached.",
        )

    try:
        results = await asyncio.wait_for(
            asyncio.to_thread(
                cv_tracker.process_frame,
                base64_img=encoded_img,
                tracking_method=data.get("tracking_method", "color"),
                color_target=data.get("color_target", "red"),
                px_to_meters=data.get("px_to_meters", 0.005),
                confidence_threshold=data.get("confidence_threshold", 0.25),
                nms_threshold=data.get("nms_threshold", 0.45),
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


@router.post("/process-frame-binary")
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


@router.post("/engagement")
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
