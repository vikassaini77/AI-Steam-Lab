"""
AITutorService - Modular Application Facade
Problem 45: Service boundaries separation.
Unified facade coordinating AI layer, Retrieval layer, Persistence layer,
and Application orchestration while preserving 100% backward compatibility.
"""
import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, List, Optional

import google.generativeai as genai
from fastapi import Request

from app.ai_agent.ai_client import _DEFAULT_MODEL, GeminiAIClient, check_cancellation
from app.ai_agent.learning_evaluation import (
    EvaluationResult,
    LearningState,
    evaluate_learning_interaction,
)
from app.ai_agent.retrieval_service import TutorRetrievalService
from app.application.tutor_orchestrator import (
    MAX_CONCURRENT_GENERATIONS,
    TutorOrchestrator,
    SSEEventName,
    make_sse_event,
)
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.repositories.memory_repository import MemoryRepository
from app.logger import logger

MAX_WORKER_THREADS = int(os.getenv("TUTOR_MAX_THREADS", "8"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
MODEL_TIMEOUT_SECONDS = float(os.getenv("MODEL_TIMEOUT_SECONDS", "30.0"))

# Shared ThreadPoolExecutor for isolating synchronous background tasks
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


# Backward-compatible _stream_model_chunks function for existing test suites
async def _stream_model_chunks(
    model,
    prompt: str,
    generation_config: dict,
    executor: ThreadPoolExecutor,
    timeout_seconds: float,
    request: Optional[Request] = None,
) -> AsyncGenerator[str, None]:
    """Streams model response chunks without blocking the event loop."""
    is_cancelled = request.is_disconnected if request else None
    client = GeminiAIClient(model=model, executor=executor)
    async for chunk in client.stream_completion(
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        is_cancelled=is_cancelled,
    ):
        yield chunk


class AITutorService:
    """
    Modular Facade composing:
    - AI Layer: GeminiAIClient
    - Retrieval Layer: TutorRetrievalService
    - Persistence Layer: MemoryRepository
    - Application Layer: TutorOrchestrator
    """
    def __init__(
        self,
        db=None,
        executor: Optional[ThreadPoolExecutor] = None,
        model: Any = _DEFAULT_MODEL,
    ):
        self._executor = executor or get_tutor_executor()

        # 1. Resolve Persistence Layer
        if db is not None:
            resolved_db = db
        elif os.getenv("USE_PGVECTOR", "false").lower() in ("true", "1") or os.getenv("POSTGRES_URL"):
            try:
                from app.core_backend.database.pgvector_db import PGVectorManager
                resolved_db = PGVectorManager()
            except Exception as e:
                logger.warning(f"Falling back to DatabaseManager: {e}")
                resolved_db = DatabaseManager()
        else:
            resolved_db = DatabaseManager()

        self._db = resolved_db
        self.memory_repository = MemoryRepository(self._db)

        # 2. Resolve AI Layer
        self.ai_client = GeminiAIClient(model=model, executor=self._executor)

        # 3. Resolve Retrieval Layer
        self.retrieval_service = TutorRetrievalService(
            repository=self.memory_repository,
            executor=self._executor,
        )

        # 4. Resolve Concurrency & Orchestrator
        self._concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
        self.orchestrator = TutorOrchestrator(
            ai_client=self.ai_client,
            retrieval_service=self.retrieval_service,
            memory_repository=self.memory_repository,
            concurrency_semaphore=self._concurrency_semaphore,
            executor=self._executor,
        )

    @property
    def model(self) -> Any:
        return self.ai_client.model if getattr(self, "ai_client", None) else None

    @model.setter
    def model(self, val: Any):
        self.ai_client = GeminiAIClient(model=val, executor=self._executor)
        if hasattr(self, "orchestrator") and self.orchestrator:
            self.orchestrator.ai_client = self.ai_client

    @property
    def db(self) -> Any:
        return self._db

    @db.setter
    def db(self, val: Any):
        self._db = val
        self.memory_repository = MemoryRepository(val)
        if hasattr(self, "retrieval_service") and self.retrieval_service:
            self.retrieval_service._repository = self.memory_repository
        if hasattr(self, "orchestrator") and self.orchestrator:
            self.orchestrator.memory_repository = self.memory_repository

    async def generate_embedding(self, text: str) -> List[float]:
        """Delegates to Retrieval Layer embedding generation."""
        return await self.retrieval_service.generate_query_embedding(text)

    async def retrieve_memories(
        self,
        prompt: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = True,
    ):
        """Delegates hybrid memory retrieval to Retrieval Layer."""
        normalized_query = " ".join(prompt.strip().split())
        q_emb = await self.generate_embedding(normalized_query)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: self.memory_repository.search_memories(
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
        """Evaluates student answer against concept rubric and records validated mastery."""
        eval_result = await evaluate_learning_interaction(
            model=self.model,
            concept=concept,
            question=question,
            student_answer=answer,
        )

        if eval_result.is_correct and eval_result.confidence >= 0.80:
            loop = asyncio.get_running_loop()
            newly_awarded, xp = await loop.run_in_executor(
                self._executor,
                lambda: self.memory_repository.award_mastery_xp(
                    user_id=user_id,
                    concept=concept,
                    amount=100,
                ),
            )
            eval_result.mastery_awarded = newly_awarded
            eval_result.xp_awarded = xp if newly_awarded else 0
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
        """Delegates use case orchestration to TutorOrchestrator in the Application Layer."""
        prompt = getattr(req, "prompt", None) or getattr(req, "message", "")
        session_id = getattr(req, "session_id", None)
        concept = getattr(req, "concept", None)
        question = getattr(req, "question", None)

        async for event_chunk in self.orchestrator.execute_tutor_stream(
            prompt=prompt,
            user_id=user_id,
            session_id=session_id,
            concept=concept,
            question=question,
            request=request,
            last_event_id=last_event_id,
            generate_embedding_fn=self.generate_embedding,
        ):
            yield event_chunk


def __getattr__(name: str):
    """Provides lazy access to tutor_executor for backward-compatible imports."""
    if name == "tutor_executor":
        return get_tutor_executor()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
