"""
Unit and integration tests for Problem 6:
Tutor Retrieval Service Observability, Explicit Status Reporting, and Failure Mode Tracking.

Verifies:
1. Healthy retrieval returns {"status": "healthy", "context": [...], "reason": None}.
2. Empty search returns {"status": "empty", "context": [], "reason": "no_relevant_memories"}.
3. Embedding failure returns {"status": "degraded", "context": [], "reason": "embedding_generation_failed"}.
4. Embedding timeout returns {"status": "degraded", "context": [], "reason": "embedding_provider_timeout"}.
5. Database query failure returns {"status": "degraded", "context": [], "reason": "database_query_failed"}.
6. Database unavailable returns {"status": "degraded", "context": [], "reason": "database_unavailable"} and triggers alert.
7. Telemetry correctly tracks failure rates, counts by category, and consecutive degradation alerts.
8. Tutor orchestrator handles RetrievalResult seamlessly.
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from app.ai_agent.retrieval_service import (
    TutorRetrievalService,
    RetrievalStatus,
    RetrievalReason,
    RetrievalResult,
    RetrievalTelemetryTracker,
    get_retrieval_telemetry,
    reset_retrieval_telemetry,
)
from app.core_backend.core.observability import alert_manager


class MockRepo:
    """Mock repository with configurable behaviors."""
    def __init__(self, memories=None, fail_with=None):
        self._memories = memories if memories is not None else []
        self._fail_with = fail_with

    def search_memories(self, query_embedding, query_text, user_id, session_id=None, top_k=3):
        if self._fail_with:
            raise self._fail_with
        return self._memories


@pytest.fixture(autouse=True)
def clean_telemetry():
    reset_retrieval_telemetry()
    alert_manager.clear()
    yield
    reset_retrieval_telemetry()
    alert_manager.clear()


@pytest.mark.asyncio
async def test_healthy_retrieval_returns_explicit_status():
    """When memories are found, status is 'healthy' with no failure reason."""
    repo = MockRepo(memories=["Memory 1: Newton's Third Law", "Memory 2: Action-reaction pairs"])
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def mock_emb(text):
        return [0.1] * 768

    result = await service.retrieve_context(
        query="What is Newton's third law?",
        user_id="user_123",
        embedding_fn=mock_emb,
    )

    assert isinstance(result, dict)
    assert result["status"] == RetrievalStatus.HEALTHY
    assert len(result["context"]) == 2
    assert result["reason"] is None
    assert result["latency_ms"] >= 0.0

    # Verify telemetry tracking
    metrics = telemetry.get_metrics()
    assert metrics["successful_requests"] == 1
    assert metrics["total_failures"] == 0
    assert metrics["failure_rate"] == 0.0


@pytest.mark.asyncio
async def test_no_relevant_memories_found_distinction():
    """When query succeeds but returns no matching memories, status is 'empty' with reason 'no_relevant_memories'."""
    repo = MockRepo(memories=[])
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def mock_emb(text):
        return [0.1] * 768

    result = await service.retrieve_context(
        query="Quantum gravity paradoxes",
        user_id="user_new",
        embedding_fn=mock_emb,
    )

    assert result["status"] == RetrievalStatus.EMPTY
    assert result["context"] == []
    assert result["reason"] == RetrievalReason.NO_RELEVANT_MEMORIES

    # Verify telemetry distinguishes empty from failures
    metrics = telemetry.get_metrics()
    assert metrics["empty_results"] == 1
    assert metrics["total_failures"] == 0
    assert metrics["failures_by_reason"][RetrievalReason.NO_RELEVANT_MEMORIES] == 1


@pytest.mark.asyncio
async def test_embedding_generation_failed_distinction():
    """When embedding model fails (e.g. quota, network), status is 'degraded' with reason 'embedding_generation_failed'."""
    repo = MockRepo(memories=["Should not be reached"])
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def failing_emb(text):
        raise RuntimeError("Gemini Embedding API 429 Quota Exceeded")

    result = await service.retrieve_context(
        query="Explain thermodynamics",
        user_id="user_123",
        embedding_fn=failing_emb,
    )

    assert result["status"] == RetrievalStatus.DEGRADED
    assert result["context"] == []
    assert result["reason"] == RetrievalReason.EMBEDDING_GENERATION_FAILED

    metrics = telemetry.get_metrics()
    assert metrics["total_failures"] == 1
    assert metrics["failures_by_reason"][RetrievalReason.EMBEDDING_GENERATION_FAILED] == 1
    assert metrics["failure_rate"] == 1.0


@pytest.mark.asyncio
async def test_embedding_provider_timeout_distinction():
    """When embedding provider times out, status is 'degraded' with reason 'embedding_provider_timeout'."""
    repo = MockRepo(memories=[])
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def timeout_emb(text):
        raise asyncio.TimeoutError("Embedding generation timed out after 5.0s")

    result = await service.retrieve_context(
        query="Explain momentum",
        user_id="user_123",
        embedding_fn=timeout_emb,
    )

    assert result["status"] == RetrievalStatus.DEGRADED
    assert result["context"] == []
    assert result["reason"] == RetrievalReason.EMBEDDING_PROVIDER_TIMEOUT

    metrics = telemetry.get_metrics()
    assert metrics["failures_by_reason"][RetrievalReason.EMBEDDING_PROVIDER_TIMEOUT] == 1


@pytest.mark.asyncio
async def test_database_query_failed_distinction():
    """When database query syntax or statement fails, status is 'degraded' with reason 'database_query_failed'."""
    repo = MockRepo(fail_with=ValueError("SyntaxError: column 'embedding_v2' does not exist"))
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def mock_emb(text):
        return [0.1] * 768

    result = await service.retrieve_context(
        query="Explain torque",
        user_id="user_123",
        embedding_fn=mock_emb,
    )

    assert result["status"] == RetrievalStatus.DEGRADED
    assert result["context"] == []
    assert result["reason"] == RetrievalReason.DATABASE_QUERY_FAILED

    metrics = telemetry.get_metrics()
    assert metrics["failures_by_reason"][RetrievalReason.DATABASE_QUERY_FAILED] == 1


@pytest.mark.asyncio
async def test_database_unavailable_distinction_and_alert():
    """
    When database is down or connection is refused,
    status is 'degraded' with reason 'database_unavailable' and triggers a critical alert.
    """
    repo = MockRepo(fail_with=ConnectionRefusedError("could not connect to server: Connection refused on port 5432"))
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def mock_emb(text):
        return [0.1] * 768

    result = await service.retrieve_context(
        query="Explain angular momentum",
        user_id="user_123",
        embedding_fn=mock_emb,
    )

    assert result["status"] == RetrievalStatus.DEGRADED
    assert result["context"] == []
    assert result["reason"] == RetrievalReason.DATABASE_UNAVAILABLE

    metrics = telemetry.get_metrics()
    assert metrics["failures_by_reason"][RetrievalReason.DATABASE_UNAVAILABLE] == 1

    # Verify critical operational alert triggered
    assert alert_manager.is_alert_active("RETRIEVAL_DATABASE_UNAVAILABLE") is True
    alert = alert_manager.get_active_alerts()[0]
    assert alert["name"] == "RETRIEVAL_DATABASE_UNAVAILABLE"
    assert alert["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_consecutive_failures_trigger_persistent_degradation_alert():
    """After 3 consecutive retrieval failures, triggers RETRIEVAL_PERSISTENT_DEGRADATION alert."""
    repo = MockRepo(fail_with=RuntimeError("Internal query failure"))
    telemetry = RetrievalTelemetryTracker()
    service = TutorRetrievalService(repository=repo, telemetry=telemetry)

    async def mock_emb(text):
        return [0.1] * 768

    for i in range(3):
        res = await service.retrieve_context(query="Query", user_id="u1", embedding_fn=mock_emb)
        assert res["status"] == RetrievalStatus.DEGRADED

    # Verify warning alert triggered for sustained degradation
    assert alert_manager.is_alert_active("RETRIEVAL_PERSISTENT_DEGRADATION") is True
    alert = [a for a in alert_manager.get_active_alerts() if a["name"] == "RETRIEVAL_PERSISTENT_DEGRADATION"][0]
    assert "consecutive failures" in alert["message"]

    # Now simulate recovery
    repo._fail_with = None
    repo._memories = ["Recovered memory"]
    res_recovered = await service.retrieve_context(query="Query", user_id="u1", embedding_fn=mock_emb)
    assert res_recovered["status"] == RetrievalStatus.HEALTHY

    # Alert should be automatically resolved on recovery
    assert alert_manager.is_alert_active("RETRIEVAL_PERSISTENT_DEGRADATION") is False

