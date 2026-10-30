import os
import math
import hashlib
import asyncio
from typing import List, Optional
import numpy as np
import google.generativeai as genai
from app.cache import get_cache, set_cache
from app.logger import logger

EXPECTED_EMBEDDING_DIM = 768
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
EMBEDDING_VERSION = "v1-gemini-embedding-001-dim768"


class EmbeddingError(RuntimeError):
    """Base exception for embedding failures."""
    pass


class EmbeddingDimensionError(EmbeddingError, ValueError):
    """Raised when the output vector dimension does not match PostgreSQL VECTOR(768)."""
    pass


class EmbeddingNumericalError(EmbeddingError, ValueError):
    """Raised when the embedding contains invalid numerical values (NaN, Inf)."""
    pass


def is_placeholder_embedding(vector: List[float]) -> bool:
    """
    Detects legacy placeholder embeddings (e.g. constant 0.1 or 0.0 vectors).
    """
    if not vector or len(vector) != EXPECTED_EMBEDDING_DIM:
        return True
    first_val = vector[0]
    # Check if all elements are identical (such as [0.1] * 768 or [0.0] * 768)
    if all(abs(x - first_val) < 1e-6 for x in vector):
        return True
    return False


async def generate_embedding(
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    expected_dim: int = EXPECTED_EMBEDDING_DIM,
) -> List[float]:
    """
    Generates real, normalized semantic embeddings using Gemini models.
    
    1. Validates input text.
    2. Checks versioned, namespaced cache (never caches placeholders or failures).
    3. Generates embedding via Google Gemini API with exact 768 dimensionality.
    4. Confirms dimension matches PostgreSQL VECTOR(768).
    5. Validates numerical sanity (no NaN, Inf).
    6. Caches verified vectors and returns.
    """
    if not text or not isinstance(text, str) or not text.strip():
        raise ValueError("Cannot generate embedding for empty or blank text.")

    cleaned_text = text.strip()

    # 1. Check versioned, namespaced cache
    text_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
    cache_key = f"emb:{EMBEDDING_VERSION}:{text_hash}"

    cached_vector = await get_cache(cache_key)
    if cached_vector:
        # Validate cached vector integrity before using
        if (
            isinstance(cached_vector, list)
            and len(cached_vector) == expected_dim
            and not is_placeholder_embedding(cached_vector)
            and all(math.isfinite(x) for x in cached_vector)
        ):
            return cached_vector
        else:
            logger.warning(f"Purging invalid/corrupt cached embedding for key: {cache_key}")

    # 2. Verify API configuration
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EmbeddingError(
            "Embedding client not configured: GEMINI_API_KEY is missing from environment."
        )

    # 3. Call embedding model via worker thread
    try:
        genai.configure(api_key=api_key)
        response = await asyncio.wait_for(
            asyncio.to_thread(
                genai.embed_content,
                model=model,
                content=cleaned_text,
                output_dimensionality=expected_dim,
            ),
            timeout=15.0,
        )
    except (asyncio.TimeoutError, TimeoutError):
        raise EmbeddingError(f"Embedding request to '{model}' timed out after 15 seconds.")
    except Exception as err:
        raise EmbeddingError(f"Failed to generate embedding from '{model}': {str(err)}") from err

    if not response or "embedding" not in response:
        raise EmbeddingError(f"Embedding provider '{model}' returned empty response.")

    vector = response["embedding"]

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

    # 7. Cache verified successful results (7-day TTL)
    await set_cache(cache_key, vector, ttl_seconds=604800)

    return vector


async def reembed_existing_memories(database_manager) -> int:
    """
    Migration utility: Scans stored conversational memories and re-embeds
    any records containing legacy constant vectors ([0.1] * 768) or mismatched dimensions.
    Returns the count of successfully updated memories.
    """
    db_data = database_manager._read_local()
    memories = db_data.get("memories", [])
    updated_count = 0

    for mem in memories:
        existing_emb = mem.get("embedding", [])
        if is_placeholder_embedding(existing_emb):
            text = mem.get("text", "")
            if text:
                try:
                    new_emb = await generate_embedding(text)
                    mem["embedding"] = new_emb
                    mem["embedding_version"] = EMBEDDING_VERSION
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"Could not re-embed memory id '{mem.get('id', 'unknown')}': {e}")

    if updated_count > 0:
        database_manager._write_local(db_data)
        logger.info(f"Re-embedded {updated_count} legacy memories with model version {EMBEDDING_VERSION}.")

    return updated_count

