"""
Tests for Problem 20: Memory Records Ownership, Scope, and Lifecycle Controls.
Verifies:
- Strict cross-account tenant isolation in retrieval.
- Account-level deletion workflows and post-deletion retrieval verification.
- Session-scoped memory deletion.
- Single-memory deletion with ownership enforcement.
- Data export workflow for account data portability.
- Retention periods (TTL) and expiration cleanup.
- API endpoints for memory lifecycle management.
"""
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.database.pgvector_db import PGVectorManager, DatabaseMode

client = TestClient(app)


def test_cross_account_memory_retrieval_isolation():
    """
    Verification:
    Test isolation across accounts: User A and User B memories are isolated.
    Retrieval for User A returns ONLY User A's memories, even with identical query embeddings.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb_physics = [0.1] * 768

    # Save memory for User A
    doc_a = db.save_memory(
        session_id="sess_a",
        text="User A notes on Newton's First Law and inertia",
        embedding=emb_physics,
        user_id="student_alice",
        experiment_id="exp_pendulum",
    )

    # Save memory for User B with identical embedding
    doc_b = db.save_memory(
        session_id="sess_b",
        text="User B notes on Quantum Entanglement and spin",
        embedding=emb_physics,
        user_id="student_bob",
        experiment_id="exp_quantum",
    )

    # Search as student_alice: MUST only retrieve Alice's memory
    results_a = db.search_memories(
        query_embedding=emb_physics,
        query_text="Newton inertia",
        user_id="student_alice",
        return_metadata=True,
    )
    assert len(results_a) == 1
    assert results_a[0]["user_id"] == "student_alice"
    assert "Newton" in results_a[0]["text"]
    assert "Quantum" not in results_a[0]["text"]

    # Search as student_bob: MUST only retrieve Bob's memory
    results_b = db.search_memories(
        query_embedding=emb_physics,
        query_text="Quantum spin",
        user_id="student_bob",
        return_metadata=True,
    )
    assert len(results_b) == 1
    assert results_b[0]["user_id"] == "student_bob"
    assert "Quantum" in results_b[0]["text"]
    assert "Newton" not in results_b[0]["text"]


def test_account_deletion_removes_memories_from_subsequent_retrieval():
    """
    Verification:
    Verify that deleting a user's memories removes them from subsequent retrieval,
    while preserving other users' memories intact.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.2] * 768

    db.save_memory(session_id="s1", text="Alice memory 1", embedding=emb, user_id="student_alice")
    db.save_memory(session_id="s2", text="Alice memory 2", embedding=emb, user_id="student_alice")
    db.save_memory(session_id="s3", text="Bob memory 1", embedding=emb, user_id="student_bob")

    # Verify Alice has 2 memories retrievable
    res_before = db.search_memories(query_embedding=emb, user_id="student_alice")
    assert len(res_before) == 2

    # Execute account-level memory deletion for Alice
    deleted_count = db.delete_user_memories(user_id="student_alice")
    assert deleted_count == 2

    # Subsequent retrieval for Alice MUST return empty
    res_after = db.search_memories(query_embedding=emb, user_id="student_alice")
    assert len(res_after) == 0

    # Bob's memories MUST remain completely intact
    res_bob = db.search_memories(query_embedding=emb, user_id="student_bob")
    assert len(res_bob) == 1
    assert "Bob memory 1" in res_bob[0]


def test_session_scoped_memory_deletion():
    """
    Verification:
    Deleting memories scoped to a specific session_id removes only that session's
    memories, retaining memories from other sessions for the same user.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.3] * 768

    db.save_memory(session_id="lab_mechanics", text="Mechanics lab notes", embedding=emb, user_id="student_carol")
    db.save_memory(session_id="lab_optics", text="Optics lab notes", embedding=emb, user_id="student_carol")

    # Delete only mechanics session
    deleted = db.delete_user_memories(user_id="student_carol", session_id="lab_mechanics")
    assert deleted == 1

    # Search with session_id=lab_mechanics returns empty
    res_mech = db.search_memories(query_embedding=emb, user_id="student_carol", session_id="lab_mechanics")
    assert len(res_mech) == 0

    # Search with session_id=lab_optics still returns optics notes
    res_optics = db.search_memories(query_embedding=emb, user_id="student_carol", session_id="lab_optics")
    assert len(res_optics) == 1
    assert "Optics" in res_optics[0]


def test_single_memory_deletion_with_ownership_protection():
    """
    Verification:
    A user cannot delete another user's memory by ID.
    A user can delete their own memory by ID, which removes it from retrieval.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.4] * 768

    id_alice = db.save_memory(session_id="s1", text="Alice private note", embedding=emb, user_id="alice")
    id_bob = db.save_memory(session_id="s1", text="Bob private note", embedding=emb, user_id="bob")

    # Bob attempts to delete Alice's memory: must fail
    bob_attempt = db.delete_memory_by_id(memory_id=id_alice, user_id="bob")
    assert bob_attempt is False

    # Alice's memory still exists
    res = db.search_memories(query_embedding=emb, user_id="alice")
    assert len(res) == 1

    # Alice deletes her own memory: must succeed
    alice_success = db.delete_memory_by_id(memory_id=id_alice, user_id="alice")
    assert alice_success is True

    # Alice's memory is now gone
    res_after = db.search_memories(query_embedding=emb, user_id="alice")
    assert len(res_after) == 0


def test_user_memory_data_export():
    """
    Verification:
    export_user_memories() exports an account's memories with ownership, session,
    and timestamps, without exposing raw high-dimensional vector embeddings.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.15] * 768

    db.save_memory(
        session_id="sess_100",
        text="Exportable study note",
        embedding=emb,
        user_id="student_export",
        experiment_id="exp_42",
        embedding_model_version="text-embedding-004",
    )

    exported = db.export_user_memories(user_id="student_export")
    assert len(exported) == 1
    record = exported[0]
    assert record["text"] == "Exportable study note"
    assert record["session_id"] == "sess_100"
    assert record["experiment_id"] == "exp_42"
    assert record["embedding_model_version"] == "text-embedding-004"
    assert "embedding" not in record  # Vector embedding omitted for export efficiency


def test_retention_ttl_and_expiration_filtering():
    """
    Verification:
    Expired memories (past retention TTL) are excluded from standard search queries,
    and cleanup_expired_memories() purges expired records.
    """
    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.5] * 768

    # Save active memory with 90 days retention
    db.save_memory(
        session_id="s_active",
        text="Active knowledge retention",
        embedding=emb,
        user_id="student_ttl",
        retention_days=90,
    )

    # Save an already expired memory (retention_days=-1)
    db.save_memory(
        session_id="s_expired",
        text="Expired temporary prompt",
        embedding=emb,
        user_id="student_ttl",
        retention_days=-1,  # Expired in the past
    )

    # Standard search excludes expired memory
    active_results = db.search_memories(query_embedding=emb, user_id="student_ttl")
    assert len(active_results) == 1
    assert "Active knowledge" in active_results[0]

    # Search with include_expired=True includes both
    all_results = db.search_memories(query_embedding=emb, user_id="student_ttl", include_expired=True)
    assert len(all_results) == 2

    # Cleanup expired memories
    purged = db.cleanup_expired_memories()
    assert purged == 1
    assert len(db.fallback_memories) == 1


def test_memory_lifecycle_api_endpoints(monkeypatch):
    """
    Verification:
    API endpoints DELETE /api/tutor/memories and GET /api/tutor/memories/export
    enforce authenticated user identity and execute deletion/export workflows.
    """
    from app.core_backend.core.dependencies import get_current_user

    db = PGVectorManager()
    db.fallback_memories = []

    emb = [0.6] * 768
    db.save_memory(session_id="web_sess", text="Web conversation memory", embedding=emb, user_id="user_api_test")

    # Wire router to use our db
    import app.core_backend.routes.tutor as tutor_module
    monkeypatch.setattr(tutor_module, "db", db)

    headers = {"Authorization": "Bearer dummy_token"}
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_api_test", "sub": "user_api_test", "role": "student"}

    try:
        # 1. Export memories via API
        exp_res = client.get("/api/tutor/memories/export", headers=headers)
        assert exp_res.status_code == 200
        data = exp_res.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["memories"][0]["text"] == "Web conversation memory"

        # 2. Delete memories via API
        del_res = client.delete("/api/tutor/memories", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["deleted_count"] == 1

        # 3. Export again: must be empty
        exp_res2 = client.get("/api/tutor/memories/export", headers=headers)
        assert exp_res2.status_code == 200
        assert exp_res2.json()["count"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)
