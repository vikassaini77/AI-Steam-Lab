"""
Tutor Retrieval Service - Retrieval Layer
Problem 45: Service boundaries separation.
Problem 6: Retrieval failure observability and explicit status contract.

Encapsulates:
- Query normalization
- Embedding generation
- Ranked hybrid memory retrieval
- Explicit retrieval status reporting ('healthy', 'empty', 'degraded')
- Failure rate telemetry distinguishing embedding, DB query, DB availability, and empty results
- Non-silent degraded operation with alert triggers
"""
import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from app.ai_agent.embedding_service import generate_embedding
from app.core_backend.repositories.memory_repository import MemoryRepositoryProtocol
from app.core_backend.core.observability import alert_manager
from app.logger import logger


class RetrievalStatus:
    HEALTHY = "healthy"
    EMPTY = "empty"
    DEGRADED = "degraded"


class RetrievalReason:
    NONE = None
    NO_RELEVANT_MEMORIES = "no_relevant_memories"
    EMBEDDING_PROVIDER_TIMEOUT = "embedding_provider_timeout"
    EMBEDDING_GENERATION_FAILED = "embedding_generation_failed"
    DATABASE_QUERY_FAILED = "database_query_failed"
    DATABASE_UNAVAILABLE = "database_unavailable"
    EMPTY_QUERY = "empty_query"


class RetrievalResult(dict):
    """
    Explicit retrieval result structure encapsulating status, retrieved memories, and diagnostic reason.

    Conforms to:
    {
        "status": "degraded" | "healthy" | "empty",
        "context": List[Any],
        "reason": "embedding_provider_timeout" | "database_unavailable" | ... | None,
        "latency_ms": float
    }

    Subclasses dict for dictionary interface and JSON serialization, while
    providing convenient property access (.status, .context, .reason).
    """

    def __init__(
        self,
        status: str,
        context: Optional[List[Any]] = None,
        reason: Optional[str] = None,
        latency_ms: float = 0.0,
        **kwargs,
    ):
        ctx = context if context is not None else []
        super().__init__(
            status=status,
            context=ctx,
            reason=reason,
            latency_ms=round(float(latency_ms), 2),
            **kwargs,
        )

    @property
    def status(self) -> str:
        return self["status"]

    @property
    def context(self) -> List[Any]:
        return self["context"]

    @property
    def reason(self) -> Optional[str]:
        return self["reason"]

    @property
    def latency_ms(self) -> float:
        return self.get("latency_ms", 0.0)


class RetrievalTelemetryTracker:
    """
    Thread-safe telemetry tracker monitoring retrieval performance, failure rates,
    and distinct failure modes.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_requests = 0
            self.successful_requests = 0
            self.empty_results = 0
            self.total_failures = 0
            self.consecutive_failures = 0
            self.failures_by_reason: Dict[str, int] = {
                RetrievalReason.NO_RELEVANT_MEMORIES: 0,
                RetrievalReason.EMBEDDING_PROVIDER_TIMEOUT: 0,
                RetrievalReason.EMBEDDING_GENERATION_FAILED: 0,
                RetrievalReason.DATABASE_QUERY_FAILED: 0,
                RetrievalReason.DATABASE_UNAVAILABLE: 0,
                RetrievalReason.EMPTY_QUERY: 0,
            }
            self.last_failure: Optional[Dict[str, Any]] = None

    @property
    def failure_rate(self) -> float:
        """Returns failure rate ratio (0.0 to 1.0) excluding valid empty queries."""
        with self._lock:
            if self.total_requests == 0:
                return 0.0
            return round(self.total_failures / self.total_requests, 4)

    def record_success(self, empty: bool = False, latency_ms: float = 0.0) -> None:
        with self._lock:
            self.total_requests += 1
            self.consecutive_failures = 0
            if empty:
                self.empty_results += 1
                self.failures_by_reason[RetrievalReason.NO_RELEVANT_MEMORIES] += 1
            else:
                self.successful_requests += 1

        # Resolve persistent degradation alert if active
        try:
            if alert_manager.is_alert_active("RETRIEVAL_PERSISTENT_DEGRADATION"):
                alert_manager.resolve_alert("RETRIEVAL_PERSISTENT_DEGRADATION")
        except Exception:
            pass

    def record_failure(self, reason: str, error_message: str, latency_ms: float = 0.0) -> None:
        with self._lock:
            self.total_requests += 1
            self.total_failures += 1
            self.consecutive_failures += 1
            current_count = self.failures_by_reason.get(reason, 0)
            self.failures_by_reason[reason] = current_count + 1
            self.last_failure = {
                "reason": reason,
                "error": error_message,
                "timestamp": time.time(),
                "latency_ms": latency_ms,
            }
            consecutive = self.consecutive_failures
            rate = round(self.total_failures / self.total_requests, 4)

        # Trigger observability alerts for severe conditions
        try:
            if reason == RetrievalReason.DATABASE_UNAVAILABLE:
                alert_manager.trigger_alert(
                    alert_name="RETRIEVAL_DATABASE_UNAVAILABLE",
                    severity="CRITICAL",
                    message=f"Database backend is unavailable for memory retrieval: {error_message}",
                    metadata={"reason": reason, "error": error_message},
                )
            elif consecutive >= 3 or rate >= 0.5:
                alert_manager.trigger_alert(
                    alert_name="RETRIEVAL_PERSISTENT_DEGRADATION",
                    severity="WARNING",
                    message=(
                        f"Memory retrieval persistent degradation detected: {consecutive} consecutive failures "
                        f"(failure rate: {rate * 100:.1f}%). Latest reason: {reason}"
                    ),
                    metadata={"reason": reason, "consecutive_failures": consecutive, "failure_rate": rate},
                )
        except Exception:
            pass

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "empty_results": self.empty_results,
                "total_failures": self.total_failures,
                "consecutive_failures": self.consecutive_failures,
                "failure_rate": round(self.total_failures / max(1, self.total_requests), 4) if self.total_requests else 0.0,
                "failures_by_reason": dict(self.failures_by_reason),
                "last_failure": dict(self.last_failure) if self.last_failure else None,
            }


retrieval_telemetry = RetrievalTelemetryTracker()


def get_retrieval_telemetry() -> RetrievalTelemetryTracker:
    return retrieval_telemetry


def reset_retrieval_telemetry() -> None:
    retrieval_telemetry.reset()


@runtime_checkable
class RetrievalProtocol(Protocol):
    """Protocol defining the retrieval layer contract for semantic search."""

    async def generate_query_embedding(self, text: str) -> List[float]:
        ...

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        top_k: int = 3,
        embedding_fn: Optional[Any] = None,
    ) -> Union[RetrievalResult, Dict[str, Any], List[Any]]:
        ...


class TutorRetrievalService:
    """
    Production implementation of the Retrieval Layer for AI Tutor interactions.
    Coordinates embedding generation and hybrid ranked retrieval via MemoryRepository.
    Enforces explicit retrieval status contracts and failure categorization.
    """

    def __init__(
        self,
        repository: MemoryRepositoryProtocol,
        executor: Optional[ThreadPoolExecutor] = None,
        telemetry: Optional[RetrievalTelemetryTracker] = None,
    ):
        self._repository = repository
        self._executor = executor
        self.telemetry = telemetry or retrieval_telemetry

    async def generate_query_embedding(self, text: str) -> List[float]:
        """Generates real 768-dimensional normalized semantic query embedding."""
        return await generate_embedding(text)

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        top_k: int = 3,
        embedding_fn: Optional[Any] = None,
    ) -> RetrievalResult:
        """
        Executes hybrid ranked retrieval (combining vector similarity and keyword search).
        Returns an explicit RetrievalResult dictionary with status and diagnostic reason:
        - status='healthy': memories retrieved successfully.
        - status='empty': query was valid, but no relevant memories exist (reason='no_relevant_memories').
        - status='degraded': retrieval failed gracefully (reason='embedding_generation_failed',
          'embedding_provider_timeout', 'database_query_failed', or 'database_unavailable').
        """
        start_time = time.perf_counter()
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return RetrievalResult(
                status=RetrievalStatus.EMPTY,
                context=[],
                reason=RetrievalReason.EMPTY_QUERY,
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Phase 1: Embedding generation
        try:
            emb_gen = embedding_fn or self.generate_query_embedding
            q_emb = await emb_gen(normalized_query)
        except (asyncio.TimeoutError, TimeoutError) as timeout_err:
            latency_ms = (time.perf_counter() - start_time) * 1000
            reason = RetrievalReason.EMBEDDING_PROVIDER_TIMEOUT
            logger.warning(
                f"TutorRetrievalService degraded mode ({reason}): {timeout_err}. Proceeding without past context.",
                extra={"user_id": user_id, "reason": reason, "event": "retrieval_embedding_timeout"},
            )
            self.telemetry.record_failure(reason, str(timeout_err), latency_ms)
            return RetrievalResult(
                status=RetrievalStatus.DEGRADED,
                context=[],
                reason=reason,
                latency_ms=latency_ms,
            )
        except Exception as emb_err:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_str = str(emb_err).lower()
            if "timeout" in err_str:
                reason = RetrievalReason.EMBEDDING_PROVIDER_TIMEOUT
            else:
                reason = RetrievalReason.EMBEDDING_GENERATION_FAILED

            logger.warning(
                f"TutorRetrievalService degraded mode ({reason}): {emb_err}. Proceeding without past context.",
                extra={"user_id": user_id, "reason": reason, "event": "retrieval_embedding_failure"},
            )
            self.telemetry.record_failure(reason, str(emb_err), latency_ms)
            return RetrievalResult(
                status=RetrievalStatus.DEGRADED,
                context=[],
                reason=reason,
                latency_ms=latency_ms,
            )

        # Phase 2: Database query execution
        try:
            loop = asyncio.get_running_loop()
            raw_results = await loop.run_in_executor(
                self._executor,
                lambda: self._repository.search_memories(
                    query_embedding=q_emb,
                    query_text=normalized_query,
                    user_id=user_id,
                    session_id=session_id,
                    top_k=top_k,
                ),
            )
        except Exception as db_err:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_type = type(db_err).__name__
            err_str = str(db_err).lower()

            # Distinguish database unavailable vs query execution error
            unavailable_markers = [
                "connection refused",
                "could not connect",
                "database unavailable",
                "connection closed",
                "connection reset",
                "cannot connect",
                "server closed the connection",
                "connection to server",
                "pool timeout",
                "host unreachable",
                "network is unreachable",
                "noserveravailable",
            ]
            if (
                any(marker in err_str for marker in unavailable_markers)
                or "connect" in err_type.lower()
                or "operationalerror" in err_type.lower()
            ):
                reason = RetrievalReason.DATABASE_UNAVAILABLE
            else:
                reason = RetrievalReason.DATABASE_QUERY_FAILED

            logger.warning(
                f"TutorRetrievalService degraded mode ({reason} - {err_type}): {db_err}. Proceeding without past context.",
                extra={"user_id": user_id, "reason": reason, "event": "retrieval_db_failure"},
            )
            self.telemetry.record_failure(reason, str(db_err), latency_ms)
            return RetrievalResult(
                status=RetrievalStatus.DEGRADED,
                context=[],
                reason=reason,
                latency_ms=latency_ms,
            )

        # Phase 3: Evaluate returned results
        latency_ms = (time.perf_counter() - start_time) * 1000
        if not raw_results:
            self.telemetry.record_success(empty=True, latency_ms=latency_ms)
            return RetrievalResult(
                status=RetrievalStatus.EMPTY,
                context=[],
                reason=RetrievalReason.NO_RELEVANT_MEMORIES,
                latency_ms=latency_ms,
            )

        self.telemetry.record_success(empty=False, latency_ms=latency_ms)
        return RetrievalResult(
            status=RetrievalStatus.HEALTHY,
            context=raw_results,
            reason=RetrievalReason.NONE,
            latency_ms=latency_ms,
        )
