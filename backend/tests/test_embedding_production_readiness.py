"""
Unit and integration tests for Problem 7:
Embedding Service Production Readiness, Single-Flight Deduplication, Retries,
Circuit Breaking, Error Sanitization, Versioning, and Production Synthetic Prohibition.
"""
import asyncio
import os
import time
import pytest
from unittest.mock import patch, MagicMock

from app.ai_agent.embedding_service import (
    generate_embedding,
    reembed_existing_memories,
    sanitize_provider_error,
    is_transient_error,
    SingleFlight,
    EmbeddingCircuitBreaker,
    EmbeddingCircuitBreakerOpenError,
    EmbeddingError,
    get_embedding_circuit_breaker,
    reset_embedding_circuit_breaker,
    EXPECTED_EMBEDDING_DIM,
    EMBEDDING_VERSION,
)
from app.core_backend.core.observability import alert_manager
from app.core_backend.database.supabase_db import DatabaseManager


@pytest.fixture(autouse=True)
def clean_embedding_state(monkeypatch):
    reset_embedding_circuit_breaker()
    alert_manager.clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-mock-gemini-key-1234567890")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("ALLOW_FAKE_VECTORS", "true")
    yield
    reset_embedding_circuit_breaker()
    alert_manager.clear()


@pytest.mark.asyncio
async def test_single_flight_request_deduplication():
    """
    Validates that concurrent identical embedding requests are deduplicated
    into exactly ONE provider API call.
    """
    call_count = 0
    fake_vector = [0.05 * ((i % 10) + 1) for i in range(EXPECTED_EMBEDDING_DIM)]

    def mock_embed(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        time.sleep(0.05)
        return {"embedding": fake_vector}

    with patch("google.generativeai.embed_content", side_effect=mock_embed):
        # Fire 8 concurrent calls for the exact same unique sentence
        unique_text = f"Single flight deduplication test {time.time()}"
        tasks = [generate_embedding(unique_text) for _ in range(8)]
        results = await asyncio.gather(*tasks)

        # Confirm all 8 callers received identical valid embeddings
        assert len(results) == 8
        for res in results:
            assert res == fake_vector

        # Confirm only ONE underlying API call was made
        assert call_count == 1


@pytest.mark.asyncio
async def test_transient_error_retry_and_recovery(monkeypatch):
    """
    Validates bounded retries with exponential backoff for transient provider failures.
    Recovers on second attempt.
    """
    attempts = 0
    fake_vector = [0.03 * ((i % 5) + 1) for i in range(EXPECTED_EMBEDDING_DIM)]

    def flaky_embed(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("ResourceExhausted: 429 Quota Exceeded (transient rate limit)")
        return {"embedding": fake_vector}

    with patch("google.generativeai.embed_content", side_effect=flaky_embed):
        res = await generate_embedding(f"Transient retry test {time.time()}")
        assert res == fake_vector
        assert attempts == 2


@pytest.mark.asyncio
async def test_provider_error_sanitization_masks_api_keys():
    """
    Verifies that raw provider error strings containing API keys or secrets
    are safely sanitized and never leaked in raised exceptions.
    """
    raw_leaked_key = "AIzaSyD1234567890abcdefghijklmnopqrstuv"
    sensitive_error = RuntimeError(f"403 Forbidden: Invalid credentials AIzaSyD1234567890abcdefghijklmnopqrstuv for project prj-998877")

    sanitized = sanitize_provider_error(sensitive_error)
    assert raw_leaked_key not in sanitized
    assert "authentication or authorization failed" in sanitized.lower()


@pytest.mark.asyncio
async def test_circuit_breaker_trips_to_open_after_repeated_failures(monkeypatch):
    """
    Verifies that consecutive provider failures trip the circuit breaker to OPEN,
    fast-failing subsequent calls and recording an alert.
    """
    monkeypatch.setenv("ALLOW_FAKE_VECTORS", "false")
    cb = EmbeddingCircuitBreaker(failure_threshold=3, cooldown_seconds=0.5)

    with patch("app.ai_agent.embedding_service._circuit_breaker", cb):
        with patch("google.generativeai.embed_content", side_effect=RuntimeError("503 Service Unavailable")):
            # 3 failures to trip the circuit
            for i in range(3):
                with pytest.raises(EmbeddingError):
                    await generate_embedding(f"Outage sentence {i}")

            # 4th call should immediately fast-fail with EmbeddingCircuitBreakerOpenError
            with pytest.raises(EmbeddingCircuitBreakerOpenError) as exc_info:
                await generate_embedding("Outage sentence fast fail")
            assert "circuit breaker is OPEN" in str(exc_info.value)

            # Confirm operational alert was triggered
            assert alert_manager.is_alert_active("EMBEDDING_CIRCUIT_BREAKER_OPEN") is True


@pytest.mark.asyncio
async def test_circuit_breaker_recovers_after_cooldown(monkeypatch):
    """
    Verifies that after cooldown, the circuit breaker enters HALF_OPEN,
    probes the provider, and resets to CLOSED upon success.
    """
    monkeypatch.setenv("ALLOW_FAKE_VECTORS", "false")
    cb = EmbeddingCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    fake_vector = [0.02 * ((i % 7) + 1) for i in range(EXPECTED_EMBEDDING_DIM)]

    with patch("app.ai_agent.embedding_service._circuit_breaker", cb):
        with patch("google.generativeai.embed_content", side_effect=RuntimeError("503 Service Unavailable")):
            for i in range(2):
                with pytest.raises(EmbeddingError):
                    await generate_embedding(f"Fail {i}")

        # Wait for cooldown to expire
        await asyncio.sleep(0.15)

        # Successful call during probe resets circuit
        with patch("google.generativeai.embed_content", return_value={"embedding": fake_vector}):
            res = await generate_embedding(f"Recover sentence {time.time()}")
            assert res == fake_vector
            assert cb.state == "CLOSED"
            assert cb.consecutive_failures == 0


@pytest.mark.asyncio
async def test_synthetic_vectors_strictly_forbidden_in_production(monkeypatch):
    """
    CRITICAL POLICY: Synthetic or fake vectors must NEVER be allowed in production,
    even if ALLOW_FAKE_VECTORS is set to true and a mock key is present.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_FAKE_VECTORS", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-mock-key")

    with patch("google.generativeai.embed_content", side_effect=RuntimeError("Upstream API failure")):
        with pytest.raises(EmbeddingError) as exc_info:
            await generate_embedding("Production query")

        # Must raise clean EmbeddingError, NOT return synthetic vector
        assert "production" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_version_migration_reembeds_outdated_versions():
    """
    Verifies that reembed_existing_memories detects memories embedded
    with outdated model versions and re-embeds them with active EMBEDDING_VERSION.
    """
    fake_vector = [0.04 * ((i % 8) + 1) for i in range(EXPECTED_EMBEDDING_DIM)]
    db = DatabaseManager()

    # Save a memory with an outdated version tag (session_id, text, embedding, user_id)
    mem_id = db.save_memory("sess_mig_1", "Outdated version memory text", fake_vector, "user_mig_1")
    db_data = db._read_local()
    for m in db_data.get("memories", []):
        if m.get("id") == mem_id:
            m["embedding_version"] = "v0-legacy-old-model-dim768"
    db._write_local(db_data)

    with patch("google.generativeai.embed_content", return_value={"embedding": fake_vector}):
        updated_count = await reembed_existing_memories(db)
        assert updated_count >= 1

        # Confirm the memory now has current EMBEDDING_VERSION
        reloaded = db._read_local()
        migrated_mem = [m for m in reloaded.get("memories", []) if m.get("id") == mem_id][0]
        assert migrated_mem["embedding_version"] == EMBEDDING_VERSION
