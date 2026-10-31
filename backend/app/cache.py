"""
Redis Cache Manager with Explicit Optional Dependency Policy & Telemetry Visibility
Problem 44: Redis cache failures must never be silently swallowed.
- Structured logging and Prometheus cache error metrics.
- Connection timeouts and exponential backoff retry policies.
- Keep cache failure non-fatal only for operations that can safely bypass it.
- Version cache keys when embedding models, dimensions, or preprocessing change.
- Deliberate expiration policies mapped by data volatility.
- Strictly prevent caching of failed, placeholder, or synthetic embeddings.
"""
import asyncio
import json
import math
import os
import time
from typing import Any, Dict, Optional, Tuple

import redis.asyncio as redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from app.logger import logger

# ==============================================================================
# Configuration & Connection Settings
# ==============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_SOCKET_CONNECT_TIMEOUT = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "0.5"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.5"))
REDIS_RETRY_ATTEMPTS = int(os.getenv("REDIS_RETRY_ATTEMPTS", "2"))
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
REDIS_OUTAGE_THRESHOLD = int(os.getenv("REDIS_OUTAGE_THRESHOLD", "3"))
REDIS_CIRCUIT_BREAKER_COOLDOWN = float(os.getenv("REDIS_CIRCUIT_BREAKER_COOLDOWN", "5.0"))


# ==============================================================================
# Custom Exceptions for Non-Bypassable Failures
# ==============================================================================

class CacheError(RuntimeError):
    """Base exception for cache subsystem errors."""
    pass


class CacheConnectionError(CacheError):
    """Raised when Redis broker connection fails and operation cannot be bypassed."""
    pass


class CacheOperationError(CacheError):
    """Raised when a cache get/set/delete operation fails on a non-bypassable workflow."""
    pass


class CacheKeyError(CacheError, ValueError):
    """Raised when a cache key is malformed or invalid."""
    pass


class CacheTTLValidationError(CacheError, ValueError):
    """Raised when a cache TTL is non-positive or exceeds policy constraints."""
    pass


# ==============================================================================
# Deliberate Expiration Policies
# ==============================================================================

class CacheTTL:
    """Deliberate TTL policy values (in seconds) mapped by data volatility."""
    VOLATILE_LEADERBOARD: int = 60         # 1 min (high-frequency leaderboard churn)
    SHORT: int = 300                       # 5 min (transient computational caches)
    SESSION_OR_AUTH: int = 900             # 15 min (user sessions, auth tokens)
    IDEMPOTENCY_TASK: int = 3600           # 1 hour (Celery / task deduplication window)
    DEFAULT: int = 3600                    # 1 hour standard default
    TUTOR_RESPONSE: int = 86400            # 24 hours (pedagogical AI tutor answers)
    SEMANTIC_EMBEDDING: int = 604800       # 7 days (deterministic immutable embeddings)
    MAX_PERSISTENT: int = 2592000          # 30 days maximum allowed TTL


# ==============================================================================
# In-Memory Fallback & Telemetry Store
# ==============================================================================

# Local in-memory cache fallback for development, testing, or Redis outages
_memory_cache: Dict[str, Tuple[Any, float]] = {}

# Telemetry for Redis cache degradations and observability
CACHE_METRICS: Dict[str, Any] = {
    "redis_hits": 0,
    "redis_misses": 0,
    "redis_errors": 0,
    "total_operations": 0,
    "consecutive_errors": 0,
    "memory_fallback_hits": 0,
    "memory_fallback_misses": 0,
    "last_error": None,
    "last_error_time": None,
    "last_error_type": None,
    "degraded_mode": False,
    "outage_alert_active": False,
    "errors_by_type": {},
}


def _record_telemetry(op: str, status: str, error_type: Optional[str] = None, error_msg: Optional[str] = None):
    """Safely updates central observability Prometheus instruments and alert manager."""
    try:
        from app.core_backend.core.observability import (
            alert_manager,
            record_cache_failure,
            record_cache_metric,
        )
        if status == "error":
            record_cache_failure(
                operation=op,
                error_type=error_type or "UnknownError",
                error_msg=error_msg or "",
                consecutive_errors=CACHE_METRICS.get("consecutive_errors", 1),
            )
        else:
            record_cache_metric(op, status)
            if CACHE_METRICS.get("outage_alert_active"):
                CACHE_METRICS["outage_alert_active"] = False
                alert_manager.resolve_alert("REDIS_CACHE_OUTAGE_DETECTED")
    except Exception:
        pass


_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Lazily creates and returns the async Redis client configured with
    timeouts, connection pooling, and exponential backoff retries.
    """
    global _redis_client
    if _redis_client is None:
        retry_policy = Retry(
            ExponentialBackoff(cap=0.5, base=0.05),
            retries=REDIS_RETRY_ATTEMPTS,
        )
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
            socket_timeout=REDIS_SOCKET_TIMEOUT,
            retry=retry_policy,
            retry_on_timeout=True,
            health_check_interval=30,
            max_connections=REDIS_MAX_CONNECTIONS,
        )
    return _redis_client


# Backward-compatible global reference
redis_client = get_redis_client()


# ==============================================================================
# Cache Key Versioning
# ==============================================================================

def build_versioned_cache_key(
    namespace: str,
    identifier: str,
    version: str = "v1",
    model: Optional[str] = None,
    dim: Optional[int] = None,
    preprocessing_version: Optional[str] = None,
) -> str:
    """
    Constructs a namespace-partitioned, model-aware, and version-tagged cache key.
    Ensures cache segregation whenever models, dimensions, or text preprocessing routines change.
    Format: <namespace>:<version>[:<model>][:<dim>][:<preprocessing_version>]:<identifier>
    """
    if not namespace or not isinstance(namespace, str):
        raise CacheKeyError("Cache namespace must be a non-empty string.")
    if not identifier or not isinstance(identifier, str):
        raise CacheKeyError("Cache identifier must be a non-empty string.")

    parts = [namespace.strip().lower(), version.strip().lower()]
    if model:
        safe_model = (
            model.replace("models/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("-", "_")
            .strip()
            .lower()
        )
        parts.append(safe_model)
    if dim is not None:
        parts.append(f"d{dim}")
    if preprocessing_version:
        parts.append(f"p{preprocessing_version.strip().lower()}")
    parts.append(identifier.strip())
    return ":".join(parts)


# ==============================================================================
# Embedding Verification (Never Cache Synthetic or Placeholder Vectors)
# ==============================================================================

def is_placeholder_or_synthetic_embedding(vector: Any, expected_dim: int = 768) -> bool:
    """
    Strict validation to detect failed, placeholder, or synthetic mock embeddings.
    Rejects constant vectors (e.g. [0.1] * 768), all-zero vectors, non-finite values,
    and dimension mismatches.
    """
    if not isinstance(vector, list) or len(vector) != expected_dim:
        return True
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
        return True
    first_val = vector[0]
    # Check for identical constant values across all dimensions
    if all(abs(x - first_val) < 1e-6 for x in vector):
        return True
    return False


# ==============================================================================
# Core Cache Operations
# ==============================================================================

async def get_cache(
    key: str,
    default: Any = None,
    bypassable: bool = True,
    raise_on_error: bool = False,
) -> Optional[Any]:
    """
    Retrieve JSON-decoded data from Redis cache.

    Policy:
    - If bypassable=True and raise_on_error=False:
      Redis errors are non-fatal. Degrades safely to in-memory fallback,
      records Prometheus telemetry, logs structured warnings, and triggers alerts on sustained outages.
    - If bypassable=False or raise_on_error=True:
      Raises CacheOperationError so callers with strict persistence requirements do not silently proceed.
    - Never returns synthetic or placeholder embeddings.
    """
    if not key or not isinstance(key, str):
        raise CacheKeyError(f"Invalid cache key: expected non-empty string, got {key!r}")

    CACHE_METRICS["total_operations"] += 1

    # Circuit breaker: fast-fallback or fast-fail during active Redis outage to protect event loop
    now = time.time()
    circuit_open = (
        CACHE_METRICS.get("consecutive_errors", 0) >= REDIS_OUTAGE_THRESHOLD
        and (now - (CACHE_METRICS.get("last_error_time") or 0.0)) < REDIS_CIRCUIT_BREAKER_COOLDOWN
    )
    if circuit_open:
        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache outage active (circuit breaker open) on non-bypassable operation for key '{key}'"
            )
        if key in _memory_cache:
            val, expiry = _memory_cache[key]
            if expiry > now:
                if (key.startswith("emb:") or ":emb:" in key) and is_placeholder_or_synthetic_embedding(val):
                    _memory_cache.pop(key, None)
                    return default
                CACHE_METRICS["memory_fallback_hits"] += 1
                return val
            else:
                _memory_cache.pop(key, None)
        CACHE_METRICS["memory_fallback_misses"] += 1
        return default

    client = get_redis_client()

    try:
        data = await client.get(key)
        if data:
            CACHE_METRICS["redis_hits"] += 1
            CACHE_METRICS["consecutive_errors"] = 0
            CACHE_METRICS["degraded_mode"] = False
            _record_telemetry("read", "hit")
            parsed = json.loads(data)

            # Guard: Detect and purge any corrupt or placeholder embeddings
            if (key.startswith("emb:") or ":emb:" in key) and is_placeholder_or_synthetic_embedding(parsed):
                logger.warning(
                    f"Purging detected placeholder or synthetic embedding from Redis cache for key: {key}",
                    extra={"operation": "read", "key": key, "action": "purge_synthetic"},
                )
                await delete_cache(key, bypassable=True)
                return default

            return parsed
        else:
            CACHE_METRICS["redis_misses"] += 1
            CACHE_METRICS["consecutive_errors"] = 0
            _record_telemetry("read", "miss")
    except Exception as e:
        err_type = type(e).__name__
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["consecutive_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["last_error_time"] = time.time()
        CACHE_METRICS["last_error_type"] = err_type
        CACHE_METRICS["degraded_mode"] = True
        CACHE_METRICS["errors_by_type"][err_type] = CACHE_METRICS["errors_by_type"].get(err_type, 0) + 1

        _record_telemetry("read", "error", error_type=err_type, error_msg=str(e))

        consec = CACHE_METRICS["consecutive_errors"]
        log_payload = {
            "event": "redis_cache_read_failure",
            "operation": "read",
            "key": key,
            "error_type": err_type,
            "error_message": str(e),
            "consecutive_errors": consec,
            "degraded_mode": True,
            "bypassable": bypassable,
        }

        if consec >= REDIS_OUTAGE_THRESHOLD:
            if not CACHE_METRICS.get("outage_alert_active"):
                CACHE_METRICS["outage_alert_active"] = True
                logger.error(
                    f"Persistent Redis cache outage detected: {consec} consecutive failures. Read failed for key '{key}': {e}",
                    extra=log_payload,
                )
        else:
            logger.warning(
                f"Redis cache read failed for key '{key}' ({err_type}): {e}. Degraded fallback active.",
                extra=log_payload,
            )

        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache read failed on non-bypassable operation for key '{key}': {e}"
            ) from e

    # Safe fallback to local in-memory cache
    if key in _memory_cache:
        val, expiry = _memory_cache[key]
        if expiry > time.time():
            if (key.startswith("emb:") or ":emb:" in key) and is_placeholder_or_synthetic_embedding(val):
                _memory_cache.pop(key, None)
                return default
            CACHE_METRICS["memory_fallback_hits"] += 1
            return val
        else:
            _memory_cache.pop(key, None)

    CACHE_METRICS["memory_fallback_misses"] += 1
    return default


async def set_cache(
    key: str,
    value: Any,
    ttl_seconds: int = CacheTTL.DEFAULT,
    bypassable: bool = True,
    raise_on_error: bool = False,
    is_synthetic: bool = False,
) -> bool:
    """
    Store data in Redis cache and local memory fallback with deliberate TTL.

    Policy:
    - Never cache failed, placeholder, or synthetic embeddings.
    - Validates TTL is a positive integer.
    - If bypassable=True and raise_on_error=False:
      Redis errors are non-fatal; stores in local memory fallback, records metrics, and returns True.
    - If bypassable=False or raise_on_error=True:
      Raises CacheOperationError so caller is aware of persistent Redis write failure.
    """
    if not key or not isinstance(key, str):
        raise CacheKeyError(f"Invalid cache key: expected non-empty string, got {key!r}")

    # Validate deliberate TTL policy
    if not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0:
        raise CacheTTLValidationError(
            f"Cache TTL must be a positive integer in seconds. Got {ttl_seconds!r}. "
            "Policy: Expiration policies must be set deliberately to prevent memory leaks."
        )
    ttl_seconds = int(ttl_seconds)
    if ttl_seconds > CacheTTL.MAX_PERSISTENT:
        logger.warning(
            f"Cache TTL {ttl_seconds}s exceeds maximum allowed persistent policy ({CacheTTL.MAX_PERSISTENT}s). Clamping.",
            extra={"key": key, "original_ttl": ttl_seconds, "clamped_ttl": CacheTTL.MAX_PERSISTENT},
        )
        ttl_seconds = CacheTTL.MAX_PERSISTENT

    # Policy 6: Do not cache failed or synthetic embeddings
    if is_synthetic:
        logger.info(
            f"Bypassing cache for synthetic embedding (key: '{key}'). Policy: synthetic vectors are never cached.",
            extra={"operation": "write", "key": key, "action": "skip_synthetic_embedding"},
        )
        return False

    if (key.startswith("emb:") or ":emb:" in key) and is_placeholder_or_synthetic_embedding(value):
        logger.warning(
            f"Refusing to cache placeholder or synthetic embedding for key '{key}'.",
            extra={"operation": "write", "key": key, "action": "reject_placeholder_embedding"},
        )
        return False

    CACHE_METRICS["total_operations"] += 1
    # Store in memory fallback
    _memory_cache[key] = (value, time.time() + ttl_seconds)

    # Circuit breaker: fast-fallback or fast-fail during active Redis outage to protect event loop
    now = time.time()
    circuit_open = (
        CACHE_METRICS.get("consecutive_errors", 0) >= REDIS_OUTAGE_THRESHOLD
        and (now - (CACHE_METRICS.get("last_error_time") or 0.0)) < REDIS_CIRCUIT_BREAKER_COOLDOWN
    )
    if circuit_open:
        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache outage active (circuit breaker open) on non-bypassable write for key '{key}'"
            )
        return True

    client = get_redis_client()
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
        CACHE_METRICS["consecutive_errors"] = 0
        CACHE_METRICS["degraded_mode"] = False
        _record_telemetry("write", "success")
        return True
    except Exception as e:
        err_type = type(e).__name__
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["consecutive_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["last_error_time"] = time.time()
        CACHE_METRICS["last_error_type"] = err_type
        CACHE_METRICS["degraded_mode"] = True
        CACHE_METRICS["errors_by_type"][err_type] = CACHE_METRICS["errors_by_type"].get(err_type, 0) + 1

        _record_telemetry("write", "error", error_type=err_type, error_msg=str(e))

        consec = CACHE_METRICS["consecutive_errors"]
        log_payload = {
            "event": "redis_cache_write_failure",
            "operation": "write",
            "key": key,
            "error_type": err_type,
            "error_message": str(e),
            "consecutive_errors": consec,
            "degraded_mode": True,
            "bypassable": bypassable,
        }

        if consec >= REDIS_OUTAGE_THRESHOLD:
            if not CACHE_METRICS.get("outage_alert_active"):
                CACHE_METRICS["outage_alert_active"] = True
                logger.error(
                    f"Persistent Redis cache outage detected: {consec} consecutive failures. Write failed for key '{key}': {e}",
                    extra=log_payload,
                )
        else:
            logger.warning(
                f"Redis cache write failed for key '{key}' ({err_type}): {e}. Stored in local fallback.",
                extra=log_payload,
            )

        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache write failed on non-bypassable operation for key '{key}': {e}"
            ) from e

        return True


async def delete_cache(
    key: str,
    bypassable: bool = True,
    raise_on_error: bool = False,
) -> bool:
    """
    Remove a key from Redis and local memory fallback.

    Policy:
    - If bypassable=True: safe fallback removal.
    - If bypassable=False or raise_on_error=True: raises on Redis deletion failure.
    """
    if not key or not isinstance(key, str):
        raise CacheKeyError(f"Invalid cache key: expected non-empty string, got {key!r}")

    CACHE_METRICS["total_operations"] += 1
    _memory_cache.pop(key, None)

    # Circuit breaker: fast-fallback or fast-fail during active Redis outage to protect event loop
    now = time.time()
    circuit_open = (
        CACHE_METRICS.get("consecutive_errors", 0) >= REDIS_OUTAGE_THRESHOLD
        and (now - (CACHE_METRICS.get("last_error_time") or 0.0)) < REDIS_CIRCUIT_BREAKER_COOLDOWN
    )
    if circuit_open:
        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache outage active (circuit breaker open) on non-bypassable delete for key '{key}'"
            )
        return True

    client = get_redis_client()
    try:
        await client.delete(key)
        CACHE_METRICS["consecutive_errors"] = 0
        _record_telemetry("delete", "success")
        return True
    except Exception as e:
        err_type = type(e).__name__
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["consecutive_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["last_error_time"] = time.time()
        CACHE_METRICS["last_error_type"] = err_type
        CACHE_METRICS["degraded_mode"] = True
        CACHE_METRICS["errors_by_type"][err_type] = CACHE_METRICS["errors_by_type"].get(err_type, 0) + 1

        _record_telemetry("delete", "error", error_type=err_type, error_msg=str(e))

        consec = CACHE_METRICS["consecutive_errors"]
        log_payload = {
            "event": "redis_cache_delete_failure",
            "operation": "delete",
            "key": key,
            "error_type": err_type,
            "error_message": str(e),
            "consecutive_errors": consec,
            "degraded_mode": True,
            "bypassable": bypassable,
        }

        if consec >= REDIS_OUTAGE_THRESHOLD:
            if not CACHE_METRICS.get("outage_alert_active"):
                CACHE_METRICS["outage_alert_active"] = True
                logger.error(
                    f"Persistent Redis cache outage detected: {consec} consecutive failures. Delete failed for key '{key}': {e}",
                    extra=log_payload,
                )
        else:
            logger.warning(
                f"Redis cache delete failed for key '{key}' ({err_type}): {e}.",
                extra=log_payload,
            )

        if not bypassable or raise_on_error:
            raise CacheOperationError(
                f"Redis cache delete failed on non-bypassable operation for key '{key}': {e}"
            ) from e

        return True


# ==============================================================================
# Health & Diagnostics
# ==============================================================================

async def check_redis_cache_health() -> Dict[str, Any]:
    """
    Returns health check status for Redis cache according to dependency policy:
    - Status: 'healthy' when connected, 'degraded' when offline.
    - Criticality: 'optional'.
    - Telemetry metrics and error observables included.
    """
    client = get_redis_client()
    start = time.perf_counter()
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=REDIS_SOCKET_TIMEOUT)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        CACHE_METRICS["consecutive_errors"] = 0
        CACHE_METRICS["degraded_mode"] = False
        return {
            "status": "healthy" if pong else "degraded",
            "connected": bool(pong),
            "criticality": "optional",
            "policy": "optional_safe_degradation",
            "latency_ms": latency_ms,
            "metrics": dict(CACHE_METRICS),
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        err_type = type(e).__name__
        CACHE_METRICS["degraded_mode"] = True
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["last_error_time"] = time.time()
        CACHE_METRICS["last_error_type"] = err_type
        return {
            "status": "degraded",
            "connected": False,
            "criticality": "optional",
            "policy": "optional_safe_degradation",
            "latency_ms": latency_ms,
            "error": str(e),
            "error_type": err_type,
            "consecutive_errors": CACHE_METRICS.get("consecutive_errors", 0),
            "fallback_active": True,
            "metrics": dict(CACHE_METRICS),
        }


def clear_local_cache():
    """Resets local memory cache and telemetry for testing and test isolation."""
    _memory_cache.clear()
    CACHE_METRICS["redis_hits"] = 0
    CACHE_METRICS["redis_misses"] = 0
    CACHE_METRICS["redis_errors"] = 0
    CACHE_METRICS["total_operations"] = 0
    CACHE_METRICS["consecutive_errors"] = 0
    CACHE_METRICS["memory_fallback_hits"] = 0
    CACHE_METRICS["memory_fallback_misses"] = 0
    CACHE_METRICS["last_error"] = None
    CACHE_METRICS["last_error_time"] = None
    CACHE_METRICS["last_error_type"] = None
    CACHE_METRICS["degraded_mode"] = False
    CACHE_METRICS["outage_alert_active"] = False
    CACHE_METRICS["errors_by_type"].clear()
