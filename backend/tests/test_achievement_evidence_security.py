"""
Test Suite for Problem 2:
Achievement verification trusts client-provided evidence.

Validates that:
1. Client cannot spoof experiment count via evidence {"experiment_count": 5}.
2. Client cannot spoof experiment IDs via unverified evidence {"experiment_id": "fake"}.
3. Client cannot use another user's experiment ID in evidence.
4. Client cannot spoof concept mastery via evidence {"concept": "gravity"}.
5. Client cannot spoof event evidence via booleans {"completed": True, "verified": True}.
6. Legitimate database-backed evidence (verified experiments, ledger records, memories) succeeds.
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
from app.core_backend.routes.gamification import LEADERBOARD_CACHE

client = TestClient(app)

USER_ALICE = {"id": "learner_alice", "sub": "learner_alice", "role": "student"}
USER_BOB = {"id": "learner_bob", "sub": "learner_bob", "role": "student"}


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
    data["memories"] = []
    data["user_achievements"] = []
    db._write_local(data)

    yield

    app.dependency_overrides.clear()
    LEADERBOARD_CACHE.clear()


# ==============================================================================
# 1. Experiment Count Security: Reject Spoofed Client Evidence
# ==============================================================================

def test_client_supplied_experiment_count_is_rejected():
    """
    Vulnerability check:
    A user with 0 experiments submits evidence: {"experiment_count": 5}
    to unlock 'physics_explorer' (requires 5 experiments).
    Must be rejected with HTTP 422 because DB has 0 experiments.
    """
    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "physics_explorer",
            "evidence": {"experiment_count": 5, "verified": True},
        },
    )
    assert res.status_code == 422
    assert "Eligibility criteria not satisfied" in res.json()["detail"]
    assert "0/5 completed experiments" in res.json()["detail"]


def test_client_supplied_unverified_experiment_id_is_rejected():
    """
    A user with 0 experiments submits evidence: {"experiment_id": "fake_exp_999"}.
    Must be rejected with HTTP 422 because the experiment does not exist in DB.
    """
    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "first_steps",
            "evidence": {"experiment_id": "fake_exp_999"},
        },
    )
    assert res.status_code == 422
    assert "Eligibility criteria not satisfied" in res.json()["detail"]


def test_client_cannot_claim_another_users_experiment_as_evidence():
    """
    User Alice attempts to use User Bob's experiment ID as evidence.
    Must be rejected with HTTP 422 because the experiment does not belong to Alice.
    """
    db = DatabaseManager()
    data = db._read_local()
    data.setdefault("experiments", []).append({
        "id": "exp_bob_secret",
        "user_id": USER_BOB["id"],
        "experiment_type": "free_fall",
        "inference_status": "completed",
    })
    db._write_local(data)

    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "first_steps",
            "evidence": {"experiment_id": "exp_bob_secret"},
        },
    )
    assert res.status_code == 422
    assert "Eligibility criteria not satisfied" in res.json()["detail"]


def test_verified_experiments_in_database_satisfy_criteria():
    """
    When Alice legitimately has completed experiments in the database,
    the achievement is granted.
    """
    db = DatabaseManager()
    data = db._read_local()
    data.setdefault("experiments", []).append({
        "id": "exp_alice_001",
        "user_id": USER_ALICE["id"],
        "experiment_type": "free_fall",
        "inference_status": "completed",
    })
    db._write_local(data)

    res = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "first_steps"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "awarded"
    assert res.json()["achievement_id"] == "first_steps"


# ==============================================================================
# 2. Concept Mastery Security: Reject Spoofed Concept Evidence
# ==============================================================================

def test_client_supplied_concept_assertion_is_rejected_without_db_record():
    """
    A user with no tutor evaluations or mastery ledger records submits:
    evidence: {"concept": "gravity"}
    to unlock 'gravity_pioneer'.
    Must be rejected with HTTP 422.
    """
    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "gravity_pioneer",
            "evidence": {"concept": "gravity", "verified": True},
        },
    )
    assert res.status_code == 422
    assert "no verified database evaluation or ledger record found" in res.json()["detail"]


def test_verified_concept_mastery_in_ledger_satisfies_criteria():
    """
    When Alice legitimately earned concept mastery in the database ledger,
    the 'gravity_pioneer' badge is successfully awarded.
    """
    db = DatabaseManager()
    db.record_xp_event(
        user_id=USER_ALICE["id"],
        action="concept_mastery",
        amount=100,
        event_id="evt_alice_gravity_mastery",
        concept="gravity",
    )

    res = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "gravity_pioneer"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "awarded"
    assert res.json()["achievement_id"] == "gravity_pioneer"


# ==============================================================================
# 3. Event Evidence Security: Reject Client Booleans Without DB History
# ==============================================================================

def test_client_dummy_booleans_are_rejected_for_event_evidence():
    """
    A user with no AI tutor history submits:
    evidence: {"completed": True, "verified": True, "event_id": "fake_event"}
    to unlock 'curious_mind'.
    Must be rejected with HTTP 422 because no backing database record exists.
    """
    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "curious_mind",
            "evidence": {"completed": True, "verified": True, "event_id": "fake_event"},
        },
    )
    assert res.status_code == 422
    assert "no database-backed verification record found" in res.json()["detail"]


def test_verified_tutor_session_in_database_satisfies_event_evidence():
    """
    When Alice has genuine interactive tutor inquiry sessions saved in memories,
    'curious_mind' is successfully awarded.
    """
    db = DatabaseManager()
    db.save_memory(
        session_id="session_alice_123",
        text="Student inquired about orbital mechanics and gravitational acceleration.",
        embedding=[0.1] * 768,
        user_id=USER_ALICE["id"],
    )

    res = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "curious_mind"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "awarded"
    assert res.json()["achievement_id"] == "curious_mind"

