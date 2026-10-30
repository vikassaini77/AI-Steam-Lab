"""
Test Suite for Problem 30: Service Dependencies and Fallback Separation
Validates explicit dependency policies and independent outage degradation:
1. PostgreSQL (REQUIRED): Durable writes and private history fail with 503; never fake persistence.
2. Redis Cache (OPTIONAL): Fails safely to local memory cache; logs warning; endpoints stay 200.
3. Redis Task Broker (REQUIRED WHEN ENABLED): Fails task dispatch with TaskBrokerUnavailableError when async enabled.
4. Gemini API (REQUIRED): Fails gracefully via SSE error event without crashing server.
5. Embedding Service (REQUIRED): Strictly rejects fake-vector fallbacks ([0.1]*768); raises EmbeddingError.
6. Sentry (OPTIONAL): Observable warning on initialization failure; application operates normally.
7. Centralized Dependency Diagnostics: GET /api/dependencies exposes policies and health matrix.
"""
import asyncio
import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.dependency_policies import (
    DEPENDENCY_POLICIES,
    DependencyCriticality,
    get_system_dependency_health,
)
from app.cache import (
    get_cache,
    set_cache,
    delete_cache,
    check_redis_cache_health,
    clear_local_cache,
    CACHE_METRICS,
)
from app.worker import (
    dispatch_async_task,
    check_broker_health,
    TaskBrokerUnavailableError,
    process_heavy_cv_frame,
)
from app.ai_agent.embedding_service import (
    generate_embedding,
    EmbeddingError,
    is_placeholder_embedding,
)
from app.core_backend.database.pgvector_db import (
    DatabasePersistenceError,
    DatabaseConnectionError,
    PGVectorManager,
    DatabaseMode,
)

client = TestClient(app)

TEST_USER = {
    "id": "dep_test_user_01",
    "email": "dep_tester@neurolab.ai",
    "role": "authenticated",
}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_dependencies"}


@pytest.fixture(autouse=True)
def setup_auth_and_cache():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    clear_local_cache()
    yield
    app.dependency_overrides.clear()
    clear_local_cache()


# ==============================================================================
# 1. Dependency Policies Registry & Diagnostic Endpoint Tests
# ==============================================================================

def test_dependency_policies_matrix_is_explicit():
    """All 6 core service dependencies have explicitly documented policies and criticalities."""
    expected_deps = [
        "postgresql",
        "redis_cache",
        "redis_task_broker",
        "gemini_api",
        "embedding_service",
        "sentry",
    ]
    for dep in expected_deps:
        assert dep in DEPENDENCY_POLICIES
        policy = DEPENDENCY_POLICIES[dep]
        assert "criticality" in policy
        assert "description" in policy
        assert "failure_behavior" in policy

    assert DEPENDENCY_POLICIES["postgresql"]["criticality"] == DependencyCriticality.REQUIRED.value
    assert DEPENDENCY_POLICIES["redis_cache"]["criticality"] == DependencyCriticality.OPTIONAL.value
    assert DEPENDENCY_POLICIES["redis_task_broker"]["criticality"] == DependencyCriticality.REQUIRED_WHEN_ENABLED.value
    assert DEPENDENCY_POLICIES["gemini_api"]["criticality"] == DependencyCriticality.REQUIRED.value
    assert DEPENDENCY_POLICIES["embedding_service"]["criticality"] == DependencyCriticality.REQUIRED.value
    assert DEPENDENCY_POLICIES["sentry"]["criticality"] == DependencyCriticality.OPTIONAL.value


def test_api_dependencies_diagnostic_endpoint():
    """GET /api/dependencies returns live status across all 6 dependencies."""
    res = client.get("/api/dependencies")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "dependencies" in data

    deps = data["dependencies"]
    assert "postgresql" in deps
    assert "redis_cache" in deps
    assert "redis_task_broker" in deps
    assert "gemini_api" in deps
    assert "embedding_service" in deps
    assert "sentry" in deps

    # Alias check /api/system/dependencies
    res_alias = client.get("/api/system/dependencies")
    assert res_alias.status_code == 200
    assert res_alias.json()["status"] == data["status"]


# ==============================================================================
# 2. PostgreSQL Outage Tests (REQUIRED Policy)
# ==============================================================================

def test_postgresql_outage_durable_writes_fail_with_503(monkeypatch):
    """
    PostgreSQL is REQUIRED for durable writes.
    When PostgreSQL is unreachable, writes must fail with 503 and never pretend success.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    mock_db = MagicMock()
    mock_db.save_experiment.side_effect = DatabasePersistenceError("PostgreSQL connection refused")
    mock_db.record_xp_event.side_effect = DatabasePersistenceError("PostgreSQL connection refused")
    mock_db.delete_user_memories.side_effect = DatabasePersistenceError("PostgreSQL connection refused")

    from app.core_backend.routes import experiments as exp_route
    from app.core_backend.routes import gamification as gam_route
    from app.core_backend.routes import tutor as tutor_route

    monkeypatch.setattr(exp_route, "db", mock_db)
    monkeypatch.setattr(gam_route, "db", mock_db)
    monkeypatch.setattr(tutor_route, "db", mock_db)

    # 1. Experiment save fails with 503
    payload = {"type": "free_fall", "height": 50.0}
    res_exp = client.post("/api/experiments/save", json=payload, headers=AUTH_HEADERS)
    assert res_exp.status_code == 503
    assert "Database persistence unavailable" in res_exp.json()["detail"]

    # 2. XP award fails with 503
    res_xp = client.post("/api/gamification/add-xp", json={"amount": 50, "action": "quiz"}, headers=AUTH_HEADERS)
    assert res_xp.status_code == 503
    assert "Database persistence unavailable" in res_xp.json()["detail"]

    # 3. Memory deletion fails with 503
    res_mem = client.delete("/api/tutor/memories", headers=AUTH_HEADERS)
    assert res_mem.status_code == 503
    assert "Database persistence unavailable" in res_mem.json()["detail"]


def test_postgresql_outage_readiness_probe_returns_503(monkeypatch):
    """When PostgreSQL is down in production, /ready returns 503 unhealthy."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pwd@db:5432/neurolab")

    from app.core_backend.database import pgvector_db
    monkeypatch.setattr(
        pgvector_db,
        "check_database_readiness",
        lambda: {"status": "unhealthy", "connected": False, "error": "Connection refused to db:5432"},
    )

    res = client.get("/ready")
    assert res.status_code == 503
    assert res.json()["status"] == "unhealthy"


# ==============================================================================
# 3. Redis Cache Outage Tests (OPTIONAL Policy)
# ==============================================================================

@pytest.mark.asyncio
async def test_redis_cache_outage_degrades_safely_to_memory(monkeypatch):
    """
    Redis Cache is OPTIONAL.
    When Redis raises connection errors, cache operations fall back to memory,
    record telemetry, log a warning, and do not raise unhandled exceptions.
    """
    mock_redis = MagicMock()

    async def mock_failing_get(key):
        raise ConnectionRefusedError("Redis connection refused on localhost:6379")

    async def mock_failing_set(key, val, ex=None):
        raise ConnectionRefusedError("Redis connection refused on localhost:6379")

    mock_redis.get = mock_failing_get
    mock_redis.set = mock_failing_set
    mock_redis.ping = mock_failing_get

    import app.cache as cache_module
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: mock_redis)

    # 1. Write during Redis outage succeeds by storing in memory fallback
    write_res = await set_cache("student_exp_cache", {"velocity": 12.5}, ttl_seconds=60)
    assert write_res is True
    assert CACHE_METRICS["redis_errors"] >= 1
    assert CACHE_METRICS["degraded_mode"] is True

    # 2. Read during Redis outage falls back to local memory without crashing
    cached_val = await get_cache("student_exp_cache")
    assert cached_val == {"velocity": 12.5}
    assert CACHE_METRICS["memory_fallback_hits"] >= 1

    # 3. Health check correctly reports degraded mode instead of crashing
    health = await check_redis_cache_health()
    assert health["status"] == "degraded"
    assert health["connected"] is False
    assert health["criticality"] == "optional"


def test_redis_cache_outage_does_not_break_api_endpoints(monkeypatch):
    """Core HTTP API endpoints remain functional (200 OK) when Redis is completely down."""
    mock_redis = MagicMock()

    async def mock_failing_call(*args, **kwargs):
        raise ConnectionRefusedError("Redis is offline")

    mock_redis.get = mock_failing_call
    mock_redis.set = mock_failing_call

    import app.cache as cache_module
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: mock_redis)

    # Check that CV readiness still returns 200
    res_cv = client.get("/api/cv/readiness")
    assert res_cv.status_code == 200

    # Check that tutor status returns 200
    res_tutor = client.get("/api/tutor/")
    assert res_tutor.status_code == 200


# ==============================================================================
# 4. Redis Task Broker Outage Tests (REQUIRED WHEN ENABLED Policy)
# ==============================================================================

def test_redis_task_broker_outage_raises_when_async_enabled(monkeypatch):
    """
    When ASYNC_TASKS_ENABLED=true, Redis task broker is strictly REQUIRED.
    If the broker is unreachable, task dispatch raises TaskBrokerUnavailableError.
    """
    monkeypatch.setenv("ASYNC_TASKS_ENABLED", "true")

    import app.worker as worker_module
    monkeypatch.setattr(
        worker_module,
        "check_broker_health",
        lambda: {"status": "unhealthy", "connected": False, "error": "Redis broker unreachable on port 6379"},
    )

    with pytest.raises(TaskBrokerUnavailableError) as exc_info:
        dispatch_async_task(process_heavy_cv_frame, {"frame_id": 101})

    assert "Redis task broker is required when asynchronous tasks are enabled" in str(exc_info.value)


def test_redis_task_broker_executes_inline_when_async_disabled(monkeypatch):
    """When ASYNC_TASKS_ENABLED=false, tasks execute synchronously without requiring the broker."""
    monkeypatch.setenv("ASYNC_TASKS_ENABLED", "false")

    def sample_task(data):
        return {"result": f"processed_{data['id']}"}

    res = dispatch_async_task(sample_task, {"id": "sync_99"})
    assert res == {"result": "processed_sync_99"}


# ==============================================================================
# 5. Gemini API Outage Tests (REQUIRED Policy)
# ==============================================================================

def test_gemini_api_outage_fails_gracefully_via_sse(monkeypatch):
    """
    Gemini API is REQUIRED for model generation.
    When the model is unconfigured (missing API key) or unavailable,
    it must fail gracefully by streaming a structured SSE error event without hanging.
    """
    from app.core_backend.routes import tutor as tutor_module
    # Simulate unconfigured model
    mock_tutor = tutor_module.get_tutor_service()
    monkeypatch.setattr(mock_tutor, "model", None)

    res = client.post("/api/tutor/chat/stream", json={"prompt": "Explain gravity"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    # Response stream must contain the structured error event
    assert "MODEL_UNCONFIGURED" in res.text
    assert "The tutor is temporarily unavailable." in res.text


# ==============================================================================
# 6. Embedding Service Outage Tests (REQUIRED, NO FAKE VECTORS Policy)
# ==============================================================================

@pytest.mark.asyncio
async def test_embedding_service_outage_fails_without_fake_vectors(monkeypatch):
    """
    Embedding service is REQUIRED for semantic retrieval.
    It must strictly fail with EmbeddingError and NEVER generate fake constant [0.1]*768 vectors.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(EmbeddingError) as exc_info:
        await generate_embedding("What is gravity?")

    assert "GEMINI_API_KEY is missing" in str(exc_info.value)

    # Verify placeholder detector correctly identifies fake constant vectors
    fake_vector = [0.1] * 768
    assert is_placeholder_embedding(fake_vector) is True

    fake_zeros = [0.0] * 768
    assert is_placeholder_embedding(fake_zeros) is True


# ==============================================================================
# 7. Sentry Outage Tests (OPTIONAL Policy)
# ==============================================================================

def test_sentry_outage_allows_normal_application_operation():
    """
    Sentry is OPTIONAL for core functionality.
    Sentry initialization failure or invalid DSN is observable but does not impact application uptime.
    """
    from app.main import SENTRY_STATUS

    # Even if Sentry is unconfigured or failed, core routes return 200
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Dependency diagnostic exposes observable Sentry state
    res_deps = client.get("/api/dependencies")
    assert res_deps.status_code == 200
    sentry_info = res_deps.json()["dependencies"]["sentry"]
    assert sentry_info["criticality"] == "optional"
    assert "status" in sentry_info

