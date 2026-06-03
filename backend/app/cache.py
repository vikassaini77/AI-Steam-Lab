import os
import json
import redis.asyncio as redis
from typing import Optional, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize async Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

async def get_cache(key: str) -> Optional[Any]:
    """Retrieve JSON-decoded data from Redis cache."""
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        print(f"Redis get error: {e}")
    return None

async def set_cache(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Store data in Redis cache with an expiration time."""
    try:
        await redis_client.set(key, json.dumps(value), ex=ttl_seconds)
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
        return False

async def delete_cache(key: str) -> bool:
    """Remove a key from the Redis cache."""
    try:
        await redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Redis delete error: {e}")
        return False
