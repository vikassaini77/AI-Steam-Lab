"""
Centralized Liveness and Readiness Health Probes for NeuroLab AI
Problem 35: Separates Liveness (process responsiveness) from Readiness (workload serving capability).

Concepts:
- Liveness (/live, /healthz):
  Is the application process alive and responsive?
  Fast in-process check. Does NOT depend on external upstream dependencies (e.g. Gemini, PostgreSQL).
  Crucial: An upstream database outage or Gemini blip must never fail liveness, preventing
  endless container restart loops and restart storms.

- Readiness (/ready, /health/ready):
  Can this instance serve its required workload?
  Validates essential dependencies (PostgreSQL database connectivity, schema version,
  task broker when async enabled, model provider configuration) using short timeouts.
  In production, if essential persistence is unreachable, returns HTTP 503.
"""
import os
import time
from typing import Dict, Any, Optional

from app.logger import logger

PROCESS_START_TIME = time.time()


def check_liveness() -> Dict[str, Any]:
    """
    Liveness probe: verifies process responsiveness without querying external dependencies.
    Used by orchestrators (Kubernetes, Render, Docker) to detect deadlocks without triggering
    restart storms during third-party or database outages.
    """
    uptime = round(time.time() - PROCESS_START_TIME, 2)
    return {
        "status": "alive",
        "process": "responsive",
        "pid": os.getpid(),
        "uptime_seconds": uptime,
        "timestamp": time.time(),
    }


def check_readiness(timeout_seconds: float = 1.0) -> Dict[str, Any]:
    """
    Readiness probe: validates whether this instance can serve its required workload.
    Checks essential dependencies (PostgreSQL database, model provider, and task broker)
    using bounded short timeouts.

    Returns:
        Dict containing overall status ('ready' | 'degraded' | 'unhealthy'),
        database readiness telemetry, model provider configuration, and task broker health.
    """
    from app.core_backend.database import pgvector_db
    from app.worker import check_broker_health

    # 1. Database readiness check with short timeout
    try:
        db_readiness = pgvector_db.check_database_readiness(timeout=timeout_seconds)
    except TypeError:
        # Fallback for mock callables that do not accept kwargs
        db_readiness = pgvector_db.check_database_readiness()
    except Exception as e:
        logger.warning(f"Database readiness check exception: {e}")
        db_readiness = {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
            "metrics": {},
        }

    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
    db_status = db_readiness.get("status", "unhealthy")

    # 2. Model provider (Gemini API) configuration check
    gemini_key = os.getenv("GEMINI_API_KEY")
    gemini_configured = bool(gemini_key and gemini_key != "unconfigured")
    model_status = "healthy" if gemini_configured else "unconfigured"

    # 3. Redis Task Broker check (required only when async tasks are enabled)
    try:
        broker_readiness = check_broker_health()
    except Exception as e:
        broker_readiness = {
            "status": "unhealthy" if os.getenv("ASYNC_TASKS_ENABLED", "false").lower() in ("true", "1") else "disabled",
            "connected": False,
            "error": str(e),
        }
    broker_status = broker_readiness.get("status", "disabled")

    # 4. Redis Cache status (optional)
    redis_url = os.getenv("REDIS_URL")
    cache_status = "configured" if redis_url else "in-memory"

    # Determine overall readiness:
    # - If PostgreSQL is unhealthy (in production / required mode) -> UNHEALTHY (503)
    # - If Redis broker is required (async enabled) and unreachable -> UNHEALTHY (503)
    # - If safe fallbacks are active (e.g. in-memory dev mode or missing model key) -> DEGRADED (200)
    # - Otherwise -> READY (200)
    if db_status == "unhealthy" or broker_status == "unhealthy":
        overall_status = "unhealthy"
    elif db_status == "degraded" or model_status != "healthy":
        overall_status = "degraded"
    else:
        overall_status = db_status if db_status in ("healthy", "ready") else "ready"

    # Build comprehensive readiness response preserving database keys at root for backward compatibility
    response_payload = {
        **db_readiness,
        "status": overall_status,
        "liveness": "alive",
        "timestamp": time.time(),
        "dependencies": {
            "database": db_readiness,
            "model_provider": {
                "name": "gemini_api",
                "status": model_status,
                "configured": gemini_configured,
                "criticality": "required_for_ai_tutor",
            },
            "task_broker": broker_readiness,
            "cache": {
                "name": "redis_cache",
                "status": cache_status,
                "criticality": "optional",
            },
        },
    }
    return response_payload
