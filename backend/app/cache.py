"""
Redis Cache Manager with Explicit Optional Dependency Policy
Problem 30: Optional for cache reads; degrade performance safely with in-memory fallback.
"""
import os
import json
import time
import asyncio
from typing import Optional, Any, Dict, Tuple
import redis.asyncio as redis
from app.logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Local in-memory cache fallback for development, testing, or Redis outages
_memory_cache: Dict[str, Tuple[Any, float]] = {}

# Telemetry for Redis cache degradations and observability
CACHE_METRICS: Dict[str, Any] = {
    "redis_hits": 0,
    "redis_misses": 0,
    "redis_errors": 0,
    "memory_fallback_hits": 0,
    "memory_fallback_misses": 0,
    "last_error": None,
    "degraded_mode": False,
}

def _record_telemetry(op: str, status: str):
    """Safely updates central observability Prometheus instruments."""
    try:
        from app.core_backend.core.observability import record_cache_metric
        record_cache_metric(op, status)
    except Exception:
        pass

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Lazily creates and returns the async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
        )
    return _redis_client


# Backward-compatible global reference
redis_client = get_redis_client()


async def get_cache(key: str) -> Optional[Any]:
    """
    Retrieve JSON-decoded data from Redis cache.
    Policy: Optional dependency. If Redis fails or is offline,
    logs a structured warning, records telemetry, and safely degrades to in-memory fallback.
    """
    client = get_redis_client()
    try:
        data = await client.get(key)
        if data:
            CACHE_METRICS["redis_hits"] += 1
            CACHE_METRICS["degraded_mode"] = False
            _record_telemetry("read", "hit")
            return json.loads(data)
        else:
            CACHE_METRICS["redis_misses"] += 1
            _record_telemetry("read", "miss")
    except Exception as e:
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["degraded_mode"] = True
        _record_telemetry("read", "error")
        logger.warning(
            f"Redis cache read failed for key '{key}' ({type(e).__name__}): {e}. "
            "Safely degrading to in-memory cache fallback without affecting core service availability."
        )

    # Safe fallback to local in-memory cache
    if key in _memory_cache:
        val, expiry = _memory_cache[key]
        if expiry > time.time():
            CACHE_METRICS["memory_fallback_hits"] += 1
            return val
        else:
            _memory_cache.pop(key, None)
    CACHE_METRICS["memory_fallback_misses"] += 1
    return None


async def set_cache(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """
    Store data in Redis cache and local memory fallback with an expiration time.
    Policy: Optional dependency. Redis failure does not crash or block callers.
    """
    _memory_cache[key] = (value, time.time() + ttl_seconds)
    client = get_redis_client()
    try:
        await client.set(key, json.dumps(value), ex=ttl_seconds)
        CACHE_METRICS["degraded_mode"] = False
        _record_telemetry("write", "success")
        return True
    except Exception as e:
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["degraded_mode"] = True
        _record_telemetry("write", "error")
        logger.warning(
            f"Redis cache write failed for key '{key}' ({type(e).__name__}): {e}. "
            "Stored in local memory cache fallback. Degraded performance safely preserved."
        )
        return True


async def delete_cache(key: str) -> bool:
    """
    Remove a key from Redis and memory fallback.
    Policy: Optional dependency.
    """
    _memory_cache.pop(key, None)
    client = get_redis_client()
    try:
        await client.delete(key)
        _record_telemetry("delete", "success")
        return True
    except Exception as e:
        CACHE_METRICS["redis_errors"] += 1
        CACHE_METRICS["last_error"] = str(e)
        CACHE_METRICS["degraded_mode"] = True
        _record_telemetry("delete", "error")
        logger.warning(f"Redis cache delete failed for key '{key}' ({type(e).__name__}): {e}.")
        return True


async def check_redis_cache_health() -> Dict[str, Any]:
    """
    Returns health check status for Redis cache according to dependency policy:
    - Status: 'healthy' when connected, 'degraded' when offline.
    - Criticality: 'optional'.
    """
    client = get_redis_client()
    try:
        pong = await asyncio.wait_for(client.ping(), timeout=0.5)
        return {
            "status": "healthy" if pong else "degraded",
            "connected": bool(pong),
            "criticality": "optional",
            "policy": "optional_safe_degradation",
            "metrics": dict(CACHE_METRICS),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "connected": False,
            "criticality": "optional",
            "policy": "optional_safe_degradation",
            "error": str(e),
            "fallback_active": True,
            "metrics": dict(CACHE_METRICS),
        }


def clear_local_cache():
    """Resets local memory cache and telemetry for testing."""
    _memory_cache.clear()
    CACHE_METRICS["redis_hits"] = 0
    CACHE_METRICS["redis_misses"] = 0
    CACHE_METRICS["redis_errors"] = 0
    CACHE_METRICS["memory_fallback_hits"] = 0
    CACHE_METRICS["memory_fallback_misses"] = 0
    CACHE_METRICS["last_error"] = None
    CACHE_METRICS["degraded_mode"] = False
