import asyncio
import os
import json
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from app.ai_agent.tutor_service import AITutorService
from app.ai_agent.learning_evaluation import EvaluationResult
from app.core_backend.core.dependencies import (
    get_current_user,
    get_db,
    get_tutor_service,
    get_database_manager,
)
from app.core_backend.core.limiter import limiter
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import DatabasePersistenceError, TenantIsolationError
from app.logger import logger

router = APIRouter()
get_tutor = get_tutor_service


def __getattr__(name: str):
    """Lazy backward-compatible attribute access for tutor_service and db without import side-effects."""
    if name == "tutor_service":
        try:
            return get_tutor_service()
        except Exception:
            return None
    if name == "db":
        try:
            return get_db()
        except Exception:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    MODEL = "model"


class ChatHistoryTurn(BaseModel):
    role: ChatRole = Field(
        ...,
        description="Role of conversational turn participant (user, assistant, system, model)",
    )
    content: Optional[str] = Field(None, max_length=4000, description="Message content")
    text: Optional[str] = Field(None, max_length=4000, description="Alternative field for message text")
    timestamp: Optional[float] = Field(None, ge=0.0, description="Turn epoch timestamp in seconds")

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="after")
    def validate_content_presence(self):
        if not (self.content or self.text):
            raise ValueError("ChatHistoryTurn must contain non-empty 'content' or 'text'.")
        return self


class ExperimentStateContext(BaseModel):
    experiment_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Type of active physics experiment (e.g. free_fall, pendulum, collision)",
    )
    parameters: Optional[Dict[str, Union[float, int, str, bool]]] = Field(
        None,
        description="Active simulation parameters map",
    )
    current_metrics: Optional[Dict[str, Union[float, int, str]]] = Field(
        None,
        description="Observed simulation metrics map",
    )
    time_elapsed: Optional[float] = Field(
        None,
        ge=0.0,
        le=100000.0,
        description="Simulation elapsed time in seconds",
    )
    status: Optional[str] = Field(
        None,
        max_length=50,
        description="Simulation status (running, paused, completed)",
    )

    model_config = {
        "extra": "forbid",
    }


class ChatRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Prompt capped at 2,000 characters to prevent token exhaustion",
    )
    history: Optional[List[ChatHistoryTurn]] = Field(
        None,
        max_length=20,
        description="Conversation history capped at 20 turns with typed roles and content",
    )
    experiment_state: Optional[ExperimentStateContext] = Field(
        None,
        description="Validated experiment simulation state and metrics",
    )
    session_id: Optional[str] = Field(None, max_length=100, description="Client session identifier")
    concept: Optional[str] = Field(None, max_length=100, description="Physics concept being discussed")
    question: Optional[str] = Field(None, max_length=500, description="Active question prompt")

    model_config = {
        "extra": "forbid",
    }


class ConceptEvaluationRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=100, description="Physics concept being evaluated")
    question: str = Field(..., min_length=1, max_length=500, description="The conceptual question presented to student")
    answer: str = Field(..., min_length=1, max_length=1000, description="Student's answer text")

    model_config = {
        "extra": "forbid",
    }


# Response Models for non-streaming endpoints
class TutorStatusResponse(BaseModel):
    status: str = Field(..., description="Service status message")


class DeleteMemoriesResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    message: str = Field(..., description="Human-readable result summary")
    deleted_count: int = Field(..., ge=0, description="Number of deleted memory records")


class DeleteSingleMemoryResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    message: str = Field(..., description="Human-readable result summary")


class ExportedMemoryItem(BaseModel):
    id: Optional[int] = Field(None, description="Memory record ID")
    content: Optional[str] = Field(None, description="Memory text content")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    user_id: Optional[str] = Field(None, description="Owning user ID")
    created_at: Optional[Union[str, datetime]] = Field(None, description="Creation timestamp")
    similarity: Optional[float] = Field(None, description="Similarity score if retrieved via vector search")
    rank: Optional[float] = Field(None, description="Combined search ranking score")

    model_config = {"extra": "allow"}


class ExportMemoriesResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    user_id: str = Field(..., description="Canonical user ID")
    count: int = Field(..., ge=0, description="Total number of exported memory records")
    memories: List[ExportedMemoryItem] = Field(default_factory=list, description="List of user memory records")


class ListMemoriesResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    user_id: str = Field(..., description="Canonical user ID")
    session_id: Optional[str] = Field(None, description="Session ID if filtered")
    count: int = Field(..., ge=0, description="Total count of returned memory records")
    memories: List[Dict[str, Any]] = Field(default_factory=list, description="List of user memory records")


class SessionHistoryResponse(BaseModel):
    status: str = Field(..., description="Operation status (success)")
    user_id: str = Field(..., description="Canonical user ID")
    session_id: str = Field(..., description="Session ID")
    count: int = Field(..., ge=0, description="Total count of returned turns")
    history: List[Dict[str, Any]] = Field(default_factory=list, description="Chronological conversation turns")


@router.get("/", response_model=TutorStatusResponse)
def get_tutor_status():
    return {"status": "Tutor endpoint is active."}


@router.post("/evaluate-answer", response_model=EvaluationResult)
@limiter.limit("30/minute")
async def evaluate_student_answer(
    request: Request,
    eval_req: ConceptEvaluationRequest,
    current_user: dict = Depends(get_current_user),
    tutor_svc: AITutorService = Depends(get_tutor_service),
):
    """
    Authoritative evaluation endpoint for student concept responses:
    - Replaces naive prompt substring checks with stateful learning evaluation.
    - Evaluates student answers against rubric criteria and models.
    - Awards mastery XP only after authoritative server-side validation.
    - Guarantees idempotency (repeated submissions do not award duplicate XP).
    """
    canonical_uid = str(current_user["id"])
    return await tutor_svc.evaluate_answer(
        user_id=canonical_uid,
        concept=eval_req.concept,
        question=eval_req.question,
        answer=eval_req.answer,
    )


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def chat_with_tutor(
    request: Request,
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
    tutor_svc: AITutorService = Depends(get_tutor_service),
    db_manager = Depends(get_db),
):
    """
    Streams AI Tutor responses with:
    - Route-specific rate limits (20 requests per minute).
    - Daily per-user request budget enforcement (100 requests per day).
    - Prompt length bounds (max 2,000 chars) and conversation history caps.
    - Worker-level concurrency limits and client disconnect handling.
    """
    canonical_uid = str(current_user["id"])

    # Enforce daily request budget
    daily_allowed, current_count = await asyncio.to_thread(db_manager.check_and_increment_daily_usage, canonical_uid, 100)
    if not daily_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily AI tutor request quota exceeded (100 requests/day). Please try again tomorrow.",
        )

    last_event_id = request.headers.get("last-event-id")
    return StreamingResponse(
        tutor_svc.stream_chat(
            req,
            user_id=canonical_uid,
            request=request,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Content-Type": "text/event-stream; charset=utf-8",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/memories", response_model=DeleteMemoriesResponse)
@limiter.limit("10/minute")
async def delete_user_memories(
    request: Request,
    session_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Account-level memory deletion workflow (Right to Erasure / Privacy):
    Deletes all vector memories associated with the authenticated user.
    Optionally scoped to a specific session_id.
    """
    canonical_uid = str(current_user["id"])
    try:
        deleted = active_db.delete_user_memories(user_id=canonical_uid, session_id=session_id)
        return {
            "status": "success",
            "message": f"Successfully deleted {deleted} memory records.",
            "deleted_count": deleted,
        }
    except TenantIsolationError as tie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(tie),
        )
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to delete memories for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Memory records could not be deleted.",
        )


@router.delete("/memories/{memory_id}", response_model=DeleteSingleMemoryResponse)
@limiter.limit("30/minute")
async def delete_single_memory(
    request: Request,
    memory_id: int,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Deletes a specific memory record with ownership verification.
    """
    canonical_uid = str(current_user["id"])
    try:
        deleted = active_db.delete_memory_by_id(memory_id=memory_id, user_id=canonical_uid)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory record not found or unauthorized.",
            )
        return {"status": "success", "message": f"Memory {memory_id} deleted."}
    except HTTPException:
        raise
    except TenantIsolationError as tie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(tie),
        )
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to delete memory {memory_id} for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database persistence unavailable: Memory {memory_id} could not be deleted.",
        )


@router.get("/memories/export", response_model=ExportMemoriesResponse)
@limiter.limit("5/minute")
async def export_user_memories(
    request: Request,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Data-export workflow for student account memories (Data Portability).
    """
    canonical_uid = str(current_user["id"])
    try:
        memories = active_db.export_user_memories(user_id=canonical_uid)
        return {
            "status": "success",
            "user_id": canonical_uid,
            "count": len(memories),
            "memories": memories,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to export memories for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Memory records could not be exported.",
        )



@router.get("/memories", response_model=ListMemoriesResponse)
@limiter.limit("30/minute")
async def list_user_memories(
    request: Request,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    List conversational memories for the authenticated user with optional session scoping and pagination.
    """
    canonical_uid = str(current_user["id"])
    try:
        memories = active_db.list_memories(
            user_id=canonical_uid,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "success",
            "user_id": canonical_uid,
            "session_id": session_id,
            "count": len(memories),
            "memories": memories,
        }
    except TenantIsolationError as tie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(tie),
        )
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to list memories for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Memory records could not be listed.",
        )


@router.get("/memories/session/{session_id}", response_model=SessionHistoryResponse)
@limiter.limit("30/minute")
async def get_session_history_endpoint(
    request: Request,
    session_id: str,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Retrieves chronological conversation history for a specific session.
    Strictly enforces that the session belongs to the authenticated user.
    """
    canonical_uid = str(current_user["id"])
    try:
        history = active_db.get_session_history(
            session_id=session_id,
            user_id=canonical_uid,
        )
        return {
            "status": "success",
            "user_id": canonical_uid,
            "session_id": session_id,
            "count": len(history),
            "history": history,
        }
    except TenantIsolationError as tie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(tie),
        )
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to retrieve session history for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Session history could not be retrieved.",
        )
