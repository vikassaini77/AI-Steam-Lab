import os
import json
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
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
from app.core_backend.database.pgvector_db import DatabasePersistenceError
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


class ChatRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Prompt capped at 2,000 characters to prevent token exhaustion",
    )
    history: Optional[List[Dict[str, Any]]] = Field(
        None,
        max_length=20,
        description="Conversation history capped at 20 turns",
    )
    experiment_state: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = Field(None, max_length=100)
    concept: Optional[str] = Field(None, max_length=100)
    question: Optional[str] = Field(None, max_length=500)


class ConceptEvaluationRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=100, description="Physics concept being evaluated")
    question: str = Field(..., min_length=1, max_length=500, description="The conceptual question presented to student")
    answer: str = Field(..., min_length=1, max_length=1000, description="Student's answer text")


@router.get("/")
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
    daily_allowed, current_count = db_manager.check_and_increment_daily_usage(canonical_uid, limit=100)
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


@router.delete("/memories")
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
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to delete memories for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Memory records could not be deleted.",
        )


@router.delete("/memories/{memory_id}")
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
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to delete memory {memory_id} for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database persistence unavailable: Memory {memory_id} could not be deleted.",
        )


@router.get("/memories/export")
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
