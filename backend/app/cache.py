import os
import json
import time
from typing import Optional, Any, Dict, Tuple
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Local in-memory cache fallback for development, testing, or Redis outages
_memory_cache: Dict[str, Tuple[Any, float]] = {}

# Initialize async Redis client with low timeout to avoid blocking when redis is offline
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=0.2,
    socket_timeout=0.2,
)


async def get_cache(key: str) -> Optional[Any]:
    """Retrieve JSON-decoded data from Redis cache, falling back to local memory if offline."""
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass

    # Check local memory fallback
    if key in _memory_cache:
        val, expiry = _memory_cache[key]
        if expiry > time.time():
            return val
        else:
            _memory_cache.pop(key, None)
    return None


async def set_cache(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Store data in Redis cache and local memory fallback with an expiration time."""
    _memory_cache[key] = (value, time.time() + ttl_seconds)
    try:
        await redis_client.set(key, json.dumps(value), ex=ttl_seconds)
        return True
    except Exception:
        return True


async def delete_cache(key: str) -> bool:
    """Remove a key from Redis and memory fallback."""
    _memory_cache.pop(key, None)
    try:
        await redis_client.delete(key)
        return True
    except Exception:
        return True
