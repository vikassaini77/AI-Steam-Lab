import os
import pytest
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from unittest.mock import MagicMock
from app.core_backend.database.pgvector_db import PGVectorManager
from app.core_backend.database.supabase_db import DatabaseManager
from app.ai_agent.tutor_service import AITutorService
from app.ai_agent.embedding_service import generate_embedding

TARGET_MEMORY = "Newton's second law: F = m * a relates net force to mass and acceleration."
DISTRACTOR_QUANTUM = "Quantum superposition allows particles to exist in multiple physical states simultaneously until measured."
DISTRACTOR_COOKING = "Combine two cups of warm water with active dry yeast and olive oil."


@pytest.mark.asyncio
async def test_exact_technical_term_retrieval():
    """
    Verification: Query with an exact technical term/formula ('F = m * a').
    Stage 2 (Keyword search) detects the exact formula and RRF ranks the target memory #1.
    """
    user_id = "test_user_exact_term"
    db = PGVectorManager()

    emb_target = await generate_embedding(TARGET_MEMORY)
    emb_quantum = await generate_embedding(DISTRACTOR_QUANTUM)
    emb_cooking = await generate_embedding(DISTRACTOR_COOKING)

    db.save_memory("sess_tech", TARGET_MEMORY, emb_target, user_id=user_id)
    db.save_memory("sess_tech", DISTRACTOR_QUANTUM, emb_quantum, user_id=user_id)
    db.save_memory("sess_tech", DISTRACTOR_COOKING, emb_cooking, user_id=user_id)

    # Query matching exact formula
    query_exact = "F = m * a"
    query_emb = await generate_embedding(query_exact)

    results = db.search_memories(
        query_embedding=query_emb,
        query_text=query_exact,
        user_id=user_id,
        top_k=3,
        return_metadata=True,
    )

    assert len(results) >= 1
    top_doc = results[0]
    assert top_doc["text"] == TARGET_MEMORY
    assert top_doc["id"] is not None
    assert top_doc["rrf_score"] > 0.0

    # Confirm separate measurable stages are recorded
    assert top_doc["keyword_rank"] == 1
    assert top_doc["keyword_score"] > 0.0
    assert top_doc["semantic_rank"] is not None


@pytest.mark.asyncio
async def test_paraphrase_query_retrieval():
    """
    Verification: Query with a paraphrase that does NOT use the exact formula or words.
    Stage 1 (Semantic vector search) identifies conceptual similarity and RRF ranks target memory #1.
    """
    user_id = "test_user_paraphrase"
    db = PGVectorManager()

    emb_target = await generate_embedding(TARGET_MEMORY)
    emb_quantum = await generate_embedding(DISTRACTOR_QUANTUM)
    emb_cooking = await generate_embedding(DISTRACTOR_COOKING)

    db.save_memory("sess_para", TARGET_MEMORY, emb_target, user_id=user_id)
    db.save_memory("sess_para", DISTRACTOR_QUANTUM, emb_quantum, user_id=user_id)
    db.save_memory("sess_para", DISTRACTOR_COOKING, emb_cooking, user_id=user_id)

    # Conceptual paraphrase without the formula 'F = m * a'
    query_paraphrase = "How does an object speed up when an external physical push acts on it?"
    query_emb = await generate_embedding(query_paraphrase)

    results = db.search_memories(
        query_embedding=query_emb,
        query_text=query_paraphrase,
        user_id=user_id,
        top_k=3,
        return_metadata=True,
    )

    assert len(results) >= 1
    top_doc = results[0]
    # Semantic search successfully retrieves the target physics memory over baking/quantum
    assert top_doc["text"] == TARGET_MEMORY
    assert top_doc["semantic_rank"] == 1
    assert top_doc["semantic_score"] is not None
    assert top_doc["semantic_score"] > 0.60


@pytest.mark.asyncio
async def test_tenant_ownership_isolation_filter():
    """
    Verification: Confirms that ownership filter prevents User B from accessing User A's memories,
    even when User B queries for the exact technical term.
    """
    user_a = "user_alpha_private"
    user_b = "user_beta_adversary"
    db = PGVectorManager()

    emb_target = await generate_embedding(TARGET_MEMORY)
    db.save_memory("sess_priv", TARGET_MEMORY, emb_target, user_id=user_a)

    query_exact = "F = m * a"
    query_emb = await generate_embedding(query_exact)

    # User B queries exact term of User A's memory
    b_results = db.search_memories(
        query_embedding=query_emb,
        query_text=query_exact,
        user_id=user_b,
        top_k=3,
        return_metadata=True,
    )

    # Must be completely isolated
    assert len(b_results) == 0


@pytest.mark.asyncio
async def test_deduplication_and_rrf_scoring():
    """
    Verification: A document matched by both semantic and keyword stages is deduplicated
    and its RRF score correctly sums both contributions.
    """
    user_id = "test_user_dedup"
    db = PGVectorManager()

    emb_target = await generate_embedding(TARGET_MEMORY)
    doc_id = db.save_memory("sess_dedup", TARGET_MEMORY, emb_target, user_id=user_id)

    query = "Newton's second law F = m * a force and acceleration"
    query_emb = await generate_embedding(query)

    results = db.search_memories(
        query_embedding=query_emb,
        query_text=query,
        user_id=user_id,
        top_k=5,
        return_metadata=True,
    )

    # Target document must appear exactly once (deduplicated)
    matched_target = [r for r in results if r["text"] == TARGET_MEMORY]
    assert len(matched_target) == 1

    doc = matched_target[0]
    # RRF score must be the sum of 1/(60 + sem_rank) + 1/(60 + kw_rank)
    expected_sem_contrib = 1.0 / (60.0 + doc["semantic_rank"])
    expected_kw_contrib = 1.0 / (60.0 + doc["keyword_rank"])
    expected_total_rrf = expected_sem_contrib + expected_kw_contrib
    assert pytest.approx(doc["rrf_score"], rel=1e-4) == expected_total_rrf


@pytest.mark.asyncio
async def test_database_manager_hybrid_parity():
    """
    Verification: Confirms DatabaseManager provides the exact same hybrid retrieval,
    measuring separate stages and RRF fusion parity with PGVectorManager.
    """
    user_id = "test_user_db_manager"
    db = DatabaseManager()

    emb_target = await generate_embedding(TARGET_MEMORY)
    emb_cooking = await generate_embedding(DISTRACTOR_COOKING)

    db.save_memory("sess_db_target", TARGET_MEMORY, emb_target, user_id=user_id)
    db.save_memory("sess_db_cook", DISTRACTOR_COOKING, emb_cooking, user_id=user_id)

    query = "F = m * a"
    query_emb = await generate_embedding(query)

    results = db.search_memories(
        query_embedding=query_emb,
        query_text=query,
        user_id=user_id,
        top_k=2,
        return_metadata=True,
    )

    assert len(results) >= 1
    assert results[0]["text"] == TARGET_MEMORY
    assert results[0]["keyword_rank"] == 1
    assert results[0]["id"] is not None


@pytest.mark.asyncio
async def test_tutor_service_hybrid_retrieval_integration():
    """
    Verification: AITutorService passes normalized query_text to db.search_memories,
    enabling hybrid retrieval in stream_chat and retrieve_memories.
    """
    user_id = "test_user_tutor_hybrid"
    mock_db = MagicMock()
    mock_db.search_memories.return_value = [TARGET_MEMORY]

    tutor = AITutorService(db=mock_db)

    # Retrieve memories through tutor service
    raw_prompt = "   Explain   F = m * a   mechanics  \n\t "
    await tutor.retrieve_memories(prompt=raw_prompt, user_id=user_id)

    # Verify search_memories was called with normalized query_text
    mock_db.search_memories.assert_called_once()
    call_kwargs = mock_db.search_memories.call_args.kwargs
    assert call_kwargs["query_text"] == "Explain F = m * a mechanics"
    assert call_kwargs["user_id"] == user_id
    assert "query_embedding" in call_kwargs
    assert len(call_kwargs["query_embedding"]) == 768
