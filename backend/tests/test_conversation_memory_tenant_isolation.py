"""
Unit & Integration Tests for Problem 9: Strict Tenant Isolation in Conversation Memory.
Files under test:
- backend/app/core_backend/repositories/memory_repository.py
- backend/app/core_backend/database/pgvector_db.py
- backend/app/core_backend/database/supabase_db.py
- backend/app/core_backend/routes/tutor.py

Requirements verified independently:
1. Save memory:
   - Mandatory valid user_id enforcement (rejects None, empty, whitespace).
   - Session ownership validation (rejects saving into another tenant's session).
2. Search memory:
   - Mandatory valid user_id enforcement.
   - Strict cross-tenant isolation (User A never retrieves User B memories).
   - Rejects searching with another tenant's session_id.
3. List memories:
   - Strict user_id filtering with pagination (limit, offset).
   - Session scoping with session ownership check.
   - Rejects listing another tenant's session.
4. Delete memory:
   - Matching both memory_id and user_id.
   - Prevents cross-tenant memory deletion.
5. Delete all user memories:
   - Strictly purges only the authenticated user's records.
   - Preserves all other tenants' data intact.
   - Rejects deletion scoped to another tenant's session.
6. Retrieve session history:
   - Chronological ordering of session interaction turns.
   - Rejects retrieval of a session belonging to another user.
7. Session ownership validation:
   - Accurate validation across new, owned, and foreign sessions.
8. MemoryRepository encapsulation:
   - Propagates TenantIsolationError rather than swallowing it.
9. API Endpoints:
   - Endpoints return HTTP 403 Forbidden on tenant violation.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.database.pgvector_db import (
    PGVectorManager,
    TenantIsolationError,
)
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.repositories.memory_repository import (
    MemoryRepository,
    MemoryRepositoryProtocol,
)
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    """Ensures each test starts and ends with a pristine in-memory state."""
    from app.core_backend.database.supabase_db import DatabaseManager, db_lock
    dm = DatabaseManager()
    with db_lock:
        data = dm._read_local()
        data["memories"] = []
        dm._write_local(data)
    yield
    with db_lock:
        data = dm._read_local()
        data["memories"] = []
        dm._write_local(data)


# ---------------------------------------------------------------------------
# 1. Save Memory Tenant Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_save_memory_requires_valid_user_id(db_cls):
    """Save memory must reject None, empty string, or whitespace-only user_id."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.1] * 768

    with pytest.raises(TenantIsolationError):
        db.save_memory(session_id="sess_1", text="Sample text", embedding=emb, user_id=None)

    with pytest.raises(TenantIsolationError):
        db.save_memory(session_id="sess_1", text="Sample text", embedding=emb, user_id="")

    with pytest.raises(TenantIsolationError):
        db.save_memory(session_id="sess_1", text="Sample text", embedding=emb, user_id="   ")


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_save_memory_requires_valid_session_id(db_cls):
    """Save memory must reject empty or whitespace session_id."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.1] * 768

    with pytest.raises(TenantIsolationError):
        db.save_memory(session_id="", text="Sample text", embedding=emb, user_id="user_alice")

    with pytest.raises(TenantIsolationError):
        db.save_memory(session_id="   ", text="Sample text", embedding=emb, user_id="user_alice")


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_save_memory_prevents_session_hijacking(db_cls):
    """User B cannot save memories into a session established and owned by User A."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.2] * 768

    # User A creates session_100
    doc_a = db.save_memory(session_id="session_100", text="Alice lesson", embedding=emb, user_id="user_alice")
    assert doc_a is not None

    # User B attempts to hijack session_100
    with pytest.raises(TenantIsolationError) as exc_info:
        db.save_memory(session_id="session_100", text="Bob hijacking attempt", embedding=emb, user_id="user_bob")

    assert "Access denied" in str(exc_info.value)
    assert "belongs to another user" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Search Memory Tenant Isolation Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_search_memories_requires_valid_user_id(db_cls):
    """Search memories must reject unauthenticated (None / empty) user_id."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.1] * 768

    with pytest.raises(TenantIsolationError):
        db.search_memories(query_embedding=emb, query_text="test", user_id=None)

    with pytest.raises(TenantIsolationError):
        db.search_memories(query_embedding=emb, query_text="test", user_id="")


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_search_memories_cross_tenant_isolation(db_cls):
    """User A's search query NEVER retrieves User B's memories under identical embeddings and queries."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb_shared = [0.3] * 768

    db.save_memory(session_id="alice_sess", text="Alice secret formula for momentum", embedding=emb_shared, user_id="alice")
    db.save_memory(session_id="bob_sess", text="Bob secret formula for optics", embedding=emb_shared, user_id="bob")

    # Alice searches
    alice_res = db.search_memories(
        query_embedding=emb_shared,
        query_text="secret formula",
        user_id="alice",
        return_metadata=True,
    )
    assert len(alice_res) == 1
    assert alice_res[0]["user_id"] == "alice"
    assert "momentum" in alice_res[0]["text"]
    assert "optics" not in alice_res[0]["text"]

    # Bob searches
    bob_res = db.search_memories(
        query_embedding=emb_shared,
        query_text="secret formula",
        user_id="bob",
        return_metadata=True,
    )
    assert len(bob_res) == 1
    assert bob_res[0]["user_id"] == "bob"
    assert "optics" in bob_res[0]["text"]
    assert "momentum" not in bob_res[0]["text"]


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_search_memories_rejects_foreign_session_id(db_cls):
    """User B cannot search scoping to User A's session."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.4] * 768
    db.save_memory(session_id="alice_private_session", text="Alice private notes", embedding=emb, user_id="alice")

    with pytest.raises(TenantIsolationError) as exc_info:
        db.search_memories(
            query_embedding=emb,
            query_text="private",
            user_id="bob",
            session_id="alice_private_session",
        )
    assert "Access denied" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 3. List Memories Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_list_memories_isolation_and_pagination(db_cls):
    """list_memories must return only the authenticated user's records with pagination support."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.5] * 768

    # Save 5 memories for Alice and 3 for Bob
    for i in range(5):
        db.save_memory(session_id="alice_s", text=f"Alice note {i}", embedding=emb, user_id="alice")
    for i in range(3):
        db.save_memory(session_id="bob_s", text=f"Bob note {i}", embedding=emb, user_id="bob")

    # List page 1 for Alice (limit=2, offset=0)
    page1 = db.list_memories(user_id="alice", limit=2, offset=0)
    assert len(page1) == 2
    assert all(m["user_id"] == "alice" for m in page1)

    # List page 2 for Alice (limit=2, offset=2)
    page2 = db.list_memories(user_id="alice", limit=2, offset=2)
    assert len(page2) == 2
    assert all(m["user_id"] == "alice" for m in page2)

    # Page 1 and Page 2 must have distinct memories
    ids_p1 = {m["id"] for m in page1}
    ids_p2 = {m["id"] for m in page2}
    assert ids_p1.isdisjoint(ids_p2)

    # Bob lists all his memories
    bob_mems = db.list_memories(user_id="bob", limit=10, offset=0)
    assert len(bob_mems) == 3
    assert all(m["user_id"] == "bob" for m in bob_mems)


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_list_memories_rejects_foreign_session(db_cls):
    """list_memories with a foreign session_id raises TenantIsolationError."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.5] * 768
    db.save_memory(session_id="alice_s", text="Alice note", embedding=emb, user_id="alice")

    with pytest.raises(TenantIsolationError):
        db.list_memories(user_id="bob", session_id="alice_s")


# ---------------------------------------------------------------------------
# 4. Delete Single Memory Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_delete_memory_by_id_strict_ownership(db_cls):
    """A user cannot delete another user's memory by ID."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.6] * 768
    id_alice = db.save_memory(session_id="s_alice", text="Alice private note", embedding=emb, user_id="alice")
    id_bob = db.save_memory(session_id="s_bob", text="Bob note", embedding=emb, user_id="bob")

    # Bob attempts to delete Alice's memory: MUST return False (or fail) without deleting
    assert db.delete_memory_by_id(memory_id=id_alice, user_id="bob") is False

    # Alice's memory still retrievable
    res_alice = db.search_memories(query_embedding=emb, user_id="alice")
    assert len(res_alice) == 1

    # Alice deletes her own memory: MUST succeed
    assert db.delete_memory_by_id(memory_id=id_alice, user_id="alice") is True

    # Alice's memory is now gone
    res_alice_after = db.search_memories(query_embedding=emb, user_id="alice")
    assert len(res_alice_after) == 0

    # Bob's memory remains intact
    res_bob = db.search_memories(query_embedding=emb, user_id="bob")
    assert len(res_bob) == 1


# ---------------------------------------------------------------------------
# 5. Delete All User Memories Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_delete_all_user_memories_preserves_other_tenants(db_cls):
    """Deleting all memories for User A purges only User A's data, preserving User B's."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.7] * 768
    db.save_memory(session_id="a1", text="Alice note 1", embedding=emb, user_id="alice")
    db.save_memory(session_id="a2", text="Alice note 2", embedding=emb, user_id="alice")
    db.save_memory(session_id="b1", text="Bob note 1", embedding=emb, user_id="bob")

    del_count = db.delete_user_memories(user_id="alice")
    assert del_count == 2

    # Alice has 0 memories left
    assert len(db.list_memories(user_id="alice")) == 0

    # Bob still has 1 memory
    bob_mems = db.list_memories(user_id="bob")
    assert len(bob_mems) == 1
    assert bob_mems[0]["text"] == "Bob note 1"


@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_delete_user_memories_rejects_foreign_session(db_cls):
    """User B cannot invoke delete_user_memories scoped to User A's session."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.7] * 768
    db.save_memory(session_id="alice_confidential_session", text="Secret data", embedding=emb, user_id="alice")

    with pytest.raises(TenantIsolationError):
        db.delete_user_memories(user_id="bob", session_id="alice_confidential_session")

    # Alice's session was NOT deleted
    assert len(db.list_memories(user_id="alice", session_id="alice_confidential_session")) == 1


# ---------------------------------------------------------------------------
# 6. Retrieve Session History Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_get_session_history_chronological_and_isolated(db_cls):
    """get_session_history returns turns in chronological order and blocks other users."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.8] * 768

    db.save_memory(session_id="lab_sess", text="Turn 1: Hypothesis", embedding=emb, user_id="carol")
    db.save_memory(session_id="lab_sess", text="Turn 2: Experimentation", embedding=emb, user_id="carol")
    db.save_memory(session_id="lab_sess", text="Turn 3: Conclusion", embedding=emb, user_id="carol")

    # Carol retrieves history: MUST return all 3 turns in chronological order
    history = db.get_session_history(session_id="lab_sess", user_id="carol")
    assert len(history) == 3
    assert history[0]["text"] == "Turn 1: Hypothesis"
    assert history[1]["text"] == "Turn 2: Experimentation"
    assert history[2]["text"] == "Turn 3: Conclusion"

    # Dave attempts to access Carol's session history: MUST be rejected
    with pytest.raises(TenantIsolationError) as exc_info:
        db.get_session_history(session_id="lab_sess", user_id="dave")

    assert "Access denied" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. Session Ownership Validation Direct Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db_cls", [PGVectorManager, DatabaseManager])
def test_validate_session_ownership_direct(db_cls):
    """validate_session_ownership returns True for fresh or own sessions, False for foreign."""
    db = db_cls()
    if hasattr(db, "fallback_memories"):
        db.fallback_memories = []

    emb = [0.9] * 768

    # Brand new session: owned by nobody yet, so allowed for anyone
    assert db.validate_session_ownership("brand_new_session", "user_1") is True

    # User 1 registers a memory in brand_new_session
    db.save_memory(session_id="brand_new_session", text="Initial note", embedding=emb, user_id="user_1")

    # Now owned by user_1
    assert db.validate_session_ownership("brand_new_session", "user_1") is True

    # user_2 cannot claim ownership
    assert db.validate_session_ownership("brand_new_session", "user_2") is False


# ---------------------------------------------------------------------------
# 8. MemoryRepository Protocol and Wrapper Tests
# ---------------------------------------------------------------------------

def test_memory_repository_wrapper_enforces_tenant_isolation():
    """MemoryRepository implements all required tenant-isolated operations."""
    pg = PGVectorManager()
    pg.fallback_memories = []
    repo = MemoryRepository(pg)

    assert isinstance(repo, MemoryRepositoryProtocol)

    emb = [0.35] * 768

    # 1. Save memory
    doc_id = repo.save_memory(session_id="repo_s1", text="Repository note", embedding=emb, user_id="user_repo")
    assert doc_id is not None

    # 2. Search memory
    results = repo.search_memories(
        query_embedding=emb,
        query_text="Repository note",
        user_id="user_repo",
        return_metadata=True,
    )
    assert len(results) == 1
    assert results[0]["user_id"] == "user_repo"

    # 3. List memories
    mems = repo.list_memories(user_id="user_repo")
    assert len(mems) == 1

    # 4. Session history
    hist = repo.get_session_history(session_id="repo_s1", user_id="user_repo")
    assert len(hist) == 1

    # 5. Cross-tenant attempt via repo must raise TenantIsolationError
    with pytest.raises(TenantIsolationError):
        repo.save_memory(session_id="repo_s1", text="Intruder note", embedding=emb, user_id="user_intruder")

    with pytest.raises(TenantIsolationError):
        repo.search_memories(query_embedding=emb, query_text="note", user_id="user_intruder", session_id="repo_s1")

    with pytest.raises(TenantIsolationError):
        repo.get_session_history(session_id="repo_s1", user_id="user_intruder")

    # 6. Delete memory
    assert repo.delete_memory(memory_id=doc_id, user_id="user_intruder") is False
    assert repo.delete_memory(memory_id=doc_id, user_id="user_repo") is True


# ---------------------------------------------------------------------------
# 9. HTTP API Endpoint Tenant Isolation Security Tests
# ---------------------------------------------------------------------------

def test_api_memories_endpoints_tenant_isolation(monkeypatch):
    """FastAPI tutor memory endpoints return HTTP 403 Forbidden on tenant violation."""
    pg = PGVectorManager()
    pg.fallback_memories = []
    emb = [0.45] * 768

    # Alice owns session 'alice_secret_session'
    pg.save_memory(session_id="alice_secret_session", text="Alice confidential note", embedding=emb, user_id="alice_user")

    import app.core_backend.routes.tutor as tutor_module
    monkeypatch.setattr(tutor_module, "db", pg)

    headers = {"Authorization": "Bearer mock_token"}

    # Simulate Bob calling API
    app.dependency_overrides[get_current_user] = lambda: {"id": "bob_user", "sub": "bob_user", "role": "student"}

    try:
        # 1. Bob tries to list memories from Alice's session -> 403 Forbidden
        res_list = client.get("/api/tutor/memories?session_id=alice_secret_session", headers=headers)
        assert res_list.status_code == 403
        assert "Access denied" in res_list.json()["detail"]

        # 2. Bob tries to get Alice's session history -> 403 Forbidden
        res_hist = client.get("/api/tutor/memories/session/alice_secret_session", headers=headers)
        assert res_hist.status_code == 403
        assert "Access denied" in res_hist.json()["detail"]

        # 3. Bob tries to delete Alice's session memories -> 403 Forbidden
        res_del_sess = client.delete("/api/tutor/memories?session_id=alice_secret_session", headers=headers)
        assert res_del_sess.status_code == 403
        assert "Access denied" in res_del_sess.json()["detail"]

        # 4. Bob lists his own memories -> 200 OK, empty list
        res_bob = client.get("/api/tutor/memories", headers=headers)
        assert res_bob.status_code == 200
        assert res_bob.json()["count"] == 0

    finally:
        app.dependency_overrides.pop(get_current_user, None)
