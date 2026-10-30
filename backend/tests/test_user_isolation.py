import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)

USER_A = {"id": "user_a_111", "email": "alice@neurolab.ai", "role": "authenticated"}
USER_B = {"id": "user_b_222", "email": "bob@neurolab.ai", "role": "authenticated"}


def auth_header_for(user: dict):
    # Dummy token string that maps to the simulated user via dependency override
    return {"Authorization": f"Bearer token_{user['id']}"}


@pytest.fixture(autouse=True)
def clean_and_setup_db(monkeypatch):
    """
    Sets up clean in-memory / local storage and mock authentication for testing isolation.
    """
    from app.core_backend.database.supabase_db import DatabaseManager, db_lock
    import app.core_backend.routes.experiments as exp_module
    import app.core_backend.routes.gamification as gam_module
    import app.core_backend.routes.tutor as tutor_module

    db_instance = DatabaseManager()
    with db_lock:
        db_instance._write_local({"experiments": [], "memories": [], "xp": {}})

    exp_module.db = db_instance
    gam_module.db = db_instance
    tutor_module.tutor_service.db = db_instance

    yield

    app.dependency_overrides.clear()


def set_active_user(user: dict):
    async def override_user(authorization=None):
        return user

    app.dependency_overrides[get_current_user] = override_user


def test_user_a_and_user_b_experiment_isolation():
    """
    Verification:
    1. Save an experiment for User A.
    2. Save an experiment for User B.
    3. Confirm that User A cannot retrieve User B's experiment history.
    4. Confirm that User B cannot retrieve User A's experiment history.
    """
    # 1. User A saves an experiment
    set_active_user(USER_A)
    exp_a_payload = {
        "user_id": USER_A["id"],
        "type": "free-fall",
        "metrics": {"max_velocity": 14.2, "duration": 1.45},
    }
    res_a = client.post("/api/experiments/save", json=exp_a_payload, headers=auth_header_for(USER_A))
    assert res_a.status_code == 200
    saved_exp_a = res_a.json()["experiment"]
    exp_a_id = saved_exp_a["id"]
    assert saved_exp_a["user_id"] == USER_A["id"]

    # 2. User B saves an experiment
    set_active_user(USER_B)
    exp_b_payload = {
        "user_id": USER_B["id"],
        "type": "pendulum",
        "metrics": {"period": 2.15, "amplitude": 30.0},
    }
    res_b = client.post("/api/experiments/save", json=exp_b_payload, headers=auth_header_for(USER_B))
    assert res_b.status_code == 200
    saved_exp_b = res_b.json()["experiment"]
    exp_b_id = saved_exp_b["id"]
    assert saved_exp_b["user_id"] == USER_B["id"]

    # 3. User A queries /history -> Expects ONLY User A's experiment
    set_active_user(USER_A)
    res_history_a = client.get("/api/experiments/history", headers=auth_header_for(USER_A))
    assert res_history_a.status_code == 200
    history_a = res_history_a.json()["history"]
    history_a_ids = [e["id"] for e in history_a]

    assert exp_a_id in history_a_ids
    assert exp_b_id not in history_a_ids  # User B's record is completely isolated

    # 4. User B queries /history -> Expects ONLY User B's experiment
    set_active_user(USER_B)
    res_history_b = client.get("/api/experiments/history", headers=auth_header_for(USER_B))
    assert res_history_b.status_code == 200
    history_b = res_history_b.json()["history"]
    history_b_ids = [e["id"] for e in history_b]

    assert exp_b_id in history_b_ids
    assert exp_a_id not in history_b_ids  # User A's record is completely isolated


def test_user_a_cannot_query_user_b_history_manually():
    """
    Verification:
    Confirm that User A attempting to query User B's history by manually
    passing user_id=User_B receives 403 Forbidden.
    """
    set_active_user(USER_A)
    res = client.get(
        f"/api/experiments/history?user_id={USER_B['id']}",
        headers=auth_header_for(USER_A),
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")


def test_user_a_cannot_save_under_user_b_identity():
    """
    Verification:
    Confirm that User A attempting to supply User B's ID in the request body
    is rejected with 403 Forbidden.
    """
    set_active_user(USER_A)
    spoofed_payload = {
        "user_id": USER_B["id"],  # User A attempting to save as User B
        "type": "free-fall",
        "metrics": {"cheating": True},
    }
    res = client.post(
        "/api/experiments/save",
        json=spoofed_payload,
        headers=auth_header_for(USER_A),
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json().get("detail", "")


def test_user_a_cannot_access_user_b_specific_experiment():
    """
    Verification:
    Confirm that User A cannot fetch User B's experiment by its ID.
    Must return 403 Forbidden.
    """
    # Create experiment as User B
    set_active_user(USER_B)
    res = client.post(
        "/api/experiments/save",
        json={"user_id": USER_B["id"], "type": "collision", "metrics": {}},
        headers=auth_header_for(USER_B),
    )
    exp_b_id = res.json()["experiment"]["id"]

    # User A tries to view User B's experiment
    set_active_user(USER_A)
    res_access = client.get(
        f"/api/experiments/experiment/{exp_b_id}",
        headers=auth_header_for(USER_A),
    )
    assert res_access.status_code == 403
    assert "Forbidden" in res_access.json().get("detail", "")


def test_gamification_xp_user_isolation():
    """
    Verification:
    1. Confirm that User A cannot award XP to User B (expects 403 Forbidden).
    2. Confirm that awarding XP updates only the canonical user's score.
    """
    set_active_user(USER_A)

    # User A attempts to award XP to User B
    tampered_xp = {
        "user_id": USER_B["id"],
        "action": "hack_xp",
        "amount": 500,
    }
    res_tamper = client.post(
        "/api/gamification/add-xp",
        json=tampered_xp,
        headers=auth_header_for(USER_A),
    )
    assert res_tamper.status_code == 403
    assert "Forbidden" in res_tamper.json().get("detail", "")

    # User A awards XP legitimately to own account
    legit_xp = {
        "user_id": USER_A["id"],
        "action": "completed_lab",
        "amount": 250,
    }
    res_legit = client.post(
        "/api/gamification/add-xp",
        json=legit_xp,
        headers=auth_header_for(USER_A),
    )
    assert res_legit.status_code == 200
    assert res_legit.json()["total_xp"] == 250

    # User A's XP endpoint returns 250
    res_a_xp = client.get("/api/gamification/my-xp", headers=auth_header_for(USER_A))
    assert res_a_xp.status_code == 200
    assert res_a_xp.json()["xp"] == 250

    # User B's XP remains 0
    set_active_user(USER_B)
    res_b_xp = client.get("/api/gamification/my-xp", headers=auth_header_for(USER_B))
    assert res_b_xp.status_code == 200
    assert res_b_xp.json()["xp"] == 0
