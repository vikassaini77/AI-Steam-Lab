"""
Production-grade Semantic Embedding Service for AI Tutor and Memory Retrieval.
Problem 45: Service boundaries separation.
Problem 7: Production verification, request deduplication, bounded exponential retries,
circuit breaking, model/preprocessing versioning, error sanitization, and strict prohibition
of synthetic vectors in production.
"""
import asyncio
import hashlib
import logging
import math
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import numpy as np

from app.cache import (
    CacheTTL,
    build_versioned_cache_key,
    get_cache,
    is_placeholder_or_synthetic_embedding,
    set_cache,
)
from app.core_backend.core.observability import alert_manager
from app.logger import logger

# ==============================================================================
# Model & Preprocessing Configuration Versioning
# ==============================================================================

EXPECTED_EMBEDDING_DIM = 768
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
PREPROCESSING_VERSION = "norm_strip_v1"
EMBEDDING_MODEL_VERSION = os.getenv("EMBEDDING_MODEL_VERSION", "v1")
EMBEDDING_VERSION = f"{EMBEDDING_MODEL_VERSION}-{DEFAULT_EMBEDDING_MODEL.replace('/', '_')}-dim{EXPECTED_EMBEDDING_DIM}-{PREPROCESSING_VERSION}"

PROVIDER_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT", "10.0"))
MAX_RETRIES = int(os.getenv("EMBEDDING_MAX_RETRIES", "2"))
INITIAL_BACKOFF_SECONDS = float(os.getenv("EMBEDDING_INITIAL_BACKOFF", "0.2"))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("EMBEDDING_CIRCUIT_BREAKER_THRESHOLD", "3"))
CIRCUIT_BREAKER_COOLDOWN = float(os.getenv("EMBEDDING_CIRCUIT_BREAKER_COOLDOWN", "5.0"))


# ==============================================================================
# Custom Exceptions
# ==============================================================================

class EmbeddingError(RuntimeError):
    """Base exception for embedding failures."""
    pass


class EmbeddingDimensionError(EmbeddingError, ValueError):
    """Raised when the output vector dimension does not match PostgreSQL VECTOR(768)."""
    pass


class EmbeddingNumericalError(EmbeddingError, ValueError):
    """Raised when the embedding contains invalid numerical values (NaN, Inf)."""
    pass


class EmbeddingCircuitBreakerOpenError(EmbeddingError):
    """Raised when the circuit breaker is OPEN to fast-fail calls during upstream outages."""
    pass


# ==============================================================================
# Error Sanitization
# ==============================================================================

def sanitize_provider_error(err: Exception) -> str:
    """
    Sanitizes raw provider exception text to prevent leaking sensitive API keys,
    tokens, project identifiers, or internal stack trace details.
    """
    raw_msg = str(err)
    # Redact Google API keys or long tokens
    redacted = re.sub(r'(?:AIza|AQ\.)[0-9A-Za-z-_]{30,}', '[REDACTED_API_KEY]', raw_msg)
    redacted = re.sub(r'[a-zA-Z0-9_\-]{32,}', '[REDACTED_CREDENTIAL]', redacted)

    msg_lower = raw_msg.lower()
    if "429" in msg_lower or "quota" in msg_lower or "resource_exhausted" in msg_lower:
        return "Embedding provider quota exceeded or rate-limited. Please retry shortly."
    if "401" in msg_lower or "403" in msg_lower or "permission" in msg_lower or "unauthenticated" in msg_lower:
        return "Embedding provider authentication or authorization failed. Check provider credentials."
    if "timeout" in msg_lower or "timed out" in msg_lower:
        return f"Embedding provider request timed out after {PROVIDER_TIMEOUT_SECONDS}s."
    if "unavailable" in msg_lower or "503" in msg_lower or "502" in msg_lower or "504" in msg_lower:
        return "Embedding provider service is temporarily unavailable."
    if "invalid_argument" in msg_lower or "bad request" in msg_lower or "400" in msg_lower:
        return "Embedding provider rejected query content as invalid argument."

    return f"Embedding generation failed: {redacted[:120]}"


def is_transient_error(err: Exception) -> bool:
    """Identifies transient network, rate-limit, and temporary provider errors suitable for retry."""
    if isinstance(err, (asyncio.TimeoutError, TimeoutError)):
        return True
    err_str = str(err).lower()
    transient_indicators = [
        "429", "quota", "resource_exhausted", "rate limit",
        "500", "502", "503", "504", "unavailable",
        "connection reset", "connection refused", "broken pipe",
        "temporary failure", "network unreachable"
    ]
    return any(ind in err_str for ind in transient_indicators)


# ==============================================================================
# Single-Flight Request Deduplication
# ==============================================================================

class SingleFlight:
    """
    Single-flight request deduplicator.
    Coalesces identical concurrent embedding generation requests into a single
    execution, strictly preventing duplicate API calls and cache-miss stampedes.
    """

    def __init__(self):
        self._inflight: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def execute(self, key: str, coro_fn):
        async with self._lock:
            if key in self._inflight:
                # Concurrent identical request is already executing; await its task
                return await self._inflight[key]

            task = asyncio.create_task(coro_fn())
            self._inflight[key] = task

        try:
            return await task
        finally:
            async with self._lock:
                self._inflight.pop(key, None)


_single_flight = SingleFlight()


# ==============================================================================
# Circuit Breaker for Provider Outages
# ==============================================================================

class CircuitState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class EmbeddingCircuitBreaker:
    """
    Circuit breaker protecting the embedding pipeline from cascading upstream failures.
    - CLOSED: normal operation.
    - OPEN: fast-fails requests without network latency when upstream is failing.
    - HALF_OPEN: allows a probe request after cooldown to test upstream health.
    """

    def __init__(
        self,
        failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        cooldown_seconds: float = CIRCUIT_BREAKER_COOLDOWN,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0
        self._lock = asyncio.Lock()

    async def before_execution(self) -> None:
        async with self._lock:
            now = time.time()
            if self.state == CircuitState.OPEN:
                if (now - self.last_failure_time) >= self.cooldown_seconds:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Embedding circuit breaker transitioning to HALF_OPEN (probing upstream).")
                else:
                    remaining = round(self.cooldown_seconds - (now - self.last_failure_time), 1)
                    raise EmbeddingCircuitBreakerOpenError(
                        f"Embedding circuit breaker is OPEN due to repeated upstream provider outages. "
                        f"Fast-failing request (cooldown active, retry in {remaining}s)."
                    )

    async def record_success(self) -> None:
        async with self._lock:
            self.consecutive_failures = 0
            if self.state != CircuitState.CLOSED:
                logger.info("Embedding circuit breaker successfully recovered -> CLOSED.")
                self.state = CircuitState.CLOSED
                try:
                    alert_manager.resolve_alert("EMBEDDING_CIRCUIT_BREAKER_OPEN")
                except Exception:
                    pass

    async def record_failure(self, error: Exception) -> None:
        async with self._lock:
            self.consecutive_failures += 1
            self.last_failure_time = time.time()
            if self.consecutive_failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    f"Embedding circuit breaker TRIPPED to OPEN ({self.consecutive_failures} consecutive failures). "
                    f"Cooldown: {self.cooldown_seconds}s.",
                    extra={"consecutive_failures": self.consecutive_failures, "error": str(error)},
                )
                try:
                    alert_manager.trigger_alert(
                        alert_name="EMBEDDING_CIRCUIT_BREAKER_OPEN",
                        severity="HIGH",
                        message=(
                            f"Embedding provider circuit breaker tripped to OPEN after "
                            f"{self.consecutive_failures} consecutive failures: {str(error)}"
                        ),
                        metadata={"consecutive_failures": self.consecutive_failures, "cooldown": self.cooldown_seconds},
                    )
                except Exception:
                    pass

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.last_failure_time = 0.0


_circuit_breaker = EmbeddingCircuitBreaker()


def get_embedding_circuit_breaker() -> EmbeddingCircuitBreaker:
    return _circuit_breaker


def reset_embedding_circuit_breaker() -> None:
    _circuit_breaker.reset()


# ==============================================================================
# Placeholder Detection
# ==============================================================================

def is_placeholder_embedding(vector: List[float]) -> bool:
    """Detects legacy placeholder embeddings (e.g. constant 0.1 or 0.0 vectors)."""
    if not vector or len(vector) != EXPECTED_EMBEDDING_DIM:
        return True
    first_val = vector[0]
    if all(abs(x - first_val) < 1e-6 for x in vector):
        return True
    return False


# ==============================================================================
# Core Embedding Generation
# ==============================================================================

async def _call_provider_with_retries(
    cleaned_text: str,
    model: str,
    expected_dim: int,
    api_key: str,
) -> tuple[List[float], bool]:
    """
    Executes raw embedding call with timeouts, bounded exponential backoff retries,
    circuit breaker protection, and strict production synthetic vector prevention.
    """
    is_production = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
    is_testing = os.getenv("ENVIRONMENT") == "test" or os.getenv("TESTING") == "true"
    allow_fake = os.getenv("ALLOW_FAKE_VECTORS", "false").lower() in ("true", "1")
    is_mock_key = api_key.startswith("test-") or api_key.startswith("mock-")

    # In tests, use smaller backoff to keep test execution snappy
    initial_backoff = 0.01 if is_testing else INITIAL_BACKOFF_SECONDS

    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            await _circuit_breaker.before_execution()

            genai.configure(api_key=api_key)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    genai.embed_content,
                    model=model,
                    content=cleaned_text,
                    output_dimensionality=expected_dim,
                ),
                timeout=PROVIDER_TIMEOUT_SECONDS,
            )

            if not response or "embedding" not in response:
                raise EmbeddingError(f"Embedding provider '{model}' returned empty response.")

            await _circuit_breaker.record_success()
            return response["embedding"], False

        except EmbeddingCircuitBreakerOpenError:
            # Circuit breaker is OPEN: do not retry, fast-fail
            raise

        except Exception as err:
            last_error = err

            # If transient error and retries remain, back off and retry first
            if attempt < MAX_RETRIES and is_transient_error(err):
                delay = initial_backoff * (2 ** attempt) + random.uniform(0.001, 0.01)
                logger.warning(
                    f"Transient embedding failure on attempt {attempt + 1}/{MAX_RETRIES + 1} "
                    f"({sanitize_provider_error(err)}). Retrying in {delay:.2f}s."
                )
                await asyncio.sleep(delay)
                continue

            # Strict policy check: Synthetic vectors are STRICTLY FORBIDDEN in production
            if not is_production and allow_fake and (is_mock_key or is_testing):
                words = [w.strip(".,?!\"'()") for w in cleaned_text.lower().split() if w.strip(".,?!\"'()")]
                vec = np.zeros(expected_dim, dtype=np.float32)
                for w in words:
                    seed = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                    rng = np.random.RandomState(seed)
                    vec += rng.randn(expected_dim).astype(np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                else:
                    rng = np.random.RandomState(42)
                    vec = rng.randn(expected_dim).astype(np.float32)
                    vec = vec / np.linalg.norm(vec)
                return vec.tolist(), True

            await _circuit_breaker.record_failure(err)

            # Terminal error on non-transient or exhausted retries
            sanitized_msg = sanitize_provider_error(err)
            logger.error(
                f"Terminal embedding generation failure for model '{model}': {sanitized_msg}",
                extra={"error_type": type(err).__name__, "sanitized_error": sanitized_msg},
            )
            raise EmbeddingError(sanitized_msg) from err

    # Fallback terminal raise
    sanitized_msg = sanitize_provider_error(last_error or RuntimeError("Unknown error"))
    raise EmbeddingError(sanitized_msg)


async def generate_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    expected_dim: int = EXPECTED_EMBEDDING_DIM,
) -> List[float]:
    """
    Generates real, normalized semantic embeddings using Gemini models.

    Production Guarantees:
    1. Single-flight request deduplication: Coalesces identical concurrent calls.
    2. Versioned namespaced caching: Keys include model, dimension, and preprocessing version.
    3. Bounded exponential retries: Retries transient rate-limits and timeouts.
    4. Circuit breaker protection: Fast-fails during provider outages.
    5. Error sanitization: Prevents leaking raw API keys or internal trace dumps.
    6. Strict production policy: Synthetic vectors strictly rejected in production.
    7. Full dimensionality and numerical validation (no NaN/Inf, no placeholders).
    """
    if not text or not isinstance(text, str) or not text.strip():
        raise ValueError("Cannot generate embedding for empty or blank text.")

    cleaned_text = text.strip()
    text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()

    # Build versioned cache key
    cache_key = build_versioned_cache_key(
        namespace="emb",
        version=EMBEDDING_MODEL_VERSION,
        model=model,
        dim=expected_dim,
        preprocessing_version=PREPROCESSING_VERSION,
        identifier=text_hash,
    )

    # Check cache first
    cached_vector = await get_cache(cache_key)
    if cached_vector:
        if (
            isinstance(cached_vector, list)
            and len(cached_vector) == expected_dim
            and not is_placeholder_embedding(cached_vector)
            and all(math.isfinite(x) for x in cached_vector)
        ):
            return cached_vector
        else:
            logger.warning(f"Purging invalid/corrupt cached embedding for key: {cache_key}")

    # Deduplicate concurrent execution for the same cache key
    async def _execute_embedding():
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EmbeddingError(
                "Embedding client not configured: GEMINI_API_KEY is missing from environment."
            )

        vector, is_synthetic = await _call_provider_with_retries(
            cleaned_text=cleaned_text,
            model=model,
            expected_dim=expected_dim,
            api_key=api_key,
        )

        # 4. Strict Dimensionality Verification
        if len(vector) != expected_dim:
            raise EmbeddingDimensionError(
                f"Unexpected embedding dimension: got {len(vector)}, expected {expected_dim} to match PostgreSQL VECTOR(768)."
            )

        # 5. Numerical Sanity Verification (no NaN, Inf)
        if not all(math.isfinite(x) for x in vector):
            raise EmbeddingNumericalError("Invalid embedding values: vector contains non-finite numbers (NaN or Inf).")

        # 6. Reject placeholder vectors
        if is_placeholder_embedding(vector):
            raise EmbeddingError("Provider returned a placeholder/uniform constant vector.")

        # 7. Never cache synthetic vectors or placeholders
        is_production = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
        if is_production and is_synthetic:
            raise EmbeddingError("Policy Violation: Synthetic vectors are strictly forbidden in production.")

        if is_synthetic:
            logger.info(
                f"Bypassing cache for synthetic/simulated embedding (key: '{cache_key}'). "
                "Policy: Failed or synthetic embeddings must never be cached."
            )
            return vector

        if is_placeholder_or_synthetic_embedding(vector, expected_dim=expected_dim):
            logger.warning(f"Refusing to cache placeholder or synthetic embedding for key: {cache_key}")
            return vector

        # Cache verified real production embeddings (7-day deliberate TTL)
        await set_cache(
            cache_key,
            vector,
            ttl_seconds=CacheTTL.SEMANTIC_EMBEDDING,
            bypassable=True,
            is_synthetic=False,
        )

        return vector

    return await _single_flight.execute(cache_key, _execute_embedding)


# ==============================================================================
# Model-Version Migration Utility
# ==============================================================================

async def reembed_existing_memories(database_manager) -> int:
    """
    Migration utility: Scans stored conversational memories and re-embeds
    any records containing legacy constant vectors ([0.1] * 768), mismatched dimensions,
    or outdated embedding model/preprocessing configuration versions.
    Returns the count of successfully updated memories.
    """
    db_data = database_manager._read_local()
    memories = db_data.get("memories", [])
    updated_count = 0

    for mem in memories:
        existing_emb = mem.get("embedding", [])
        existing_version = mem.get("embedding_version")

        needs_reembed = (
            is_placeholder_embedding(existing_emb)
            or len(existing_emb) != EXPECTED_EMBEDDING_DIM
            or existing_version != EMBEDDING_VERSION
        )

        if needs_reembed:
            text = mem.get("text", "")
            if text:
                try:
                    new_emb = await generate_embedding(text)
                    mem["embedding"] = new_emb
                    mem["embedding_version"] = EMBEDDING_VERSION
                    mem["updated_at"] = time.time()
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"Could not re-embed memory id '{mem.get('id', 'unknown')}': {e}")

    if updated_count > 0:
        database_manager._write_local(db_data)
        logger.info(f"Re-embedded {updated_count} memories to version {EMBEDDING_VERSION}.")

    return updated_count
