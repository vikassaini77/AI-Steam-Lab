"""
Centralized Dependency Policies and Degradation Protocol for NeuroLab AI
Problem 30: Clearly separates essential services from optional dependencies.

Dependency Matrix & Policies:
--------------------------------------------------------------------------------------
Dependency          Criticality              Recommended Policy & Failure Behavior
--------------------------------------------------------------------------------------
PostgreSQL          REQUIRED                 Required for durable writes, XP ledger, and
                                             private experiment history. Must fail fast with
                                             HTTP 503 (DatabasePersistenceError). Never pretend
                                             writes succeeded or leak cross-user state.

Redis Cache         OPTIONAL                 Optional for cache reads. Degrades performance safely
                                             to local in-memory cache fallback. Telemetry records
                                             degradation. Core endpoints continue with HTTP 200.

Redis Task Broker   REQUIRED (when enabled)  Required when asynchronous tasks are enabled
                                             (ASYNC_TASKS_ENABLED=true). Task enqueueing fails
                                             with TaskBrokerUnavailableError (HTTP 503) if
                                             broker is unreachable. Never silently drops tasks.

Gemini API          REQUIRED                 Required for AI tutor model generation. Fails
                                             gracefully by emitting explicit MODEL_UNAVAILABLE or
                                             MODEL_TIMEOUT SSE events. Never crashes or hangs server.

Embedding Service   REQUIRED                 Required for semantic vector retrieval. Strictly
                                             rejects fake constant [0.1]*768 or random vector
                                             fallbacks. Degrades retrieval to keyword search only.

Sentry              OPTIONAL                 Optional for core operations. Failures during
                                             initialization or event reporting are captured,
                                             logged as observable warnings, and do not affect
                                             application uptime.
--------------------------------------------------------------------------------------
"""
import os
import time
from enum import Enum
from typing import Dict, Any, Optional

from app.logger import logger


class DependencyCriticality(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    REQUIRED_WHEN_ENABLED = "required_when_enabled"


class DependencyHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"
    UNCONFIGURED = "unconfigured"


DEPENDENCY_POLICIES = {
    "postgresql": {
        "name": "PostgreSQL (pgvector)",
        "criticality": DependencyCriticality.REQUIRED.value,
        "description": "Required for durable writes, XP ledger, and private experiment history",
        "failure_behavior": "Must fail fast with HTTP 503 (DatabasePersistenceError). Never pretend writes succeeded or leak state across users.",
        "fallback": "None for durable writes. In-memory fallback permitted strictly in local development/test mode with explicit warnings.",
    },
    "redis_cache": {
        "name": "Redis Cache",
        "criticality": DependencyCriticality.OPTIONAL.value,
        "description": "Optional for cache reads; degrade performance safely with in-memory fallback",
        "failure_behavior": "Log structured warning, record telemetry, and fall back to local in-memory store. Main endpoints continue normally.",
        "fallback": "Local in-memory TTL cache fallback.",
    },
    "redis_task_broker": {
        "name": "Redis Task Broker (Celery)",
        "criticality": DependencyCriticality.REQUIRED_WHEN_ENABLED.value,
        "description": "Required when asynchronous tasks are enabled",
        "failure_behavior": "Fail task dispatch explicitly with TaskBrokerUnavailableError (HTTP 503). Never silently drop tasks or lose jobs.",
        "fallback": "Synchronous execution when async tasks disabled; explicit error when async enabled.",
    },
    "gemini_api": {
        "name": "Google Gemini API",
        "criticality": DependencyCriticality.REQUIRED.value,
        "description": "Required for model generation; fail gracefully",
        "failure_behavior": "Emit explicit MODEL_UNAVAILABLE/MODEL_TIMEOUT SSE event without crashing or hanging the server.",
        "fallback": "Structured SSE error event with safe user-facing message and administrative diagnostic code.",
    },
    "embedding_service": {
        "name": "Embedding Service (Gemini/pgvector)",
        "criticality": DependencyCriticality.REQUIRED.value,
        "description": "Required for semantic retrieval; no fake-vector fallback",
        "failure_behavior": "Raise EmbeddingError if API key missing or provider fails. Never generate fake constant or random vectors. Degrade to keyword-only search.",
        "fallback": "Degrade hybrid retrieval to keyword-only search without generating fake vectors.",
    },
    "sentry": {
        "name": "Sentry APM & Error Tracking",
        "criticality": DependencyCriticality.OPTIONAL.value,
        "description": "Optional for core functionality, but failures should be observable",
        "failure_behavior": "Log observable warning if initialization or event capture fails. Application startup and operations continue unaffected.",
        "fallback": "Standard structured JSON application logs.",
    },
}


async def get_system_dependency_health() -> Dict[str, Any]:
    """
    Executes a comprehensive health evaluation across all service dependencies,
    applying explicit criticality and fallback policies.
    """
    dependencies: Dict[str, Any] = {}

    # 1. PostgreSQL (REQUIRED)
    from app.core_backend.database.pgvector_db import check_database_readiness
    db_status = check_database_readiness()
    pg_healthy = db_status.get("status") in ("ready", "healthy")
    pg_degraded = db_status.get("status") == "degraded"
    dependencies["postgresql"] = {
        **DEPENDENCY_POLICIES["postgresql"],
        "status": "healthy" if pg_healthy else ("degraded" if pg_degraded else "unhealthy"),
        "details": db_status,
    }

    # 2. Redis Cache (OPTIONAL)
    from app.cache import check_redis_cache_health
    cache_status = await check_redis_cache_health()
    dependencies["redis_cache"] = {
        **DEPENDENCY_POLICIES["redis_cache"],
        "status": cache_status.get("status", "degraded"),
        "details": cache_status,
    }

    # 3. Redis Task Broker (REQUIRED WHEN ENABLED)
    from app.worker import check_broker_health
    broker_status = check_broker_health()
    dependencies["redis_task_broker"] = {
        **DEPENDENCY_POLICIES["redis_task_broker"],
        "status": broker_status.get("status", "disabled"),
        "details": broker_status,
    }

    # 4. Gemini API (REQUIRED)
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_healthy = bool(gemini_key and gemini_key != "unconfigured")
    dependencies["gemini_api"] = {
        **DEPENDENCY_POLICIES["gemini_api"],
        "status": "healthy" if gemini_healthy else "unconfigured",
        "details": {
            "configured": bool(gemini_key),
            "model": "gemini-2.5-flash",
        },
    }

    # 5. Embedding Service (REQUIRED, NO FAKE VECTORS)
    from app.ai_agent.embedding_service import DEFAULT_EMBEDDING_MODEL, EXPECTED_EMBEDDING_DIM
    dependencies["embedding_service"] = {
        **DEPENDENCY_POLICIES["embedding_service"],
        "status": "healthy" if gemini_healthy else "unconfigured",
        "details": {
            "configured": bool(gemini_key),
            "model": DEFAULT_EMBEDDING_MODEL,
            "dimension": EXPECTED_EMBEDDING_DIM,
            "fake_vector_fallback_enabled": False,  # Strictly forbidden
        },
    }

    # 6. Sentry (OPTIONAL)
    sentry_dsn = os.getenv("SENTRY_DSN")
    from app.main import SENTRY_STATUS
    dependencies["sentry"] = {
        **DEPENDENCY_POLICIES["sentry"],
        "status": "healthy" if SENTRY_STATUS.get("initialized") else ("disabled" if not sentry_dsn else "degraded"),
        "details": SENTRY_STATUS,
    }

    # Determine overall system health
    # If any REQUIRED dependency is UNHEALTHY -> overall is UNHEALTHY
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    is_pg_unhealthy = dependencies["postgresql"]["status"] == "unhealthy"
    is_broker_unhealthy = dependencies["redis_task_broker"]["status"] == "unhealthy"

    if is_pg_unhealthy or is_broker_unhealthy:
        overall = "unhealthy"
    elif not gemini_healthy and is_prod:
        overall = "unhealthy"
    elif dependencies["redis_cache"]["status"] == "degraded" or dependencies["postgresql"]["status"] == "degraded" or not gemini_healthy:
        overall = "degraded"
    else:
        overall = "ready"

    return {
        "status": overall,
        "timestamp": time.time(),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "dependencies": dependencies,
    }

