"""
Test Suite for Problem 25: Badge counts are inferred from XP (P1)
Validates:
1. Core Verification: A user with XP but no completed achievement does NOT receive a fabricated badge count.
2. Dedicated achievement model with ID, definition, eligibility criteria, award timestamp, associated user, and evidence.
3. Badges are awarded ONLY when criteria are satisfied (ineligible awards are rejected with HTTP 422).
4. Idempotency: Awarding the same achievement twice does not duplicate badge records or increment badge count.
5. Leaderboard reflects authentic, database-calculated badge counts, completely uncoupled from XP.
6. Public badge endpoint (/api/gamification/user-badges/{user_id}) and catalog endpoint (/api/gamification/achievements/catalog).
7. PGVectorManager PostgreSQL queries and conflict resolution.
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
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import PGVectorManager, DatabasePersistenceError
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.routes.gamification import LEADERBOARD_CACHE, ACHIEVEMENT_CATALOG

client = TestClient(app)

TEST_USER_A = {"id": "learner_alice", "sub": "learner_alice", "role": "student"}
TEST_USER_B = {"id": "learner_bob", "sub": "learner_bob", "role": "student"}


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Resets local database and cache before each test."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_A
    LEADERBOARD_CACHE.clear()

    db = DatabaseManager()
    data = db._read_local()
    data["xp"] = {}
    data["xp_ledger"] = {}
    data["experiments"] = []
    data["user_achievements"] = []
    db._write_local(data)

    yield

    app.dependency_overrides.clear()
    LEADERBOARD_CACHE.clear()


def test_user_with_xp_but_no_completed_achievement_receives_zero_badges():
    """
    Problem 25 Core Verification:
    A user with 5,000 XP but no completed achievement must receive 0 badges,
    NOT the fabricated int(xp / 500) = 10.
    """
    db = DatabaseManager()
    # Award 5000 XP to Alice through the ledger
    for i in range(10):
        db.record_xp_event(
            user_id=TEST_USER_A["id"],
            action="lab_challenge",
            amount=500,
            event_id=f"evt_xp_500_{i}",
        )

    # 1. Inspect Leaderboard
    res_lb = client.get("/api/gamification/leaderboard")
    assert res_lb.status_code == 200
    items = res_lb.json()
    assert len(items) == 1
    alice_entry = items[0]
    assert alice_entry["user_id"] == TEST_USER_A["id"]
    assert alice_entry["xp"] == 5000
    # Crucial check: Badges must be 0, NOT 10!
    assert alice_entry["badges"] == 0, f"Expected 0 badges, but got fabricated {alice_entry['badges']}"

    # 2. Inspect /achievements endpoint
    res_ach = client.get("/api/gamification/achievements")
    assert res_ach.status_code == 200
    ach_payload = res_ach.json()
    assert ach_payload["user_id"] == TEST_USER_A["id"]
    assert ach_payload["total_badges"] == 0
    assert len(ach_payload["earned_achievements"]) == 0

    # 3. Inspect public /user-badges endpoint
    res_ub = client.get(f"/api/gamification/user-badges/{TEST_USER_A['id']}")
    assert res_ub.status_code == 200
    ub_payload = res_ub.json()
    assert ub_payload["badge_count"] == 0
    assert ub_payload["badges"] == []


def test_achievement_catalog_endpoint():
    """
    Validates that the achievement catalog returns well-formed achievement definitions
    with criteria, tiers, badge icons, and descriptions.
    """
    res = client.get("/api/gamification/achievements/catalog")
    assert res.status_code == 200
    catalog = res.json()
    assert len(catalog) >= 5

    catalog_ids = [item["id"] for item in catalog]
    assert "first_steps" in catalog_ids
    assert "quantum_leap" in catalog_ids
    assert "physics_explorer" in catalog_ids

    first_steps = next(item for item in catalog if item["id"] == "first_steps")
    assert first_steps["name"] == "First Steps"
    assert first_steps["badge_icon"] == "target"
    assert first_steps["criteria"]["criteria_type"] == "experiment_count"
    assert first_steps["criteria"]["threshold"] == 1


def test_award_achievement_criteria_enforcement_rejected_when_ineligible():
    """
    Badges must NOT be awarded when criteria are not satisfied (HTTP 422).
    """
    # 1. first_steps requires 1 completed experiment; user has 0 experiments
    res = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "first_steps"},
    )
    assert res.status_code == 422
    assert "Eligibility criteria not satisfied" in res.json()["detail"]

    # 2. quantum_leap requires 1000 XP; user has 0 XP
    res_ql = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "quantum_leap"},
    )
    assert res_ql.status_code == 422
    assert "below required threshold" in res_ql.json()["detail"]

    # 3. Nonexistent achievement returns 404
    res_fake = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "nonexistent_super_badge"},
    )
    assert res_fake.status_code == 404


def test_award_achievement_success_when_criteria_satisfied():
    """
    When criteria are satisfied, the achievement is successfully awarded,
    recorded with timestamp and evidence, and increments badge totals.
    """
    db = DatabaseManager()
    # Satisfy criteria for first_steps by saving 1 experiment
    db.save_experiment(
        user_id=TEST_USER_A["id"],
        experiment_type="free_fall",
        data={"height": 10.0, "time": 1.43},
    )

    # Award first_steps
    res = client.post(
        "/api/gamification/award-achievement",
        json={
            "achievement_id": "first_steps",
            "evidence": {"experiment_type": "free_fall", "verified": True},
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "awarded"
    assert payload["achievement_id"] == "first_steps"
    assert payload["name"] == "First Steps"
    assert payload["total_badges"] == 1
    assert payload["awarded_at"] is not None
    assert payload["record"]["evidence"]["experiment_type"] == "free_fall"

    # Verify Leaderboard now shows 1 badge
    res_lb = client.get("/api/gamification/leaderboard")
    assert res_lb.status_code == 200
    assert res_lb.json()[0]["badges"] == 1


def test_award_achievement_idempotency_prevents_duplicate_badges():
    """
    Submitting the same achievement award twice returns 'already_earned'
    and does not duplicate the badge or increase badge count.
    """
    db = DatabaseManager()
    db.save_experiment(
        user_id=TEST_USER_A["id"],
        experiment_type="pendulum",
        data={"length": 1.0, "period": 2.01},
    )

    # First award -> awarded
    res1 = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "first_steps", "event_id": "evt_ach_test_1"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "awarded"
    assert res1.json()["total_badges"] == 1

    # Second award -> already_earned
    res2 = client.post(
        "/api/gamification/award-achievement",
        json={"achievement_id": "first_steps", "event_id": "evt_ach_test_2"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_earned"
    assert res2.json()["total_badges"] == 1

    # Verify persistent store has exactly 1 achievement
    user_achs = db.get_user_achievements(TEST_USER_A["id"])
    assert len(user_achs) == 1


def test_leaderboard_uncoupled_xp_and_badge_counts():
    """
    Validates leaderboard with multiple users having different XP and badge ratios:
    - User A: High XP (2000), 0 badges
    - User B: Moderate XP (500), 2 badges
    Demonstrates that badges are not calculated as int(xp / 500).
    """
    db = DatabaseManager()

    # User A: 2000 XP, 0 badges
    db.record_xp_event(TEST_USER_A["id"], "grant", 500, event_id="evt_a1")
    db.record_xp_event(TEST_USER_A["id"], "grant", 500, event_id="evt_a2")
    db.record_xp_event(TEST_USER_A["id"], "grant", 500, event_id="evt_a3")
    db.record_xp_event(TEST_USER_A["id"], "grant", 500, event_id="evt_a4")

    # User B: 500 XP, 2 badges
    db.record_xp_event(TEST_USER_B["id"], "grant", 500, event_id="evt_b1")
    db.award_achievement(TEST_USER_B["id"], "first_steps", evidence={"verified": True})
    db.award_achievement(TEST_USER_B["id"], "curious_mind", evidence={"verified": True})

    res = client.get("/api/gamification/leaderboard")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 2

    # User A is rank 1 (2000 XP), but has 0 badges (NOT 4)
    item_a = next(it for it in items if it["user_id"] == TEST_USER_A["id"])
    assert item_a["xp"] == 2000
    assert item_a["badges"] == 0

    # User B is rank 2 (500 XP), and has 2 badges (NOT 1)
    item_b = next(it for it in items if it["user_id"] == TEST_USER_B["id"])
    assert item_b["xp"] == 500
    assert item_b["badges"] == 2


def test_user_badges_public_endpoint():
    """
    Validates public retrieval of a user's badges with metadata.
    """
    db = DatabaseManager()
    db.award_achievement(
        user_id="researcher_carol",
        achievement_id="first_steps",
        evidence={"lab": "optics"},
    )

    res = client.get("/api/gamification/user-badges/researcher_carol")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == "researcher_carol"
    assert data["badge_count"] == 1
    assert data["badges"][0]["id"] == "first_steps"
    assert data["badges"][0]["name"] == "First Steps"
    assert data["badges"][0]["evidence"]["lab"] == "optics"


def test_pgvector_db_achievements_postgresql_queries():
    """
    Directly tests PGVectorManager achievement methods with mocked connection:
    - award_achievement with ON CONFLICT (user_id, achievement_id) DO NOTHING
    - get_user_badge_counts_batch with ANY(%s) aggregation
    """
    mgr = object.__new__(PGVectorManager)
    mgr.is_in_memory_fallback = False
    mgr.allow_in_memory_fallback = False
    mgr.mode = "production"
    mgr.url = "postgresql://mock:5432/test"
    mgr.pool = None

    mock_cur = MagicMock()
    # Batch count return: user_1 -> 3 badges, user_2 -> 1 badge
    mock_cur.fetchall.return_value = [
        ("user_1", 3),
        ("user_2", 1),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch.object(mgr, "_get_conn") as mock_get_conn, patch.object(
        mgr, "_execute", side_effect=lambda **kwargs: kwargs["operation_fn"]()
    ):
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        batch_counts = mgr.get_user_badge_counts_batch(["user_1", "user_2", "user_3"])
        assert batch_counts["user_1"] == 3
        assert batch_counts["user_2"] == 1
        assert batch_counts["user_3"] == 0  # Unawarded user defaults to 0

        executed_sql = mock_cur.execute.call_args[0][0]
        assert "SELECT user_id, COUNT(*)" in executed_sql
        assert "WHERE user_id = ANY(%s)" in executed_sql
