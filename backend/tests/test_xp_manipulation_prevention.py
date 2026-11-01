"""
Test Suite for Problem 1 (P0 High Priority):
XP can potentially be manipulated by authenticated users.

Validates all 5 required solution components:
1. Do not let clients determine XP amounts: Server rules govern actual awarded XP.
2. Generate XP awards on the backend after verifying a completed activity.
3. Verify the experiment or learning evaluation exists and belongs to the user.
4. Calculate the award amount using server-side rules (e.g. 100 XP for experiment completion).
5. Enforce a unique database constraint on the event identity (changing event_id cannot bypass duplicate protection).
"""
import os
import pytest
from unittest.mock import patch
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.routes.gamification import LEADERBOARD_CACHE, SERVER_ACTIVITY_RULES

client = TestClient(app)

USER_ALICE = {"id": "student_alice", "sub": "student_alice", "role": "student"}
USER_BOB = {"id": "student_bob", "sub": "student_bob", "role": "student"}


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Resets local database and cache before each test."""
    app.dependency_overrides[get_current_user] = lambda: USER_ALICE
    LEADERBOARD_CACHE.clear()

    db = DatabaseManager()
    data = db._read_local()
    data["xp"] = {USER_ALICE["id"]: 0, USER_BOB["id"]: 0}
    data["xp_ledger"] = {}
    data["experiments"] = []
    db._write_local(data)

    yield

    app.dependency_overrides.clear()
    LEADERBOARD_CACHE.clear()


def create_mock_experiment(user_id: str, experiment_id: str, status: str = "completed"):
    """Helper to insert a verified experiment into the database."""
    db = DatabaseManager()
    data = db._read_local()
    exp_record = {
        "id": experiment_id,
        "user_id": user_id,
        "experiment_type": "free_fall",
        "type": "free_fall",
        "inference_status": status,
        "server_computed_results": {"velocity": 19.8, "time": 2.02},
    }
    data.setdefault("experiments", []).append(exp_record)
    db._write_local(data)
    return exp_record


# ==============================================================================
# Requirement 1 & 4: Server-Side Rules Govern XP Amounts (Clients Cannot Dictate)
# ==============================================================================

def test_clients_cannot_determine_arbitrary_xp_amounts():
    """
    Vulnerability check:
    A user attempts to award themselves 500 XP for an experiment completion:
    {
      "amount": 500,
      "action": "experiment_completed",
      "experiment_id": "exp_valid_1"
    }
    The server MUST NOT award 500 XP.
    The award amount must be calculated strictly using server-side rules (100 XP).
    """
    create_mock_experiment(user_id=USER_ALICE["id"], experiment_id="exp_valid_1")

    payload = {
        "amount": 500,
        "action": "experiment_completed",
        "experiment_id": "exp_valid_1",
        "event_id": "event-001",
    }
    res = client.post("/api/gamification/add-xp", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["awarded"] is True
    # Server calculates rule-based amount (100 XP), rejecting client's 500 XP claim
    expected_xp = SERVER_ACTIVITY_RULES["experiment_completed"]
    assert data["xp_awarded"] == expected_xp
    assert data["xp_awarded"] != 500
    assert data["total_xp"] == expected_xp


# ==============================================================================
# Requirement 3: Activity Verification (Experiment Exists and Belongs to User)
# ==============================================================================

def test_activity_verification_rejects_missing_experiment():
    """
    If a user claims XP for an experiment that does not exist in the database,
    the server must reject the claim with HTTP 404.
    """
    payload = {
        "amount": 500,
        "action": "experiment_completed",
        "experiment_id": "non_existent_exp_999",
        "event_id": "event-001",
    }
    res = client.post("/api/gamification/add-xp", json=payload)
    assert res.status_code == 404
    assert "Activity verification failed" in res.json()["detail"]


def test_activity_verification_rejects_claiming_another_users_experiment():
    """
    If User Alice attempts to claim XP for an experiment performed by User Bob,
    the server must reject the claim with HTTP 403 Forbidden.
    """
    create_mock_experiment(user_id=USER_BOB["id"], experiment_id="exp_bob_001")

    payload = {
        "amount": 100,
        "action": "experiment_completed",
        "experiment_id": "exp_bob_001",
        "event_id": "event-001",
    }
    res = client.post("/api/gamification/add-xp", json=payload)
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]
    assert "another user" in res.json()["detail"].lower()


def test_activity_verification_rejects_action_without_experiment_id():
    """
    Claiming 'experiment_completed' without identifying an experiment must be rejected (HTTP 422).
    """
    payload = {
        "amount": 500,
        "action": "experiment_completed",
        "event_id": "event-001",
    }
    res = client.post("/api/gamification/add-xp", json=payload)
    assert res.status_code in (422, 404)


# ==============================================================================
# Requirement 5: Changing event_id Cannot Bypass Duplicate-Event Protection
# ==============================================================================

def test_changing_event_id_cannot_bypass_duplicate_protection():
    """
    Core Exploit Scenario from Problem Statement:
    A user submits a completed experiment with event_id: "event-001" and receives XP.
    Then, the user changes the event_id to "event-002" attempting to claim XP again.
    
    The server binds the event identity deterministically to the experiment (evt_exp_...).
    The database constraint on event identity rejects the second attempt as a duplicate.
    """
    create_mock_experiment(user_id=USER_ALICE["id"], experiment_id="exp_unique_42")

    # Call 1: First submission with event_id="event-001"
    res1 = client.post(
        "/api/gamification/add-xp",
        json={
            "amount": 500,
            "action": "experiment_completed",
            "experiment_id": "exp_unique_42",
            "event_id": "event-001",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "success"
    assert data1["awarded"] is True
    initial_total = data1["total_xp"]
    assert initial_total == SERVER_ACTIVITY_RULES["experiment_completed"]

    # Call 2: Attacker changes event_id to "event-002"
    res2 = client.post(
        "/api/gamification/add-xp",
        json={
            "amount": 500,
            "action": "experiment_completed",
            "experiment_id": "exp_unique_42",
            "event_id": "event-002",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "duplicate"
    assert data2["awarded"] is False
    assert data2["xp_awarded"] == 0
    # Total XP must remain strictly unchanged!
    assert data2["total_xp"] == initial_total

    # Call 3: Attacker omits event_id completely
    res3 = client.post(
        "/api/gamification/add-xp",
        json={
            "amount": 500,
            "action": "experiment_completed",
            "experiment_id": "exp_unique_42",
        },
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["status"] == "duplicate"
    assert data3["awarded"] is False
    assert data3["xp_awarded"] == 0
    assert data3["total_xp"] == initial_total


# ==============================================================================
# Requirement 2: Backend Generates XP Awards Automatically on Completed Activity
# ==============================================================================

def test_backend_automatically_awards_xp_on_experiment_save():
    """
    When an experiment is saved and completed via the backend route (/api/experiments/save),
    the backend automatically awards XP.
    Subsequent manual claims via /add-xp are recognized as duplicates.
    """
    save_payload = {
        "experiment_type": "free_fall",
        "height": 20.0,
        "gravity": 9.81,
    }
    res_save = client.post("/api/experiments/save", json=save_payload)
    assert res_save.status_code == 200
    save_data = res_save.json()
    assert save_data["status"] == "saved"
    saved_exp_id = save_data["experiment"]["id"]

    # Verify XP was automatically awarded to Alice
    res_my_xp = client.get("/api/gamification/my-xp")
    assert res_my_xp.status_code == 200
    assert res_my_xp.json()["xp"] == SERVER_ACTIVITY_RULES["experiment_completed"]

    # Verify that trying to claim XP manually for this experiment is rejected as duplicate
    res_claim = client.post(
        "/api/gamification/add-xp",
        json={
            "action": "experiment_completed",
            "experiment_id": saved_exp_id,
            "amount": 500,
            "event_id": "arbitrary_new_event_id",
        },
    )
    assert res_claim.status_code == 200
    assert res_claim.json()["status"] == "duplicate"
    assert res_claim.json()["awarded"] is False
    assert res_claim.json()["xp_awarded"] == 0

