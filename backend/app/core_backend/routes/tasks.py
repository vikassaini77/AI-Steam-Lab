"""
NeuroLab AI: Asynchronous Tasks API Router
Problem 43: Task dispatch and durable result retrieval endpoints.
Provides:
- GET /api/v1/tasks/{task_id}: Queries task execution status, explicit state, and durable results.
- POST /api/v1/tasks/cv/process-frame-async: Dispatches asynchronous YOLOv8 / kinematics frame processing.
- POST /api/v1/tasks/tutor/generate-async: Dispatches asynchronous AI tutor generation.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel, Field

from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import limiter
from app.worker import (
    dispatch_async_task,
    get_celery_task_status,
    process_heavy_cv_frame,
    generate_ai_tutor_response,
    CVTaskPayload,
    AITaskPayload,
    TaskBrokerUnavailableError,
)
from app.logger import logger

router = APIRouter()


class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="Unique Celery task identifier")
    state: str = Field(..., description="Explicit task state: PENDING, STARTED, PROCESSING, SUCCESS, FAILURE, RETRY")
    status: str = Field(..., description="High-level status: pending, processing, completed, failed")
    progress: Optional[int] = Field(None, description="Completion percentage (0-100)")
    step: Optional[str] = Field(None, description="Current processing stage")
    result: Optional[Dict[str, Any]] = Field(None, description="Output payload on SUCCESS")
    error: Optional[str] = Field(None, description="Error message on FAILURE")
    ready: bool = Field(..., description="Whether task has reached terminal state")


class TaskDispatchResponse(BaseModel):
    task_id: str = Field(..., description="Unique Celery task identifier")
    status: str = Field(..., description="Dispatch status: queued or completed")
    state: str = Field(..., description="Initial task state")
    result: Optional[Dict[str, Any]] = Field(None, description="Inline result if async is disabled")


@router.get("/{task_id}", response_model=TaskStatusResponse)
@limiter.limit("120/minute")
def get_task_result(request: Request, task_id: str):
    """
    Retrieves the execution status, explicit state, and durable output of an asynchronous task.
    """
    if not task_id or not task_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_id parameter is required.",
        )
    task_info = get_celery_task_status(task_id.strip())
    return task_info


@router.post("/cv/process-frame-async", response_model=TaskDispatchResponse)
@limiter.limit("60/minute")
def dispatch_cv_frame_task(
    request: Request,
    payload: CVTaskPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    Dispatches a heavy YOLOv8 / kinematics frame processing task to Celery worker queue.
    """
    payload_dict = payload.model_dump()
    payload_dict["user_id"] = str(current_user.get("id", "anonymous"))

    try:
        task_res = dispatch_async_task(process_heavy_cv_frame, payload_dict)
    except TaskBrokerUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # If dispatched via Celery AsyncResult (has .id)
    if hasattr(task_res, "id"):
        return {
            "task_id": task_res.id,
            "status": "queued",
            "state": "PENDING",
            "result": None,
        }

    # If executed synchronously inline
    task_id = task_res.get("task_id", "sync_cv")
    return {
        "task_id": task_id,
        "status": "completed",
        "state": "SUCCESS",
        "result": task_res,
    }


@router.post("/tutor/generate-async", response_model=TaskDispatchResponse)
@limiter.limit("60/minute")
def dispatch_tutor_generate_task(
    request: Request,
    payload: AITaskPayload,
    current_user: dict = Depends(get_current_user),
):
    """
    Dispatches a background AI Tutor generation task to Celery worker queue.
    """
    payload_dict = payload.model_dump()
    payload_dict["user_id"] = str(current_user.get("id", "anonymous"))

    try:
        task_res = dispatch_async_task(generate_ai_tutor_response, payload_dict)
    except TaskBrokerUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    # If dispatched via Celery AsyncResult
    if hasattr(task_res, "id"):
        return {
            "task_id": task_res.id,
            "status": "queued",
            "state": "PENDING",
            "result": None,
        }

    # If executed synchronously inline
    task_id = task_res.get("task_id", "sync_ai")
    return {
        "task_id": task_id,
        "status": "completed",
        "state": "SUCCESS",
        "result": task_res,
    }

