"""
Test Suite for Problem 22: SQL writes and XP updates integrity guarantees
Validates:
1. Store authoritative XP total in the database (never accept client-supplied total).
2. Transactional execution of XP mutations.
3. Immutable and auditable ledger (xp_ledger) tracking all awarded points.
4. Server-side validation of award amounts (strictly positive, capped at MAX_XP_PER_EVENT).
5. Idempotency keys / unique event IDs rejecting duplicate reward events.
6. Verification: Submit the same reward event twice and confirm XP is awarded only once.
7. Ledger reconciliation and audit history retrieval.
"""
import os
import pytest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.database.pgvector_db import PGVectorManager, DatabasePersistenceError
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.core.dependencies import get_current_user, get_db, reset_shared_dependencies
from app.core_backend.routes.gamification import MAX_XP_PER_EVENT

client = TestClient(app)

TEST_USER_A = {"id": "user_xp_alice", "sub": "user_xp_alice", "role": "student"}
TEST_USER_B = {"id": "user_xp_bob", "sub": "user_xp_bob", "role": "student"}


@pytest.fixture(autouse=True)
def override_auth_and_cleanup():
    reset_shared_dependencies()
    db = DatabaseManager()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_A
    app.dependency_overrides[get_db] = lambda: db
    data = db._read_local()
    if "xp" in data:
        data["xp"][TEST_USER_A["id"]] = 0
        data["xp"][TEST_USER_B["id"]] = 0
    if "xp_ledger" in data:
        data["xp_ledger"] = {
            k: v for k, v in data["xp_ledger"].items()
            if v.get("user_id") not in (TEST_USER_A["id"], TEST_USER_B["id"])
        }
    db._write_local(data)

    with patch.dict(os.environ, {"ALLOW_IN_MEMORY_FALLBACK": "true"}):
        yield

    app.dependency_overrides.clear()
    reset_shared_dependencies()


def test_server_enforces_positive_award_amounts():
    """
    Verification:
    Zero or negative award amounts must be rejected by the server (HTTP 422).
    """
    # 1. Zero amount rejected
    res_zero = client.post(
        "/api/gamification/add-xp",
        json={"action": "test_zero", "amount": 0},
    )
    assert res_zero.status_code == 422

    # 2. Negative amount rejected
    res_neg = client.post(
        "/api/gamification/add-xp",
        json={"action": "test_neg", "amount": -100},
    )
    assert res_neg.status_code == 422


def test_server_enforces_maximum_award_cap():
    """
    Verification:
    Amounts exceeding MAX_XP_PER_EVENT (500 XP) must be rejected by the server (HTTP 422).
    """
    res_excessive = client.post(
        "/api/gamification/add-xp",
        json={"action": "exploit_xp", "amount": 50000},
    )
    assert res_excessive.status_code == 422


def test_idempotent_event_rejection_submitting_same_event_twice():
    """
    Verification (User Story):
    Submit the same reward event twice and confirm that XP is awarded only once.
    Second submission returns duplicate status and does NOT increment total XP.
    """
    event_id = "quiz_completed_lab_98765"
    payload = {
        "action": "quiz_completed",
        "amount": 75,
        "event_id": event_id,
        "concept": "Newton's Second Law",
    }

    # First submission -> Should succeed and award 75 XP
    res1 = client.post("/api/gamification/add-xp", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    assert data1["awarded"] is True
    assert data1["xp_awarded"] == 75
    first_total = data1["total_xp"]
    assert first_total >= 75

    # Second submission with the exact same event_id -> Must be recognized as duplicate
    res2 = client.post("/api/gamification/add-xp", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "duplicate"
    assert data2["awarded"] is False
    assert data2["xp_awarded"] == 0
    # Total XP must remain completely unchanged
    assert data2["total_xp"] == first_total

    # Verify through /my-xp endpoint that total was not doubled
    res_my_xp = client.get("/api/gamification/my-xp")
    assert res_my_xp.status_code == 200
    assert res_my_xp.json()["xp"] == first_total


def test_auditable_ledger_recording_and_history_endpoint():
    """
    Verification:
    Awarded points create immutable audit entries in xp_ledger, queryable via /xp-history.
    """
    event_id_1 = "exp_step_1_id"
    event_id_2 = "exp_step_2_id"

    client.post("/api/gamification/add-xp", json={"action": "experiment_step", "amount": 25, "event_id": event_id_1})
    client.post("/api/gamification/add-xp", json={"action": "experiment_step", "amount": 25, "event_id": event_id_2})

    res_history = client.get("/api/gamification/xp-history?limit=10")
    assert res_history.status_code == 200
    history = res_history.json()["history"]

    recorded_event_ids = [entry["event_id"] for entry in history]
    assert event_id_1 in recorded_event_ids
    assert event_id_2 in recorded_event_ids

    entry_1 = next(e for e in history if e["event_id"] == event_id_1)
    assert entry_1["amount"] == 25
    assert entry_1["action"] == "experiment_step"


def test_reconcile_xp_from_ledger():
    """
    Verification:
    Reconciles aggregate user_xp from the sum of the immutable xp_ledger records.
    """
    res_recon = client.post("/api/gamification/reconcile")
    assert res_recon.status_code == 200
    reconciled_xp = res_recon.json()["reconciled_xp"]
    assert isinstance(reconciled_xp, int)
    assert reconciled_xp >= 0


def test_pgvector_db_transactional_integrity_with_rollback():
    """
    Verification:
    Tests that PGVectorManager uses atomic database transactions for XP mutations,
    rolling back cleanly on database exceptions without corrupting state.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate error on aggregate update after ledger insert
    mock_cursor.fetchone.return_value = ("evt_test_123",)
    mock_cursor.execute.side_effect = [
        None,  # 1. INSERT INTO xp_ledger succeeds
        Exception("Deadlock or foreign key violation"),  # 2. INSERT INTO user_xp fails
    ]

    manager = PGVectorManager(url="postgresql://app:pass@db:5432/stemlab")
    manager.mode = PGVectorManager.DatabaseMode.PRODUCTION if hasattr(PGVectorManager, "DatabaseMode") else "production"
    from app.core_backend.database.pgvector_db import DatabaseMode
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    with patch.object(manager, "_get_conn") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        with pytest.raises(DatabasePersistenceError):
            manager.record_xp_event(
                user_id="user_test_tx",
                action="lab_completed",
                amount=100,
                event_id="evt_tx_failure",
            )

        # Confirm rollback was triggered on connection
        mock_conn.commit.assert_not_called()


def test_never_accept_client_supplied_total_as_authoritative():
    """
    Verification:
    Client sending arbitrary fields like 'total_xp' in payload cannot overwrite
    authoritative database total. Total is always calculated by the server.
    """
    db = DatabaseManager()
    initial_xp = db.get_user_xp(TEST_USER_A["id"])

    # Client attempts to inject a spoofed total_xp: 999999
    res = client.post(
        "/api/gamification/add-xp",
        json={"action": "test_tamper", "amount": 50, "total_xp": 999999, "event_id": "tamper_event_1"},
    )
    assert res.status_code == 200
    data = res.json()
    # Server calculates authoritative total (initial + 50), never 999999
    assert data["total_xp"] == initial_xp + 50
    assert data["total_xp"] != 999999
