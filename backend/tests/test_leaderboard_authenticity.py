"""
Test Suite for Problem 24: The leaderboard contains fabricated users (P1)
Validates:
1. No fabricated/mock users in production responses.
2. Authentic database-driven scoring and ranking via deterministic ordering (ROW_NUMBER / tie-breaking).
3. Pagination support (limit, offset) and headers (X-Total-Count, X-Limit, X-Offset, X-Cache).
4. In-memory TTL caching and invalidation on XP mutations.
5. PII and privacy protection: display names masked with pseudonyms, no email addresses leaked.
6. Demo data seeding strictly prohibited in production (HTTP 403) and enabled in development.
7. Verification: Insert a known set of users and XP totals, call the leaderboard endpoint, and verify exact ordering and ranks.
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
from app.core_backend.database.pgvector_db import PGVectorManager
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.routes.gamification import LEADERBOARD_CACHE, mask_user_display_name

client = TestClient(app)

TEST_ADMIN = {"id": "test_admin_user", "sub": "test_admin_user", "role": "admin"}


@pytest.fixture(autouse=True)
def clean_db_and_cache():
    """Resets local storage and clears the leaderboard cache before each test."""
    app.dependency_overrides[get_current_user] = lambda: TEST_ADMIN
    LEADERBOARD_CACHE.clear()

    db = DatabaseManager()
    data = db._read_local()
    data["xp"] = {}
    data["xp_ledger"] = {}
    db._write_local(data)

    yield

    app.dependency_overrides.clear()
    LEADERBOARD_CACHE.clear()


def test_leaderboard_contains_no_fabricated_mock_users_in_production(monkeypatch):
    """
    Problem 24 Core Requirement:
    Remove mock users (Sarah Chen, David Park, etc.) from production responses.
    Empty database must return an empty list, not fake peer records.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Standard call to empty database
    res = client.get("/api/gamification/leaderboard")
    assert res.status_code == 200
    data = res.json()
    assert data == [], f"Expected empty list in production for empty DB, got: {data}"

    # Even if client explicitly passes include_demo=true, production must reject/ignore it
    res_demo = client.get("/api/gamification/leaderboard?include_demo=true")
    assert res_demo.status_code == 200
    assert res_demo.json() == []

    # Verify none of the old mock user IDs or names appear
    mock_names = ["Sarah Chen", "David Park", "Elena Rodriguez", "James Wilson"]
    for item in res.json():
        assert item.get("name") not in mock_names
        assert not str(item.get("id")).startswith("mock_")


def test_leaderboard_exact_ordering_and_ranks():
    """
    Verification:
    Insert a known set of users and XP totals, call the leaderboard endpoint,
    and verify the exact ordering and computed ranks.
    """
    db = DatabaseManager()
    # Insert 3 users with known XP values
    db.record_xp_event("student_charlie", "lab_complete", 300, event_id="evt_c1")
    db.record_xp_event("student_alice", "lab_complete", 500, event_id="evt_a1")
    db.record_xp_event("student_alice", "quiz_pass", 500, event_id="evt_a2")  # Alice total: 1000
    db.record_xp_event("student_bob", "concept_mastery", 450, event_id="evt_b1")  # Bob total: 450

    res = client.get("/api/gamification/leaderboard")
    assert res.status_code == 200
    items = res.json()

    assert len(items) == 3
    # 1st place: Alice (1000 XP)
    assert items[0]["user_id"] == "student_alice"
    assert items[0]["xp"] == 1000
    assert items[0]["rank"] == 1

    # 2nd place: Bob (450 XP)
    assert items[1]["user_id"] == "student_bob"
    assert items[1]["xp"] == 450
    assert items[1]["rank"] == 2

    # 3rd place: Charlie (300 XP)
    assert items[2]["user_id"] == "student_charlie"
    assert items[2]["xp"] == 300
    assert items[2]["rank"] == 3


def test_leaderboard_deterministic_tie_breaking():
    """
    When users have identical XP totals, ranks must be deterministically ordered
    by user_id ascending (consistent across calls).
    """
    db = DatabaseManager()
    db.record_xp_event("user_zeta", "award", 250, event_id="evt_z1")
    db.record_xp_event("user_alpha", "award", 250, event_id="evt_a1")
    db.record_xp_event("user_gamma", "award", 250, event_id="evt_g1")

    res = client.get("/api/gamification/leaderboard")
    assert res.status_code == 200
    items = res.json()

    assert len(items) == 3
    # All 250 XP -> alphabetical tie-breaking: alpha (1), gamma (2), zeta (3)
    assert items[0]["user_id"] == "user_alpha"
    assert items[0]["rank"] == 1
    assert items[1]["user_id"] == "user_gamma"
    assert items[1]["rank"] == 2
    assert items[2]["user_id"] == "user_zeta"
    assert items[2]["rank"] == 3


def test_leaderboard_pagination_and_headers():
    """
    Validates pagination (limit, offset) and metadata headers:
    X-Total-Count, X-Limit, X-Offset, X-Cache.
    """
    db = DatabaseManager()
    for i in range(1, 6):
        db.record_xp_event(f"user_{i:02d}", "award", i * 100, event_id=f"evt_{i}")

    # Total users = 5, ordered 500, 400, 300, 200, 100

    # Page 1: limit 2, offset 0 -> ranks 1 and 2
    res_p1 = client.get("/api/gamification/leaderboard?limit=2&offset=0")
    assert res_p1.status_code == 200
    p1_items = res_p1.json()
    assert len(p1_items) == 2
    assert p1_items[0]["rank"] == 1
    assert p1_items[0]["xp"] == 500
    assert p1_items[1]["rank"] == 2
    assert p1_items[1]["xp"] == 400
    assert res_p1.headers["x-total-count"] == "5"
    assert res_p1.headers["x-limit"] == "2"
    assert res_p1.headers["x-offset"] == "0"

    # Page 2: limit 2, offset 2 -> ranks 3 and 4 (rank continuity)
    res_p2 = client.get("/api/gamification/leaderboard?limit=2&offset=2")
    assert res_p2.status_code == 200
    p2_items = res_p2.json()
    assert len(p2_items) == 2
    assert p2_items[0]["rank"] == 3
    assert p2_items[0]["xp"] == 300
    assert p2_items[1]["rank"] == 4
    assert p2_items[1]["xp"] == 200
    assert res_p2.headers["x-total-count"] == "5"
    assert res_p2.headers["x-limit"] == "2"
    assert res_p2.headers["x-offset"] == "2"

    # Page 3: limit 2, offset 4 -> rank 5
    res_p3 = client.get("/api/gamification/leaderboard?limit=2&offset=4")
    assert res_p3.status_code == 200
    p3_items = res_p3.json()
    assert len(p3_items) == 1
    assert p3_items[0]["rank"] == 5
    assert p3_items[0]["xp"] == 100


def test_leaderboard_caching_and_mutation_invalidation():
    """
    Validates in-memory TTL caching:
    - 1st call: X-Cache MISS
    - 2nd call: X-Cache HIT
    - XP mutation: invalidates cache
    - 3rd call: X-Cache MISS
    """
    db = DatabaseManager()
    db.record_xp_event("user_cache_test", "award", 200, event_id="evt_cache_1")

    # 1. First fetch -> MISS
    res1 = client.get("/api/gamification/leaderboard?limit=5&offset=0")
    assert res1.status_code == 200
    assert res1.headers["x-cache"] == "MISS"
    assert len(res1.json()) == 1

    # 2. Second fetch -> HIT
    res2 = client.get("/api/gamification/leaderboard?limit=5&offset=0")
    assert res2.status_code == 200
    assert res2.headers["x-cache"] == "HIT"

    # 3. Award new XP via add-xp endpoint
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_cache_test", "role": "student"}
    res_award = client.post(
        "/api/gamification/add-xp",
        json={"amount": 100, "action": "quiz", "event_id": "evt_cache_2"},
    )
    assert res_award.status_code == 200
    assert res_award.json()["awarded"] is True

    # 4. Third fetch -> MISS (invalidated) and returns updated XP (300)
    res3 = client.get("/api/gamification/leaderboard?limit=5&offset=0")
    assert res3.status_code == 200
    assert res3.headers["x-cache"] == "MISS"
    assert res3.json()[0]["xp"] == 300


def test_leaderboard_pii_and_privacy_masking():
    """
    Validates privacy protection:
    - Displays pseudonymized names (e.g. Scientist Ali*** or Scientist A1B2).
    - Prevents leaking raw email addresses in public responses.
    - Preserves user_id for frontend client highlighting.
    """
    db = DatabaseManager()
    db.record_xp_event("alexander.smith@cambridge.ac.uk", "research", 350, event_id="evt_pii_1")
    db.record_xp_event("usr-8f3a-92bc", "research", 250, event_id="evt_pii_2")

    res = client.get("/api/gamification/leaderboard")
    assert res.status_code == 200
    items = res.json()

    assert len(items) == 2
    # Email user
    email_user = next(it for it in items if "cambridge" in it["user_id"])
    assert email_user["name"] == "Scientist Ale***"
    assert "@" not in email_user["name"]
    assert "cambridge" not in email_user["name"]
    assert email_user["avatar"] is None

    # Alphanumeric user
    alpha_user = next(it for it in items if it["user_id"] == "usr-8f3a-92bc")
    assert alpha_user["name"] == "Scientist USR8"
    assert alpha_user["avatar"] is None


def test_demo_seed_endpoint_forbidden_in_production(monkeypatch):
    """
    Demo data seeding must be strictly forbidden in production (HTTP 403).
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    res = client.post("/api/gamification/seed-demo-leaderboard")
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_demo_seed_endpoint_allowed_in_development(monkeypatch):
    """
    In development environments, demo seeding successfully populates realistic learners.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")

    res = client.post("/api/gamification/seed-demo-leaderboard")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "success"
    assert payload["seeded_users"] > 0

    # Verify leaderboard now contains the seeded learners with authentic ranks
    res_lb = client.get("/api/gamification/leaderboard")
    assert res_lb.status_code == 200
    lb_items = res_lb.json()
    assert len(lb_items) >= 5

    # Check top ranks
    assert lb_items[0]["rank"] == 1
    assert lb_items[0]["xp"] == 1500
    assert lb_items[1]["rank"] == 2
    assert lb_items[1]["xp"] == 1200


def test_pgvector_db_leaderboard_window_function_execution():
    """
    Validates PGVectorManager.get_leaderboard SQL construction:
    Uses ROW_NUMBER() window function, deterministic ordering, and filters xp > 0.
    """
    mgr = object.__new__(PGVectorManager)
    mgr.is_in_memory_fallback = False
    mgr.allow_in_memory_fallback = False
    mgr.mode = "production"
    mgr.url = "postgresql://mock:5432/test"
    mgr.pool = None

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = [
        ("user_101", 5000, 1),
        ("user_102", 3500, 2),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    with patch.object(mgr, "_get_conn") as mock_get_conn, patch.object(mgr, "_execute", side_effect=lambda **kwargs: kwargs["operation_fn"]()):
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        results = mgr.get_leaderboard(limit=2, offset=0)
        assert len(results) == 2
        assert results[0] == {"id": "user_101", "user_id": "user_101", "rank": 1, "xp": 5000}
        assert results[1] == {"id": "user_102", "user_id": "user_102", "rank": 2, "xp": 3500}

        # Inspect SQL executed
        executed_sql = mock_cur.execute.call_args[0][0]
        params = mock_cur.execute.call_args[0][1]
        assert "ROW_NUMBER() OVER (ORDER BY xp DESC, user_id ASC) AS rank" in executed_sql
        assert "WHERE xp > 0" in executed_sql
        assert params == (2, 0)

