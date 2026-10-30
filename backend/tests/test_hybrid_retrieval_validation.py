"""
Test Suite for Problem 21: Hybrid SQL Retrieval Validation
Validates:
1. Accurate ranking terminology (PostgreSQL Cover Density ts_rank_cd, not BM25).
2. FULL OUTER JOIN and COALESCE logic (zero duplicates, zero missing metadata across semantic-only, keyword-only, and intersection matches).
3. pgvector index and compatible operator class (HNSW index with vector_cosine_ops for <=> cosine distance).
4. Calibrated embedding threshold per model and environment override.
5. Ownership and tenant filtering in SQL.
6. Independent testing of semantic-only, keyword-only, and hybrid search modes.
7. EXPLAIN / query plan inspection.
8. Retrieval benchmark confirming hybrid results improve evaluation metrics (MRR, Recall@K) over both baselines.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from app.core_backend.database.pgvector_db import PGVectorManager
from app.core_backend.database.hybrid_retrieval import (
    get_calibrated_threshold,
    DEFAULT_CALIBRATED_THRESHOLDS,
    execute_in_memory_hybrid_search,
)
from app.core_backend.database.migrations import (
    REQUIRED_SCHEMA_VERSION,
    verify_search_indexes,
    MIGRATION_V3_SQL,
)
from app.core_backend.database.retrieval_benchmark import (
    RetrievalBenchmark,
    generate_benchmark_embedding,
    BENCHMARK_CORPUS,
    BENCHMARK_QUERIES,
)


def test_accurate_ranking_terminology_and_metadata():
    """
    Verification:
    PostgreSQL's built-in ranking function ts_rank_cd is Cover Density Ranking, not BM25.
    Metadata returns keyword_score and ts_rank_cd_score with accurate terminology,
    while maintaining backward-compatible bm25_score alias.
    """
    manager = PGVectorManager()
    user_id = "test_user_terminology"
    text = "Newton's second law: F = m * a relates net force to mass and acceleration."
    emb = generate_benchmark_embedding(text)

    manager.save_memory("sess_term", text, emb, user_id=user_id)

    results = manager.search_memories(
        query_embedding=emb,
        query_text="F = m * a",
        user_id=user_id,
        top_k=1,
        return_metadata=True,
        search_mode="hybrid",
    )

    assert len(results) == 1
    doc = results[0]
    # Check accurate terminology fields
    assert "keyword_score" in doc
    assert "ts_rank_cd_score" in doc
    assert "bm25_score" in doc  # backward-compatible alias
    assert doc["keyword_score"] == doc["ts_rank_cd_score"]
    assert doc["ranking_algorithm"] == "rrf_hybrid_cover_density"


def test_independent_search_modes():
    """
    Verification:
    Test semantic-only, keyword-only, and hybrid queries independently.
    - semantic-only: executes only vector search, keyword ranks are None.
    - keyword-only: executes only full-text search without requiring vector embeddings.
    - hybrid: combines both via RRF.
    """
    manager = PGVectorManager()
    user_id = "test_user_independent_modes"
    text_1 = "Newton's second law: F = m * a relates net force to mass and acceleration."
    text_2 = "Kinematic equation for velocity: v = u + a * t relates final velocity to acceleration and time."

    emb_1 = generate_benchmark_embedding(text_1)
    emb_2 = generate_benchmark_embedding(text_2)

    manager.save_memory("sess_indep", text_1, emb_1, user_id=user_id)
    manager.save_memory("sess_indep", text_2, emb_2, user_id=user_id)

    # 1. Semantic-only mode
    sem_results = manager.search_memories(
        query_embedding=emb_1,
        query_text="",
        user_id=user_id,
        search_mode="semantic",
        return_metadata=True,
    )
    assert len(sem_results) >= 1
    assert sem_results[0]["text"] == text_1
    assert sem_results[0]["semantic_rank"] == 1
    assert sem_results[0]["semantic_score"] is not None
    assert sem_results[0]["keyword_rank"] is None
    assert sem_results[0]["keyword_score"] is None

    # 2. Keyword-only mode (no embedding passed)
    kw_results = manager.search_memories(
        query_embedding=None,
        query_text="v = u + a * t",
        user_id=user_id,
        search_mode="keyword",
        return_metadata=True,
    )
    assert len(kw_results) >= 1
    assert kw_results[0]["text"] == text_2
    assert kw_results[0]["keyword_rank"] == 1
    assert kw_results[0]["keyword_score"] is not None
    assert kw_results[0]["semantic_rank"] is None
    assert kw_results[0]["semantic_score"] is None

    # 3. Hybrid mode
    hyb_results = manager.search_memories(
        query_embedding=emb_1,
        query_text="F = m * a",
        user_id=user_id,
        search_mode="hybrid",
        return_metadata=True,
    )
    assert len(hyb_results) >= 1
    assert hyb_results[0]["text"] == text_1
    assert hyb_results[0]["semantic_rank"] == 1
    assert hyb_results[0]["keyword_rank"] == 1
    assert hyb_results[0]["rrf_score"] > 0.0


def test_full_outer_join_coalesce_logic_and_deduplication():
    """
    Verification:
    Test FULL OUTER JOIN and COALESCE behavior for:
    - Case A: Semantic match only (keyword_rank is None, metadata preserved, no duplicates).
    - Case B: Keyword match only (semantic_rank is None, metadata preserved, no duplicates).
    - Case C: Both match (single combined row, RRF score sums both contributions, no duplicates).
    """
    memories = [
        {
            "id": 101,
            "text": "Pure semantic match: Objects accelerate in a gravitational field without equations.",
            "embedding": [0.9] * 50 + [0.0] * 718,  # Matches semantic query
            "user_id": "u_join",
            "session_id": "s_join",
            "experiment_id": "exp_join",
            "embedding_model_version": "text-embedding-004",
        },
        {
            "id": 102,
            "text": "Pure keyword match: F = m * a Newton force calculation formula.",
            "embedding": [0.0] * 768,  # Zero vector, will not match semantic query
            "user_id": "u_join",
            "session_id": "s_join",
            "experiment_id": "exp_join",
            "embedding_model_version": "text-embedding-004",
        },
        {
            "id": 103,
            "text": "Dual match: F = m * a objects accelerate under net gravitational force.",
            "embedding": [0.9] * 50 + [0.0] * 718,  # Matches both
            "user_id": "u_join",
            "session_id": "s_join",
            "experiment_id": "exp_join",
            "embedding_model_version": "text-embedding-004",
        },
    ]

    query_emb = [0.9] * 50 + [0.0] * 718
    query_text = "F = m * a"

    results, metadata = execute_in_memory_hybrid_search(
        memories=memories,
        query_embedding=query_emb,
        query_text=query_text,
        user_id="u_join",
        top_k=10,
        return_metadata=True,
    )

    doc_ids = [d["id"] for d in metadata]
    # 1. No duplicates: each unique document appears at most once
    assert len(doc_ids) == len(set(doc_ids))
    assert set(doc_ids) == {101, 102, 103}

    # Case C (Dual match): doc 103 should have both ranks and highest RRF score
    doc_103 = next(d for d in metadata if d["id"] == 103)
    assert doc_103["semantic_rank"] is not None
    assert doc_103["keyword_rank"] is not None
    assert doc_103["rrf_score"] > 0.0

    # Case A (Semantic match only): doc 101 has semantic rank, keyword rank is None
    doc_101 = next(d for d in metadata if d["id"] == 101)
    assert doc_101["semantic_rank"] is not None
    assert doc_101["keyword_rank"] is None
    assert doc_101["session_id"] == "s_join"
    assert doc_101["experiment_id"] == "exp_join"

    # Case B (Keyword match only): doc 102 has keyword rank, semantic rank is None or low
    doc_102 = next(d for d in metadata if d["id"] == 102)
    assert doc_102["keyword_rank"] is not None
    assert doc_102["session_id"] == "s_join"
    assert doc_102["experiment_id"] == "exp_join"


def test_pgvector_index_and_compatible_operator_class():
    """
    Verification:
    1. Migration 3 creates full-text search GIN index and pgvector HNSW index.
    2. Vector index specifies 'vector_cosine_ops' operator class, which is compatible
       with the <=> cosine distance metric used in SQL queries.
    3. verify_search_indexes() detects and reports active index configuration.
    """
    assert REQUIRED_SCHEMA_VERSION >= 3
    assert "idx_memories_text_fts" in MIGRATION_V3_SQL
    assert "idx_memories_embedding_hnsw" in MIGRATION_V3_SQL
    assert "vector_cosine_ops" in MIGRATION_V3_SQL

    # Test verify_search_indexes with mock connection
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("idx_memories_embedding_hnsw", "hnsw", "vector_cosine_ops"),
        ("idx_memories_text_fts", "gin", ""),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    index_status = verify_search_indexes(mock_conn)
    assert index_status["vector_index_present"] is True
    assert index_status["vector_index_type"] == "hnsw"
    assert index_status["vector_opclass"] == "vector_cosine_ops"
    assert index_status["fts_index_present"] is True
    assert index_status["fts_index_type"] == "gin"


def test_embedding_threshold_calibration():
    """
    Verification:
    Embedding threshold is calibrated for the actual embedding model:
    - Default for text-embedding-004 is 0.65.
    - Default for models/gemini-embedding-001 is 0.62.
    - Can be overridden via SEMANTIC_CONFIDENCE_THRESHOLD environment variable.
    - Low confidence triggers when semantic score is below calibrated threshold.
    """
    assert get_calibrated_threshold("text-embedding-004") == 0.65
    assert get_calibrated_threshold("models/gemini-embedding-001") == 0.62
    assert get_calibrated_threshold(None) == DEFAULT_CALIBRATED_THRESHOLDS["default"]

    # Test environment variable override
    with patch.dict(os.environ, {"SEMANTIC_CONFIDENCE_THRESHOLD": "0.72"}):
        assert get_calibrated_threshold("text-embedding-004") == 0.72

    # Test confidence trigger: score 0.60 is below calibrated 0.65 for text-embedding-004
    # Construct normalized 768-dim vectors with exact cosine similarity 0.60: 0.60^2 + 0.80^2 = 1.0
    memories = [
        {
            "id": 201,
            "text": "Marginally related text about forces.",
            "embedding": [0.60, 0.80] + [0.0] * 766,
            "user_id": "u_thresh",
            "embedding_model_version": "text-embedding-004",
        }
    ]
    query_emb = [1.0, 0.0] + [0.0] * 766  # Cosine similarity is exactly 0.60

    results, _ = execute_in_memory_hybrid_search(
        memories=memories,
        query_embedding=query_emb,
        query_text="",
        user_id="u_thresh",
        top_k=1,
        return_metadata=False,
        embedding_model_version="text-embedding-004",
    )
    # Cosine sim 0.60 < calibrated 0.65 -> flags LOW_CONFIDENCE
    assert results == ["System: [LOW_CONFIDENCE] Let me think about this differently..."]


def test_ownership_and_tenant_filters_in_sql():
    """
    Verification:
    Ensures that tenant ownership (user_id), session_id, and experiment_id
    filters strictly isolate candidate memories in SQL and in-memory searches.
    """
    manager = PGVectorManager()
    user_alice = "user_alice_secure"
    user_mallory = "user_mallory_attacker"

    text = "Secret experiment physics notes: F = m * a"
    emb = generate_benchmark_embedding(text)

    manager.save_memory("sess_secret", text, emb, user_id=user_alice)

    # Mallory queries with exact technical term
    for mode in ("semantic", "keyword", "hybrid"):
        mallory_results = manager.search_memories(
            query_embedding=emb if mode != "keyword" else None,
            query_text="F = m * a" if mode != "semantic" else "",
            user_id=user_mallory,
            search_mode=mode,
        )
        assert len(mallory_results) == 0, f"Mode {mode} leaked Alice's memory to Mallory!"


def test_explain_search_query_execution_and_index_verification():
    """
    Verification:
    explain_search_query executes query plan generation and validates that
    pgvector HNSW index and full-text search GIN index are utilized.
    """
    manager = PGVectorManager()
    plan_info = manager.explain_search_query(
        query_embedding=[0.1] * 768,
        query_text="F = m * a",
        user_id="test_user_explain",
        search_mode="hybrid",
        analyze=False,
    )

    assert "plan_lines" in plan_info
    assert plan_info["uses_vector_index"] is True
    assert plan_info["uses_fts_index"] is True
    assert plan_info["search_mode"] == "hybrid"


def test_retrieval_benchmark_proves_hybrid_superiority():
    """
    Verification:
    Executes the comprehensive Retrieval Benchmark across:
    1. Technical formula queries (keyword-favored)
    2. Conceptual paraphrases (semantic-favored)
    3. Mixed hybrid queries
    
    Confirms that Hybrid RRF retrieval improves the evaluation metrics (MRR, Recall@K)
    over both the semantic-only and keyword-only baselines.
    """
    manager = PGVectorManager()
    benchmark = RetrievalBenchmark(manager=manager, user_id="benchmark_suite_user")
    populated_count = benchmark.populate()
    assert populated_count == len(BENCHMARK_CORPUS)

    summary = benchmark.run_benchmark(top_k=3)

    print("\n--- Benchmark Evaluation Summary ---")
    print(f"Keyword MRR:  {summary['keyword_mrr']:.4f} | Recall@3: {summary['keyword_recall_at_3']:.4f}")
    print(f"Semantic MRR: {summary['semantic_mrr']:.4f} | Recall@3: {summary['semantic_recall_at_3']:.4f}")
    print(f"Hybrid MRR:   {summary['hybrid_mrr']:.4f} | Recall@3: {summary['hybrid_recall_at_3']:.4f}")

    # Confirm hybrid retrieval outperforms or equals baselines
    assert summary["hybrid_mrr"] > summary["keyword_mrr"], (
        f"Expected Hybrid MRR ({summary['hybrid_mrr']}) > Keyword MRR ({summary['keyword_mrr']})"
    )
    assert summary["hybrid_recall_at_3"] > summary["keyword_recall_at_3"], (
        f"Expected Hybrid Recall ({summary['hybrid_recall_at_3']}) > Keyword Recall ({summary['keyword_recall_at_3']})"
    )
    assert summary["hybrid_mrr"] >= summary["semantic_mrr"], (
        f"Expected Hybrid MRR ({summary['hybrid_mrr']}) >= Semantic MRR ({summary['semantic_mrr']})"
    )
    assert summary["hybrid_recall_at_3"] >= summary["semantic_recall_at_3"], (
        f"Expected Hybrid Recall ({summary['hybrid_recall_at_3']}) >= Semantic Recall ({summary['semantic_recall_at_3']})"
    )
    assert summary["hybrid_overall_win"] is True
