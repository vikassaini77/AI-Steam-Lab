import os
import time
import json
import uuid
import asyncio
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, AsyncGenerator, Union, Any
from fastapi import Request
import google.generativeai as genai
from app.core_backend.database.supabase_db import DatabaseManager
from app.cache import get_cache, set_cache
from app.core_backend.knowledge_graph import kg_manager
from app.ai_agent.embedding_service import (
    generate_embedding as generate_real_embedding,
    EmbeddingError,
    EXPECTED_EMBEDDING_DIM,
)
from app.ai_agent.learning_evaluation import (
    LearningState,
    EvaluationResult,
    evaluate_learning_interaction,
)
from app.logger import logger

MAX_CONCURRENT_GENERATIONS = int(os.getenv("MAX_CONCURRENT_GENERATIONS", "5"))
MAX_WORKER_THREADS = int(os.getenv("TUTOR_MAX_THREADS", "8"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "30.0"))

# Thread pool for isolating synchronous model / DB calls from the event loop
_tutor_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_tutor_executor() -> ThreadPoolExecutor:
    """Lazily creates and returns the shared ThreadPoolExecutor on demand."""
    global _tutor_executor
    with _executor_lock:
        if _tutor_executor is None:
            _tutor_executor = ThreadPoolExecutor(
                max_workers=MAX_WORKER_THREADS,
                thread_name_prefix="tutor_worker",
            )
        return _tutor_executor


def shutdown_tutor_executor(wait: bool = False):
    """Gracefully shuts down the shared ThreadPoolExecutor during application shutdown."""
    global _tutor_executor
    with _executor_lock:
        if _tutor_executor is not None:
            _tutor_executor.shutdown(wait=wait)
            _tutor_executor = None


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
    """
    Formats a compliant Server-Sent Events (SSE) data frame adhering to the formal protocol:
    event: <event_name>
    id: <event_id>
    data: <json_string>

    Ensures both standard EventSource parser compliance and backward compatibility
    with consumers reading data JSON payload directly.
    """
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


async def _stream_model_chunks(
    model,
    prompt: str,
    generation_config: dict,
    executor: ThreadPoolExecutor,
    timeout_seconds: float,
    request: Optional[Request] = None,
) -> AsyncGenerator[str, None]:
    """
    Streams model response chunks without blocking the asyncio event loop:
    1. Uses native async streaming (generate_content_async) when available.
    2. If the model is synchronous, isolates generation in a bounded thread pool
       and pipes chunks through an asyncio.Queue.
    3. Enforces upstream timeout per chunk / request and handles cancellation.
    """
    use_async = (
        isinstance(model, genai.GenerativeModel)
        or (
            hasattr(model, "generate_content_async")
            and not hasattr(model, "_mock_return_value")
        )
    )

    if use_async:
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    prompt,
                    stream=True,
                    generation_config=generation_config,
                ),
                timeout=timeout_seconds,
            )
            async for chunk in response:
                if request and await request.is_disconnected():
                    logger.info("Client disconnected during async stream generation.")
                    break
                text = getattr(chunk, "text", "")
                if text:
                    yield text
        except (asyncio.TimeoutError, TimeoutError):
            raise TimeoutError(f"Model generation timed out after {timeout_seconds}s")
    else:
        # Synchronous fallback isolated in bounded thread pool
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sentinel = object()

        def _sync_worker():
            try:
                res = model.generate_content(
                    prompt,
                    stream=True,
                    generation_config=generation_config,
                )
                for chunk in res:
                    text = getattr(chunk, "text", str(chunk))
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", text))
                loop.call_soon_threadsafe(queue.put_nowait, ("done", sentinel))
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))

        loop.run_in_executor(executor, _sync_worker)

        while True:
            if request and await request.is_disconnected():
                logger.info("Client disconnected during sync-queue stream consumption.")
                break
            try:
                msg_type, val = await asyncio.wait_for(queue.get(), timeout=timeout_seconds)
            except (asyncio.TimeoutError, TimeoutError):
                raise TimeoutError(f"Model generation timed out after {timeout_seconds}s")

            if msg_type == "chunk":
                if val:
                    yield val
            elif msg_type == "done":
                break
            elif msg_type == "error":
                raise val


class AITutorService:
    def __init__(
        self,
        db=None,
        executor: Optional[ThreadPoolExecutor] = None,
        model: Optional[Any] = None,
    ):
        if model is not None:
            self.model = model
        else:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(
                    "gemini-2.5-flash",
                    generation_config={
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "temperature": 0.7,
                    },
                )
                logger.info("Gemini API Client initialized with output token limits.")
            else:
                self.model = None

        if db is not None:
            self.db = db
        elif os.getenv("USE_PGVECTOR", "false").lower() in ("true", "1") or os.getenv("POSTGRES_URL"):
            try:
                from app.core_backend.database.pgvector_db import PGVectorManager
                self.db = PGVectorManager()
            except Exception as e:
                logger.warning(f"Falling back to DatabaseManager: {e}")
                self.db = DatabaseManager()
        else:
            self.db = DatabaseManager()

        self._concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
        self._executor = executor or get_tutor_executor()

    async def generate_embedding(self, text: str):
        """
        Generates real 768-dimensional semantic embeddings using the configured embedding model.
        Fails explicitly or handles degraded mode rather than returning fake constant vectors.
        """
        return await generate_real_embedding(text)

    async def retrieve_memories(
        self,
        prompt: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = True,
    ):
        """
        Executes hybrid retrieval combining semantic vector search and keyword/BM25 search via RRF.
        Offloads synchronous database search to bounded thread pool to avoid blocking event loop.
        Records scores and document IDs for evaluation.
        """
        normalized_query = " ".join(prompt.strip().split())
        q_emb = await self.generate_embedding(normalized_query)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self.db.search_memories(
                query_embedding=q_emb,
                query_text=normalized_query,
                user_id=user_id,
                session_id=session_id,
                experiment_id=experiment_id,
                top_k=top_k,
                return_metadata=return_metadata,
            ),
        )

    async def evaluate_answer(
        self,
        user_id: str,
        concept: str,
        question: str,
        answer: str,
    ) -> EvaluationResult:
        """
        Authoritatively evaluates a student's answer against a concept and question.
        Uses pedagogical rubrics and AI model evaluation.
        Authoritative XP rewards are server-side validated and strictly idempotent.
        """
        # Decouple evaluation judgment from state mutation
        eval_result = await evaluate_learning_interaction(
            model=self.model,
            concept=concept,
            question=question,
            student_answer=answer,
        )

        # Authoritative database mutation occurs ONLY upon validated mastery
        if eval_result.is_correct and eval_result.confidence >= 0.80:
            loop = asyncio.get_running_loop()
            newly_awarded, _ = await loop.run_in_executor(
                self._executor,
                lambda: self.db.award_mastery_xp(
                    user_id=user_id,
                    concept=concept,
                    amount=100,
                ),
            )
            eval_result.mastery_awarded = newly_awarded
            eval_result.xp_awarded = 100 if newly_awarded else 0
            eval_result.state = LearningState.MASTERY_CONFIRMED
        else:
            eval_result.mastery_awarded = False
            eval_result.xp_awarded = 0
            eval_result.state = LearningState.ANSWER_EVALUATED

        return eval_result

    async def stream_chat(
        self,
        req,
        user_id: str = "default_user",
        request: Optional[Request] = None,
        last_event_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        request_id = f"req_{uuid.uuid4().hex[:10]}"
        event_counter = 0
        start_time = time.perf_counter()

        def emit(event_type: str, data: dict) -> str:
            nonlocal event_counter
            event_counter += 1
            return make_sse_event(payload=data, event=event_type, event_id=event_counter)

        if not self.model:
            logger.warning(f"[{request_id}] Tutor request rejected: Model not configured (missing GEMINI_API_KEY).")
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
            # 1. Acquire concurrency slot with short timeout
            try:
                await asyncio.wait_for(self._concurrency_semaphore.acquire(), timeout=1.5)
                acquired = True
                try:
                    from app.core_backend.core.observability import update_queue_depth
                    active = MAX_CONCURRENT_GENERATIONS - getattr(self._concurrency_semaphore, "_value", MAX_CONCURRENT_GENERATIONS)
                    update_queue_depth("tutor_concurrency", float(max(0, active)))
                except Exception:
                    pass
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning(f"[{request_id}] Concurrency ceiling reached: worker generations at capacity.")
                yield emit(SSEEventName.ERROR, {
                    "error": "The tutor is currently at maximum capacity. Please retry in a few moments.",
                    "error_code": "CONCURRENCY_LIMIT_EXCEEDED",
                    "text": "The tutor is currently busy assisting other students. Please try again shortly.",
                    "request_id": request_id,
                    "status": "error",
                })
                return

            # Check if caller already disconnected before model call
            if request and await request.is_disconnected():
                logger.info(f"[{request_id}] Client disconnected early before generation started.")
                return

            # Emit initial metadata frame containing safe request and model metadata
            session_id = str(getattr(req, "session_id", None) or f"sess_{user_id[:8]}")
            raw_model_name = getattr(self.model, "model_name", None)
            if isinstance(raw_model_name, str):
                model_name = raw_model_name
            else:
                model_name = "gemini-2.5-flash" if self.model else "unknown"
            yield emit(SSEEventName.METADATA, {
                "request_id": request_id,
                "model": model_name,
                "session_id": session_id,
                "reconnect_last_event_id": last_event_id,
                "timestamp": time.time(),
                "status": "started",
            })

            prompt_lower = req.prompt.lower()

            # If explicit concept evaluation is requested in this interaction
            target_concept = getattr(req, "concept", None)
            target_question = getattr(req, "question", None)
            eval_context_note = ""

            if target_concept and target_question:
                eval_res = await self.evaluate_answer(
                    user_id=user_id,
                    concept=target_concept,
                    question=target_question,
                    answer=req.prompt,
                )
                yield emit(SSEEventName.EVALUATION, {
                    "evaluation": eval_res.model_dump(),
                    "request_id": request_id,
                })
                if eval_res.mastery_awarded:
                    yield emit(SSEEventName.MASTERY, {
                        "kg_update": f"{target_concept} Mastered",
                        "xp_awarded": eval_res.xp_awarded,
                        "request_id": request_id,
                    })

                eval_context_note = (
                    f"\nLearning Evaluation State:\n"
                    f"- Concept: {target_concept}\n"
                    f"- Question: {target_question}\n"
                    f"- Result is_correct: {eval_res.is_correct} (confidence: {eval_res.confidence})\n"
                    f"- Feedback: {eval_res.feedback}\n"
                    f"Use this evaluation to guide your Socratic response."
                )

            # --- Hybrid RAG Retrieval (Semantic + Keyword via RRF) ---
            try:
                normalized_query = " ".join(req.prompt.strip().split())
                q_emb = await self.generate_embedding(normalized_query)
                loop = asyncio.get_running_loop()
                past_context = await loop.run_in_executor(
                    self._executor,
                    lambda: self.db.search_memories(
                        query_embedding=q_emb,
                        query_text=normalized_query,
                        user_id=user_id,
                        top_k=3,
                    ),
                )
            except Exception as retrieval_err:
                # Log diagnostic information on server, but do not crash or leak internal details to client
                logger.warning(f"[{request_id}] Hybrid memory retrieval degraded mode ({type(retrieval_err).__name__}): {retrieval_err}")
                past_context = ""

            sys_prompt = (
                "You are a friendly and adaptive AI physics tutor. "
                "Provide simple, clear explanations with intuitive analogies. "
                "Keep responses concise and bounded."
            )
            if eval_context_note:
                sys_prompt += f"\n{eval_context_note}"

            if past_context and "[LOW_CONFIDENCE]" in past_context[0]:
                sys_prompt += "\nSystem Note: Low confidence. Use knowledge graph prerequisites."
                if "newton" in prompt_lower:
                    loop = asyncio.get_running_loop()
                    prereqs = await loop.run_in_executor(
                        self._executor,
                        lambda: kg_manager.get_prerequisites("Newton's 3rd Law"),
                    )
                    sys_prompt += f"\nSuggest prerequisites first: {', '.join(prereqs)}"
            elif past_context:
                sys_prompt += f"\nUser historical context: {past_context}"

            # --- Model Call with Timeout, Non-blocking Streaming, and Cancellation ---
            try:
                full_text = ""
                chunk_count = 0
                async for chunk_text in _stream_model_chunks(
                    model=self.model,
                    prompt=f"{sys_prompt}\nUser: {req.prompt}",
                    generation_config={
                        "max_output_tokens": MAX_OUTPUT_TOKENS,
                        "temperature": 0.7,
                    },
                    executor=self._executor,
                    timeout_seconds=MODEL_TIMEOUT_SECONDS,
                    request=request,
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

                # Terminal Completion Event with full usage statistics
                duration = round(time.perf_counter() - start_time, 3)
                prompt_tokens = max(1, len(req.prompt) // 4)
                completion_tokens = max(1, len(full_text) // 4)
                total_tokens = max(1, (len(req.prompt) + len(full_text)) // 4)

                try:
                    from app.core_backend.core.observability import record_model_inference_metrics
                    record_model_inference_metrics(
                        model=model_name,
                        operation="chat_stream",
                        duration_seconds=duration,
                        token_usage={
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                        },
                        status="success",
                    )
                except Exception:
                    pass

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

                # Save memory in bounded executor without blocking event loop
                try:
                    session_id = str(getattr(req, "session_id", None) or f"sess_{user_id[:8]}")
                    emb = await self.generate_embedding(full_text)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        self._executor,
                        lambda: self.db.save_memory(
                            session_id=session_id,
                            text=f"Q: {req.prompt} A: {full_text}",
                            embedding=emb,
                            user_id=user_id,
                        ),
                    )
                except Exception as save_err:
                    logger.exception(f"[{request_id}] Error persisting conversation memory: {type(save_err).__name__}")

            except (asyncio.TimeoutError, TimeoutError):
                duration = round(time.perf_counter() - start_time, 3)
                try:
                    from app.core_backend.core.observability import record_model_inference_metrics
                    record_model_inference_metrics(
                        model=model_name,
                        operation="chat_stream",
                        duration_seconds=duration,
                        status="timeout",
                        error_message="timeout",
                    )
                except Exception:
                    pass
                logger.warning(f"[{request_id}] Model generation timed out after {MODEL_TIMEOUT_SECONDS}s")
                yield emit(SSEEventName.ERROR, {
                    "error": "The tutor took too long to respond.",
                    "error_code": "MODEL_TIMEOUT",
                    "text": "The tutor took too long to respond. Please try again.",
                    "request_id": request_id,
                    "status": "error",
                })
            except Exception as model_err:
                duration = round(time.perf_counter() - start_time, 3)
                err_lower = str(model_err).lower()
                if "timeout" in err_lower or "timed out" in err_lower or "deadline" in err_lower:
                    try:
                        from app.core_backend.core.observability import record_model_inference_metrics
                        record_model_inference_metrics(
                            model=model_name,
                            operation="chat_stream",
                            duration_seconds=duration,
                            status="timeout",
                            error_message="timeout",
                        )
                    except Exception:
                        pass
                    logger.warning(f"[{request_id}] Upstream model request timed out")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor took too long to respond.",
                        "error_code": "MODEL_TIMEOUT",
                        "text": "The tutor took too long to respond. Please try again.",
                        "request_id": request_id,
                        "status": "error",
                    })
                elif "quota" in err_lower or "resource_exhausted" in err_lower or "429" in err_lower:
                    try:
                        from app.core_backend.core.observability import record_model_inference_metrics
                        record_model_inference_metrics(
                            model=model_name,
                            operation="chat_stream",
                            duration_seconds=duration,
                            status="quota_exhausted",
                            error_message=str(model_err),
                        )
                    except Exception:
                        pass
                    logger.warning(f"[{request_id}] Upstream AI model quota exhausted: {type(model_err).__name__}")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor is currently experiencing high demand. Please try again shortly.",
                        "error_code": "QUOTA_EXHAUSTED",
                        "text": "The tutor is currently experiencing high demand. Please try again shortly.",
                        "request_id": request_id,
                        "status": "error",
                    })
                else:
                    try:
                        from app.core_backend.core.observability import record_model_inference_metrics
                        record_model_inference_metrics(
                            model=model_name,
                            operation="chat_stream",
                            duration_seconds=duration,
                            status="error",
                            error_message=str(model_err),
                        )
                    except Exception:
                        pass
                    logger.exception(f"[{request_id}] Unexpected model failure mid-stream: {type(model_err).__name__}")
                    yield emit(SSEEventName.ERROR, {
                        "error": "The tutor is temporarily unavailable.",
                        "error_code": "MODEL_STREAM_ERROR",
                        "text": "The tutor is temporarily unavailable. Please try again later.",
                        "request_id": request_id,
                        "status": "error",
                    })

        except asyncio.CancelledError:
            logger.info(f"[{request_id}] Client disconnected: stream cancelled.")
            return
        except Exception as unexpected_err:
            logger.exception(f"[{request_id}] Critical failure in tutor stream handler: {type(unexpected_err).__name__}")
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


def __getattr__(name: str):
    """Provides lazy access to tutor_executor for backward-compatible imports."""
    if name == "tutor_executor":
        return get_tutor_executor()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

