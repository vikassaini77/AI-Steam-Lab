import os
import math
import numpy as np
import pytest
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv("backend/.env")

from app.ai_agent.embedding_service import (
    generate_embedding,
    reembed_existing_memories,
    is_placeholder_embedding,
    EmbeddingError,
    EmbeddingDimensionError,
    EmbeddingNumericalError,
    EXPECTED_EMBEDDING_DIM,
    EMBEDDING_VERSION,
)
from app.core_backend.database.supabase_db import DatabaseManager

# Fallback test API key if backend/.env is not loaded
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"


def cosine_sim(a, b):
    v_a = np.array(a, dtype=np.float32)
    v_b = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(v_a)
    norm_b = np.linalg.norm(v_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(v_a, v_b) / (norm_a * norm_b))


def test_placeholder_embedding_detection():
    """Detects constant vectors like [0.1] * 768 and [0.0] * 768 as placeholders."""
    assert is_placeholder_embedding([0.1] * EXPECTED_EMBEDDING_DIM) is True
    assert is_placeholder_embedding([0.0] * EXPECTED_EMBEDDING_DIM) is True
    assert is_placeholder_embedding([1.0] * 100) is True  # wrong dim

    # Random non-uniform vector
    np.random.seed(42)
    real_like = np.random.randn(EXPECTED_EMBEDDING_DIM).tolist()
    assert is_placeholder_embedding(real_like) is False


@pytest.mark.asyncio
async def test_empty_input_rejected():
    """Empty or whitespace-only queries must be rejected immediately."""
    with pytest.raises(ValueError) as exc:
        await generate_embedding("")
    assert "empty" in str(exc.value).lower()

    with pytest.raises(ValueError) as exc:
        await generate_embedding("   \n\t  ")
    assert "empty" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_unexpected_dimension_rejected():
    """Vectors not matching EXPECTED_EMBEDDING_DIM (768) must raise EmbeddingDimensionError."""
    fake_response = {"embedding": [0.05] * 512}  # 512 instead of 768
    with patch("google.generativeai.embed_content", return_value=fake_response):
        with pytest.raises(EmbeddingDimensionError) as exc:
            await generate_embedding("test query", model="mock-model")
        assert "512" in str(exc.value)
        assert str(EXPECTED_EMBEDDING_DIM) in str(exc.value)


@pytest.mark.asyncio
async def test_non_finite_values_rejected():
    """Vectors containing NaN or Infinity must raise EmbeddingNumericalError."""
    bad_vector = [0.01] * 768
    bad_vector[10] = float("nan")
    fake_response = {"embedding": bad_vector}
    with patch("google.generativeai.embed_content", return_value=fake_response):
        with pytest.raises(EmbeddingNumericalError):
            await generate_embedding("test query", model="mock-model")


@pytest.mark.asyncio
async def test_namespaced_versioned_caching():
    """Successful embedding calls should be cached using versioned, namespaced keys."""
    np.random.seed(123)
    mock_vec = np.random.randn(EXPECTED_EMBEDDING_DIM).tolist()
    fake_response = {"embedding": mock_vec}

    with patch("google.generativeai.embed_content", return_value=fake_response) as mock_embed:
        # First call hits mock
        res1 = await generate_embedding("Unique test sentence for cache 12345")
        assert len(res1) == EXPECTED_EMBEDDING_DIM
        assert mock_embed.call_count == 1

        # Second call hits cache
        res2 = await generate_embedding("Unique test sentence for cache 12345")
        assert res1 == res2
        assert mock_embed.call_count == 1  # Not called again!


@pytest.mark.asyncio
async def test_real_embedding_semantic_separation():
    """
    Verification: Compare embeddings of related and unrelated physics questions.
    Related questions must have significantly higher cosine similarity than unrelated.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key.startswith("test-") or api_key.startswith("mock-") or not api_key:
        pytest.skip("Skipping live Gemini embedding test: non-production mock credentials in use.")

    # 1. Related physics questions
    q_physics_1 = "What is Newton's second law of motion relating force and acceleration?"
    q_physics_2 = "How does net force equal mass times acceleration in classical mechanics?"

    # 2. Unrelated question
    q_unrelated = "How do you bake artisan sourdough bread with whole wheat flour?"

    emb_p1 = await generate_embedding(q_physics_1)
    emb_p2 = await generate_embedding(q_physics_2)
    emb_un = await generate_embedding(q_unrelated)

    sim_related = cosine_sim(emb_p1, emb_p2)
    sim_unrelated = cosine_sim(emb_p1, emb_un)

    # Assert related questions have high similarity and clear delta over unrelated
    assert sim_related > 0.60, f"Expected related similarity > 0.60, got {sim_related}"
    assert sim_unrelated < 0.55, f"Expected unrelated similarity < 0.55, got {sim_unrelated}"
    assert sim_related > sim_unrelated + 0.15, "Related similarity must be noticeably higher than unrelated"


@pytest.mark.asyncio
async def test_labeled_retrieval_ranking():
    """
    Verification: Evaluate retrieval results against a labeled memory set.
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key.startswith("test-") or api_key.startswith("mock-") or not api_key:
        pytest.skip("Skipping live Gemini embedding test: non-production mock credentials in use.")

    db = DatabaseManager()
    user_id = "test_user_eval_ranking"

    # Seed labeled memories
    mem_physics_target = "Newton's second law: F = m * a states that acceleration is proportional to net force."
    mem_pendulum = "The period of a simple pendulum is T = 2*pi*sqrt(L/g), independent of mass."
    mem_cooking = "Mix two cups of flour with baking powder, butter, and warm milk."

    emb_target = await generate_embedding(mem_physics_target)
    emb_pendulum = await generate_embedding(mem_pendulum)
    emb_cooking = await generate_embedding(mem_cooking)

    db.save_memory("sess_1", mem_physics_target, emb_target, user_id=user_id)
    db.save_memory("sess_1", mem_pendulum, emb_pendulum, user_id=user_id)
    db.save_memory("sess_1", mem_cooking, emb_cooking, user_id=user_id)

    # Query for Newton's 2nd law
    query = "Explain how force causes acceleration when mass is constant"
    query_emb = await generate_embedding(query)

    ranked_results = db.search_memories(query_emb, user_id=user_id, top_k=3)

    assert len(ranked_results) >= 2
    # The top ranked memory MUST be the target Newton's law memory
    assert ranked_results[0] == mem_physics_target
    # The cooking memory should NOT be the top result
    assert ranked_results[0] != mem_cooking


@pytest.mark.asyncio
async def test_reembed_existing_memories_migration():
    """
    Tests that reembed_existing_memories identifies legacy constant [0.1]*768 vectors
    and updates them with real embeddings.
    """
    import uuid
    db = DatabaseManager()
    user_id = f"test_mig_{uuid.uuid4().hex[:8]}"

    # Inject legacy placeholder memory
    db.save_memory("sess_mig", "Energy is conserved in closed physical systems.", [0.1] * 768, user_id=user_id)

    # Confirm it is recognized as placeholder
    local_data = db._read_local()
    legacy_record = next(m for m in local_data["memories"] if m.get("user_id") == user_id)
    assert is_placeholder_embedding(legacy_record["embedding"]) is True

    # Run migration
    updated = await reembed_existing_memories(db)
    assert updated >= 1

    # Verify record was upgraded
    upgraded_data = db._read_local()
    upgraded_record = next(m for m in upgraded_data["memories"] if m.get("user_id") == user_id)
    assert is_placeholder_embedding(upgraded_record["embedding"]) is False
    assert len(upgraded_record["embedding"]) == EXPECTED_EMBEDDING_DIM
    assert upgraded_record.get("embedding_version") == EMBEDDING_VERSION
