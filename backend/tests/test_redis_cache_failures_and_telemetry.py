"""
Tests for Problem 44: Redis cache failures are swallowed without adequate visibility.
Verifies:
1. Graceful degradation to memory fallback when Redis is offline.
2. Cache errors remain fully observable via structured logging, CACHE_METRICS, and Prometheus counters.
3. Persistent outages trigger operational alerts (REDIS_CACHE_OUTAGE_DETECTED).
4. Non-bypassable operations raise CacheOperationError instead of silently swallowing errors.
5. Connection timeouts, retry policies, and pool settings are strictly configured.
6. Cache key versioning segregates by model, dimension, and preprocessing version.
7. Deliberate TTL policies (CacheTTL) with validation against non-positive TTLs.
8. Failed, placeholder, or synthetic embeddings are strictly never cached.
9. Verification: Stopping Redis degrades operations gracefully while errors remain observable.
"""
import time
import math
import asyncio
from unittest.mock import MagicMock, patch
import pytest

from app.cache import (
    get_cache,
    set_cache,
    delete_cache,
    check_redis_cache_health,
    clear_local_cache,
    build_versioned_cache_key,
    is_placeholder_or_synthetic_embedding,
    CacheTTL,
    CacheError,
    CacheOperationError,
    CacheKeyError,
    CacheTTLValidationError,
    CACHE_METRICS,
    get_redis_client,
)
from app.core_backend.core.observability import (
    CACHE_OPERATIONS_TOTAL,
    CACHE_ERRORS_TOTAL,
    alert_manager,
)
from app.ai_agent.embedding_service import generate_embedding, EXPECTED_EMBEDDING_DIM


@pytest.fixture(autouse=True)
def setup_teardown_cache():
    """Isolates each test by clearing local memory cache and resetting metrics."""
    clear_local_cache()
    alert_manager.resolve_alert("REDIS_CACHE_OUTAGE_DETECTED")
    yield
    clear_local_cache()
    alert_manager.resolve_alert("REDIS_CACHE_OUTAGE_DETECTED")


# ==============================================================================
# 1. Graceful Degradation & Full Observability on Redis Outage
# ==============================================================================

@pytest.mark.asyncio
async def test_redis_outage_degrades_gracefully_with_full_observability(monkeypatch):
    """
    Verification: Stop Redis and confirm that cache-dependent operations degrade
    gracefully to local memory while errors remain observable in metrics and logs.
    """
    mock_redis = MagicMock()

    async def failing_call(*args, **kwargs):
        raise ConnectionRefusedError("Connection refused: Redis is stopped on localhost:6379")

    mock_redis.get = failing_call
    mock_redis.set = failing_call
    mock_redis.delete = failing_call
    mock_redis.ping = failing_call

    import app.cache as cache_module
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: mock_redis)

    # 1. Write during outage: degrades to memory fallback and returns True
    success = await set_cache("experiment_summary_123", {"physics_val": 42}, ttl_seconds=CacheTTL.SHORT)
    assert success is True

    # Confirm error observability
    assert CACHE_METRICS["redis_errors"] >= 1
    assert CACHE_METRICS["consecutive_errors"] >= 1
    assert CACHE_METRICS["degraded_mode"] is True
    assert "Connection refused" in str(CACHE_METRICS["last_error"])
    assert CACHE_METRICS["last_error_type"] == "ConnectionRefusedError"
    assert CACHE_METRICS["errors_by_type"].get("ConnectionRefusedError", 0) >= 1

    # 2. Read during outage: gracefully served from memory fallback
    cached_val = await get_cache("experiment_summary_123")
    assert cached_val == {"physics_val": 42}
    assert CACHE_METRICS["memory_fallback_hits"] >= 1

    # Confirm read error on Redis was recorded too
    assert CACHE_METRICS["redis_errors"] >= 2
    assert CACHE_METRICS["consecutive_errors"] >= 2

    # 3. Health check observes degraded state
    health = await check_redis_cache_health()
    assert health["status"] == "degraded"
    assert health["connected"] is False
    assert health["fallback_active"] is True
    assert health["error_type"] == "ConnectionRefusedError"


@pytest.mark.asyncio
async def test_persistent_outage_triggers_operational_alert(monkeypatch):
    """Confirms consecutive failures trigger REDIS_CACHE_OUTAGE_DETECTED alert."""
    mock_redis = MagicMock()

    async def failing_call(*args, **kwargs):
        raise TimeoutError("Redis socket read timeout")

    mock_redis.get = failing_call
    mock_redis.set = failing_call
    mock_redis.delete = failing_call

    import app.cache as cache_module
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: mock_redis)

    # Trigger consecutive errors
    for i in range(3):
        await get_cache(f"test_key_{i}")

    assert CACHE_METRICS["consecutive_errors"] == 3
    assert CACHE_METRICS["outage_alert_active"] is True

    # Verify operational alert was raised in AlertManager
    active_alerts = alert_manager.get_active_alerts()
    outage_alert = next((a for a in active_alerts if a["name"] == "REDIS_CACHE_OUTAGE_DETECTED"), None)
    assert outage_alert is not None
    assert outage_alert["severity"] == "WARNING"
    assert "3 consecutive failures" in outage_alert["message"]


# ==============================================================================
# 2. Non-Bypassable Failures (Explicit Non-Fatal vs Fatal Policy)
# ==============================================================================

@pytest.mark.asyncio
async def test_non_bypassable_cache_failure_raises_exception(monkeypatch):
    """
    Confirms operations that cannot safely bypass Redis raise CacheOperationError
    instead of silently continuing with local fallback or returning None/False.
    """
    mock_redis = MagicMock()

    async def failing_call(*args, **kwargs):
        raise ConnectionResetError("Redis broker connection dropped unexpectedly")

    mock_redis.get = failing_call
    mock_redis.set = failing_call
    mock_redis.delete = failing_call

    import app.cache as cache_module
    monkeypatch.setattr(cache_module, "get_redis_client", lambda: mock_redis)

    # 1. Non-bypassable read must raise CacheOperationError
    with pytest.raises(CacheOperationError) as exc_get:
        await get_cache("critical_distributed_session", bypassable=False)
    assert "non-bypassable" in str(exc_get.value)

    # 2. Non-bypassable write with raise_on_error=True must raise CacheOperationError
    with pytest.raises(CacheOperationError) as exc_set:
        await set_cache("idempotency_lock_token", "locked", ttl_seconds=60, raise_on_error=True)
    assert "non-bypassable" in str(exc_set.value)

    # 3. Non-bypassable delete must raise CacheOperationError
    with pytest.raises(CacheOperationError) as exc_del:
        await delete_cache("idempotency_lock_token", bypassable=False)
    assert "non-bypassable" in str(exc_del.value)


# ==============================================================================
# 3. Connection Timeouts & Sensible Retry Configuration
# ==============================================================================

def test_redis_client_configuration():
    """Verifies that Redis client uses non-blocking timeouts, connection pooling, and retry backoff."""
    client = get_redis_client()
    connection_kwargs = client.connection_pool.connection_kwargs

    # Sockets must have short bounded timeouts (0.5s or less)
    assert connection_kwargs["socket_connect_timeout"] <= 0.5
    assert connection_kwargs["socket_timeout"] <= 0.5
    # Retry policy must be enabled
    assert connection_kwargs.get("retry_on_timeout") is True
    assert connection_kwargs.get("retry") is not None
    assert client.connection_pool.max_connections >= 10


# ==============================================================================
# 4. Cache Key Versioning
# ==============================================================================

def test_cache_key_versioning_segregation():
    """
    Verifies that cache keys incorporate model, dimension, and preprocessing version,
    preventing cross-model cache pollution or outdated format collisions.
    """
    text_id = "abc123456789"

    # Default model
    key1 = build_versioned_cache_key(
        namespace="emb",
        identifier=text_id,
        version="v1",
        model="models/gemini-embedding-001",
        dim=768,
        preprocessing_version="norm_v1",
    )
    assert key1 == f"emb:v1:gemini_embedding_001:d768:pnorm_v1:{text_id}"

    # Upgraded model: different key
    key2 = build_versioned_cache_key(
        namespace="emb",
        identifier=text_id,
        version="v1",
        model="models/text-embedding-004",
        dim=768,
        preprocessing_version="norm_v1",
    )
    assert key2 != key1
    assert "text_embedding_004" in key2

    # Higher dimension: different key
    key3 = build_versioned_cache_key(
        namespace="emb",
        identifier=text_id,
        version="v1",
        model="models/gemini-embedding-001",
        dim=1536,
        preprocessing_version="norm_v1",
    )
    assert key3 != key1
    assert "d1536" in key3

    # Modified preprocessing: different key
    key4 = build_versioned_cache_key(
        namespace="emb",
        identifier=text_id,
        version="v1",
        model="models/gemini-embedding-001",
        dim=768,
        preprocessing_version="norm_v2",
    )
    assert key4 != key1
    assert "pnorm_v2" in key4


def test_invalid_cache_key_rejected():
    """Rejects empty or non-string cache keys."""
    with pytest.raises(CacheKeyError):
        build_versioned_cache_key("", "id123")

    with pytest.raises(CacheKeyError):
        build_versioned_cache_key("ns", "")


# ==============================================================================
# 5. Deliberate Expiration Policies (CacheTTL)
# ==============================================================================

@pytest.mark.asyncio
async def test_deliberate_ttl_validation():
    """Rejects non-positive or missing TTL to prevent unbounded cache retention."""
    with pytest.raises(CacheTTLValidationError):
        await set_cache("valid_key", {"data": 1}, ttl_seconds=0)

    with pytest.raises(CacheTTLValidationError):
        await set_cache("valid_key", {"data": 1}, ttl_seconds=-10)

    with pytest.raises(CacheTTLValidationError):
        await set_cache("valid_key", {"data": 1}, ttl_seconds="invalid")  # type: ignore


def test_cache_ttl_constants_alignment():
    """Confirms defined CacheTTL values match documented SLA volatility."""
    assert CacheTTL.VOLATILE_LEADERBOARD == 60       # 1 min
    assert CacheTTL.SHORT == 300                     # 5 min
    assert CacheTTL.SESSION_OR_AUTH == 900           # 15 min
    assert CacheTTL.IDEMPOTENCY_TASK == 3600         # 1 hr
    assert CacheTTL.DEFAULT == 3600                  # 1 hr
    assert CacheTTL.TUTOR_RESPONSE == 86400          # 24 hrs
    assert CacheTTL.SEMANTIC_EMBEDDING == 604800     # 7 days


# ==============================================================================
# 6. Do Not Cache Failed or Synthetic Embeddings
# ==============================================================================

@pytest.mark.asyncio
async def test_refuses_to_cache_placeholder_embedding():
    """Policy: Uniform constant vectors ([0.1] * 768) must never be written to cache."""
    placeholder_vec = [0.1] * 768
    key = "emb:v1:test:d768:fake_text_hash"

    stored = await set_cache(key, placeholder_vec, ttl_seconds=CacheTTL.SEMANTIC_EMBEDDING)
    assert stored is False

    # Confirm it is not stored in memory fallback
    res = await get_cache(key)
    assert res is None


@pytest.mark.asyncio
async def test_refuses_to_cache_synthetic_flagged_embedding():
    """Policy: Embeddings marked is_synthetic=True must never be written to cache."""
    valid_vec = [0.01 * i for i in range(768)]
    key = "emb:v1:test:d768:synthetic_text_hash"

    stored = await set_cache(key, valid_vec, ttl_seconds=CacheTTL.SEMANTIC_EMBEDDING, is_synthetic=True)
    assert stored is False

    res = await get_cache(key)
    assert res is None


@pytest.mark.asyncio
async def test_get_cache_evicts_placeholder_if_encountered():
    """If a legacy placeholder is somehow retrieved from cache, get_cache evicts it and returns default."""
    key = "emb:v1:test:legacy_placeholder"
    # Manually poison memory cache with a legacy placeholder
    import app.cache as cache_module
    cache_module._memory_cache[key] = ([0.1] * 768, time.time() + 3600)

    val = await get_cache(key, default=None)
    assert val is None
    # Confirm purged from memory cache
    assert key not in cache_module._memory_cache


@pytest.mark.asyncio
async def test_generate_embedding_does_not_cache_synthetic_vectors():
    """
    When mock credentials are used and synthetic vectors are generated under ALLOW_FAKE_VECTORS,
    they must NOT be saved to the cache.
    """
    with patch("os.getenv", side_effect=lambda k, d=None: "true" if k == "ALLOW_FAKE_VECTORS" else ("mock-key" if k == "GEMINI_API_KEY" else d)):
        with patch("app.cache.set_cache", wraps=set_cache) as spy_set_cache:
            emb = await generate_embedding("Unique physics query about angular momentum 998877")
            assert len(emb) == EXPECTED_EMBEDDING_DIM

            # Confirm set_cache was NOT called because is_synthetic was True
            spy_set_cache.assert_not_called()

