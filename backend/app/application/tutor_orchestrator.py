"""
Tutor Workflow Orchestrator - Application Layer
Problem 45: Service boundaries separation.
Coordinates use case execution across AI, Retrieval, Persistence, and Infrastructure layers.
Does not perform direct SQL queries or raw SDK model calls; delegates to explicit layer interfaces.
"""
import asyncio
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Optional, Union

from fastapi import Request

from app.ai_agent.ai_client import AIClientProtocol
from app.ai_agent.learning_evaluation import LearningState, evaluate_learning_interaction
from app.ai_agent.retrieval_service import RetrievalProtocol
from app.core_backend.core.observability import record_model_inference_metrics
from app.core_backend.knowledge_graph import kg_manager
from app.core_backend.repositories.memory_repository import MemoryRepositoryProtocol
from app.logger import logger

MAX_CONCURRENT_GENERATIONS = int(os.getenv("MAX_CONCURRENT_GENERATIONS", "5"))
MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "30.0"))


class SSEEventName:
    METADATA = "metadata"
    TOKEN = "token"
    ERROR = "error"
    DONE = "done"
    EVALUATION = "evaluation"
    MASTERY = "mastery"


def make_sse_event(
    payload: dict,
    event: Optional[str] = None,
    event_id: Optional[Union[int, str]] = None,
) -> str:
    """Formats compliant Server-Sent Events (SSE) data frame."""
    if event is None:
        if payload.get("done") is True:
            event = SSEEventName.DONE
        elif payload.get("error") or payload.get("status") == "error":
            event = SSEEventName.ERROR
        elif "token" in payload or "text" in payload:
            event = SSEEventName.TOKEN
        elif "evaluation" in payload:
            event = SSEEventName.EVALUATION
        elif "kg_update" in payload:
            event = SSEEventName.MASTERY
        else:
            event = payload.get("event", "message")

    payload["event"] = event

    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(payload, default=str)}")
    return "\n".join(lines) + "\n\n"


class TutorOrchestrator:
    """
    Application Layer Use Case Orchestrator for AI Tutor interactions.
    Coordinates AI Layer, Retrieval Layer, Persistence Layer, and Observability.
    """
    def __init__(
        self,
        ai_client: AIClientProtocol,
        retrieval_service: RetrievalProtocol,
        memory_repository: MemoryRepositoryProtocol,
        concurrency_semaphore: Optional[asyncio.Semaphore] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        self.ai_client = ai_client
        self.retrieval_service = retrieval_service
        self.memory_repository = memory_repository
        self._concurrency_semaphore = concurrency_semaphore or asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
        self.executor = executor

    async def execute_tutor_stream(
        self,
        prompt: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        concept: Optional[str] = None,
        question: Optional[str] = None,
        request: Optional[Request] = None,
        last_event_id: Optional[str] = None,
        generate_embedding_fn: Optional[Any] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Orchestrates full Socratic tutor interaction workflow:
        1. Emits initial metadata event.
        2. Evaluates answer against concept rubric if concept/question is provided.
        3. Retrieves relevant conversational memories via retrieval service.
        4. Composes pedagogical prompt with prerequisites if needed.
        5. Streams model tokens from AI client.
        6. Persists conversation memory to repository.
        7. Records inference telemetry.
        """
        request_id = f"req_{uuid.uuid4().hex[:10]}"
        event_counter = 0
        start_time = time.perf_counter()

        def emit(event_type: str, data: dict) -> str:
            nonlocal event_counter
            event_counter += 1
            return make_sse_event(payload=data, event=event_type, event_id=event_counter)

        # Guard: Check model readiness
        if not self.ai_client.is_configured():
            logger.warning(f"[{request_id}] Tutor request rejected: AI client unconfigured.")
            yield emit(SSEEventName.ERROR, {
                "error": "The tutor is temporarily unavailable.",
                "error_code": "MODEL_UNCONFIGURED",
                "text": "The tutor is temporarily unavailable. Please contact your administrator.",
                "request_id": request_id,
                "status": "error",
            })
            return

        acquired = False
        try:
            # Concurrency control
            try:
                await asyncio.wait_for(self._concurrency_semaphore.acquire(), timeout=1.5)
                acquired = True
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning(f"[{request_id}] Concurrency ceiling reached.")
                yield emit(SSEEventName.ERROR, {
                    "error": "The tutor is currently at maximum capacity. Please retry shortly.",
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "text": "The tutor is currently busy assisting other students. Please try again shortly.",
                    "request_id": request_id,
                    "status": "error",
                })
                return

            # Check client disconnection
            if request and await request.is_disconnected():
                logger.info(f"[{request_id}] Client disconnected before generation.")
                return

            sess_id = session_id or f"sess_{user_id[:8]}"
            yield emit(SSEEventName.METADATA, {
                "request_id": request_id,
                "model": self.ai_client.model_name,
                "session_id": sess_id,
                "reconnect_last_event_id": last_event_id,
                "timestamp": time.time(),
                "status": "started",
            })

            eval_context_note = ""

            # Step 1: Learning evaluation use case
            if concept and question:
                eval_res = await evaluate_learning_interaction(
                    model=getattr(self.ai_client, "model", None),
                    concept=concept,
                    question=question,
                    student_answer=prompt,
                )
                yield emit(SSEEventName.EVALUATION, {
                    "evaluation": eval_res.model_dump(),
                    "request_id": request_id,
                })

                if eval_res.is_correct and eval_res.confidence >= 0.80:
                    awarded, xp = self.memory_repository.award_mastery_xp(
                        user_id=user_id,
                        concept=concept,
                        amount=100,
                    )
                    eval_res.mastery_awarded = awarded
                    eval_res.xp_awarded = xp if awarded else 0
                    eval_res.state = LearningState.MASTERY_CONFIRMED

                    if awarded:
                        yield emit(SSEEventName.MASTERY, {
                            "kg_update": f"{concept} Mastered",
                            "xp_awarded": eval_res.xp_awarded,
                            "request_id": request_id,
                        })

                eval_context_note = (
                    f"\nLearning Evaluation State:\n"
                    f"- Concept: {concept}\n"
                    f"- Question: {question}\n"
                    f"- Result is_correct: {eval_res.is_correct} (confidence: {eval_res.confidence})\n"
                    f"- Feedback: {eval_res.feedback}\n"
                    f"Use this evaluation to guide your Socratic response."
                )

            # Step 2: Context Retrieval use case (graceful degradation)
            try:
                if generate_embedding_fn is not None:
                    try:
                        past_context = await self.retrieval_service.retrieve_context(
                            query=prompt,
                            user_id=user_id,
                            session_id=sess_id,
                            top_k=3,
                            embedding_fn=generate_embedding_fn,
                        )
                    except TypeError:
                        past_context = await self.retrieval_service.retrieve_context(
                            query=prompt,
                            user_id=user_id,
                            session_id=sess_id,
                            top_k=3,
                        )
                else:
                    past_context = await self.retrieval_service.retrieve_context(
                        query=prompt,
                        user_id=user_id,
                        session_id=sess_id,
                        top_k=3,
                    )
            except Exception as retrieval_err:
                logger.warning(f"[{request_id}] Retrieval service failure ({type(retrieval_err).__name__}): {retrieval_err}. Degraded fallback active.")
                past_context = []

            # Step 3: Prompt assembly
            sys_prompt = (
                "You are a friendly and adaptive AI physics tutor. "
                "Provide simple, clear explanations with intuitive analogies. "
                "Keep responses concise and bounded."
            )
            if eval_context_note:
                sys_prompt += f"\n{eval_context_note}"

            if past_context and isinstance(past_context, list) and "[LOW_CONFIDENCE]" in str(past_context[0]):
                sys_prompt += "\nSystem Note: Low confidence. Use knowledge graph prerequisites."
                if "newton" in prompt.lower():
                    loop = asyncio.get_running_loop()
                    prereqs = await loop.run_in_executor(
                        self.executor,
                        lambda: kg_manager.get_prerequisites("Newton's 3rd Law"),
                    )
                    sys_prompt += f"\nSuggest prerequisites first: {', '.join(prereqs)}"
            elif past_context:
                sys_prompt += f"\nUser historical context: {past_context}"

            # Step 4: Stream completion tokens from AI client
            full_text = ""
            chunk_count = 0
            is_cancelled = request.is_disconnected if request else None

            try:
                async for chunk_text in self.ai_client.stream_completion(
                    prompt=prompt,
                    system_instruction=sys_prompt,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS,
                    is_cancelled=is_cancelled,
                ):
                    chunk_count += 1
                    full_text += chunk_text
                    yield emit(SSEEventName.TOKEN, {
                        "token": chunk_text,
                        "text": chunk_text,
                        "delta": chunk_text,
                        "index": chunk_count,
                        "request_id": request_id,
                    })

                # Step 5: Terminal Done Event & Observability
                duration = round(time.perf_counter() - start_time, 3)
                prompt_tokens = max(1, len(prompt) // 4)
                completion_tokens = max(1, len(full_text) // 4)
                total_tokens = max(1, (len(prompt) + len(full_text)) // 4)

                try:
                    record_model_inference_metrics(
                        model=self.ai_client.model_name,
                        operation="stream_completion",
                        duration_seconds=duration,
                        token_usage={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": total_tokens,
                        },
                        status="success",
                    )
                except Exception as m_err:
                    logger.warning(f"[{request_id}] Failed to record model metric: {m_err}")

                yield emit(SSEEventName.DONE, {
                    "done": True,
                    "status": "completed",
                    "finish_reason": "stop",
                    "request_id": request_id,
                    "usage": {
                        "prompt_tokens_est": prompt_tokens,
                        "completion_tokens_est": completion_tokens,
                        "total_tokens_est": total_tokens,
                        "duration_seconds": duration,
                        "chunks_emitted": chunk_count,
                    },
                    "timestamp": time.time(),
                })

                # Step 6: Asynchronous persistence of interaction memory in worker thread
                try:
                    emb_generator = generate_embedding_fn or self.retrieval_service.generate_query_embedding
                    emb = await emb_generator(full_text)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        self.executor,
                        lambda: self.memory_repository.save_memory(
                            session_id=sess_id,
                            text=f"Q: {prompt} A: {full_text}",
                            embedding=emb,
                            user_id=user_id,
                        ),
                    )
                except Exception as save_err:
                    logger.warning(f"[{request_id}] Failed to persist interaction memory: {save_err}")

            except (asyncio.TimeoutError, TimeoutError):
                duration = round(time.perf_counter() - start_time, 3)
                try:
                    record_model_inference_metrics(
                        model=self.ai_client.model_name,
                        operation="stream_completion",
                        duration_seconds=duration,
                        status="timeout",
                        error_message="Model generation timed out",
                    )
                except Exception:
                    pass
                logger.warning(f"[{request_id}] Model generation timed out.")
                yield emit(SSEEventName.ERROR, {
                    "error": "The tutor took too long to respond.",
                    "error_code": "MODEL_TIMEOUT",
                    "text": "The tutor took too long to respond. Please try again.",
                    "request_id": request_id,
                    "status": "error",
                })
            except Exception as stream_err:
                duration = round(time.perf_counter() - start_time, 3)
                try:
                    record_model_inference_metrics(
                        model=self.ai_client.model_name,
                        operation="stream_completion",
                        duration_seconds=duration,
                        status="error",
                        error_message=str(stream_err),
                    )
                except Exception:
                    pass

                err_str = str(stream_err).lower()
                err_cls = type(stream_err).__name__.lower()

                if "timeout" in err_cls or "timed out" in err_str:
                    logger.warning(f"[{request_id}] Model generation timed out: {stream_err}")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor took too long to respond.",
                        "error_code": "MODEL_TIMEOUT",
                        "text": "The tutor took too long to respond. Please try again.",
                        "request_id": request_id,
                        "status": "error",
                    })
                elif "quota" in err_str or "resource_exhausted" in err_str or "429" in err_str:
                    logger.warning(f"[{request_id}] AI model quota exhausted: {stream_err}")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor is currently experiencing high demand. Please try again shortly.",
                        "error_code": "QUOTA_EXHAUSTED",
                        "text": "The tutor is currently experiencing high demand. Please try again shortly.",
                        "request_id": request_id,
                        "status": "error",
                    })
                else:
                    logger.exception(f"[{request_id}] Model streaming error: {stream_err}")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor is temporarily unavailable.",
                        "error_code": "MODEL_STREAM_ERROR",
                        "text": "The tutor is temporarily unavailable. Please try again later.",
                        "request_id": request_id,
                        "status": "error",
                    })

        except asyncio.CancelledError:
            logger.info(f"[{request_id}] Stream cancelled by client.")
            return
        except Exception as unhandled:
            logger.exception(f"[{request_id}] Critical failure in tutor orchestrator: {unhandled}")
            yield make_sse_event({
                "error": "The tutor is temporarily unavailable.",
                "error_code": "INTERNAL_STREAM_FAILURE",
                "text": "The tutor is temporarily unavailable. Please try again later.",
                "request_id": request_id,
                "status": "error",
            }, event=SSEEventName.ERROR)
        finally:
            if acquired:
                self._concurrency_semaphore.release()
            try:
                from app.core_backend.core.observability import update_queue_depth
                active = MAX_CONCURRENT_GENERATIONS - getattr(self._concurrency_semaphore, "_value", MAX_CONCURRENT_GENERATIONS)
                update_queue_depth("tutor_concurrency", float(max(0, active)))
            except Exception:
                pass
