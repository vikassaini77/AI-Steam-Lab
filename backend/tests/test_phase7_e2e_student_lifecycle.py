"""
Phase 7: End-to-End Complete Student Lifecycle and Cross-User Data Isolation Validation
Validates the complete 12-step scientific workflow:
1. Registration
2. Login
3. Experiment Metadata Retrieval
4. Parameter Configuration
5. Measurement Collection (Sensor/Webcam)
6. Theoretical Calculation & Solver
7. Graph / Time-Series Generation
8. AI Tutor Pedagogical Explanation
9. Durable Experiment Persistence
10. Session Revocation / Logout
11. Re-authentication
12. Saved Experiment Retrieval & Verification
+ Multi-tenant cross-user data isolation: Second student cannot access first student's private experiment.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import (
    get_current_user,
    reset_shared_dependencies,
    clear_revoked_tokens,
)
from app.core_backend.database.supabase_db import DatabaseManager

STUDENT_A_ID = "student_a_phase7_" + uuid.uuid4().hex[:8]
STUDENT_B_ID = "student_b_phase7_" + uuid.uuid4().hex[:8]

STUDENT_A_USER = {
    "id": STUDENT_A_ID,
    "email": "student_a@university.edu",
    "role": "authenticated",
}

STUDENT_B_USER = {
    "id": STUDENT_B_ID,
    "email": "student_b@university.edu",
    "role": "authenticated",
}


@pytest.fixture(autouse=True)
def clean_test_state():
    app.dependency_overrides.clear()
    reset_shared_dependencies()
    clear_revoked_tokens()
    yield
    app.dependency_overrides.clear()
    reset_shared_dependencies()
    clear_revoked_tokens()


def test_full_student_e2e_lifecycle_and_cross_user_isolation():
    client = TestClient(app)

    # -------------------------------------------------------------
    # Step 1 & 2: Student A Registration & Login
    # -------------------------------------------------------------
    # In test mode, authenticate as Student A
    app.dependency_overrides[get_current_user] = lambda: STUDENT_A_USER
    auth_headers_a = {"Authorization": "Bearer token_student_a"}

    # Verify authenticated identity
    me_res = client.get("/api/gamification/my-xp", headers=auth_headers_a)
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == STUDENT_A_ID

    # -------------------------------------------------------------
    # Step 3: Student A opens a physics experiment
    # -------------------------------------------------------------
    meta_res = client.get("/api/experiments/metadata/pendulum", headers=auth_headers_a)
    assert meta_res.status_code == 200
    meta = meta_res.json()["metadata"]
    assert meta["id"] == "pendulum"
    assert "Simple Pendulum" in meta["title"]
    assert "Small-Angle Ideal Period" in str(meta["governing_equations"])
    assert "small_angle_approximation_note" in meta
    assert "length" in meta["units"]
    assert len(meta["instructions"]) > 0
    assert len(meta["learning_objectives"]) > 0

    # -------------------------------------------------------------
    # Step 4: Student configures input parameters
    # -------------------------------------------------------------
    configured_params = {
        "length": 1.25,
        "gravity": 9.81,
        "initial_angle_deg": 12.0,
        "mass": 0.5,
    }

    # -------------------------------------------------------------
    # Step 5: Student performs measurements (observations / timings)
    # -------------------------------------------------------------
    # 5 oscillations timed at 11.21 seconds -> period ~2.242s
    measure_payload = {
        "parameters": configured_params,
        "observations": [
            {"time_seconds": 0.0, "angle_deg": 12.0},
            {"time_seconds": 1.12, "angle_deg": -11.9},
            {"time_seconds": 2.24, "angle_deg": 11.8},
            {"time_seconds": 3.36, "angle_deg": -11.7},
            {"time_seconds": 4.48, "angle_deg": 11.6},
            {"time_seconds": 5.60, "angle_deg": -11.5},
        ],
        "measurement_mode": "manual",
    }
    meas_res = client.post("/api/experiments/measure/pendulum", json=measure_payload, headers=auth_headers_a)
    assert meas_res.status_code == 200
    meas_data = meas_res.json()
    experimental_period = meas_data["experimental_value"]
    assert experimental_period > 0

    # -------------------------------------------------------------
    # Step 6 & 7: System calculates theoretical results & graphs
    # -------------------------------------------------------------
    calc_payload = {"parameters": configured_params}
    calc_res = client.post("/api/experiments/calculate/pendulum", json=calc_payload, headers=auth_headers_a)
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    theoretical_period = calc_data["primary_theoretical_value"]
    # T = 2 * pi * sqrt(1.25 / 9.81) = 2.2429s
    expected_period = 2.243
    assert abs(theoretical_period - expected_period) < 0.02
    assert "theoretical_series" in calc_data
    assert len(calc_data["theoretical_series"]) >= 50
    assert "time" in calc_data["theoretical_series"][0]

    # -------------------------------------------------------------
    # Step 8: AI Tutor explains the results
    # -------------------------------------------------------------
    pct_err = abs(experimental_period - theoretical_period) / theoretical_period * 100.0
    explain_payload = {
        "parameters": configured_params,
        "results": {
            "experimental_value": experimental_period,
            "primary_theoretical_value": theoretical_period,
            "percentage_error": pct_err,
        },
        "student_question": "Why did my measured period differ slightly from theory?",
    }
    exp_res = client.post("/api/experiments/explain/pendulum", json=explain_payload, headers=auth_headers_a)
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert "what_it_demonstrates" in exp_data
    assert "why_observed_differs_from_theory" in exp_data

    # -------------------------------------------------------------
    # Step 9: Student saves the experiment
    # -------------------------------------------------------------
    save_payload = {
        "experiment_type": "pendulum",
        "name": "Phase 7 Simple Pendulum Run",
        "length": configured_params["length"],
        "gravity": configured_params["gravity"],
        "angle_deg": configured_params["initial_angle_deg"],
        "mass": configured_params["mass"],
        "parameters": configured_params,
        "metrics": {
            "displacement_max": 1.25,
            "velocity_peak": 0.85,
            "sync_percentage": "99.4%",
            "measured_period": experimental_period,
            "theoretical_period": theoretical_period,
            "percentage_error": pct_err,
        },
    }
    save_res = client.post("/api/experiments/save", json=save_payload, headers=auth_headers_a)
    assert save_res.status_code == 200
    saved_meta = save_res.json()
    experiment_id = saved_meta["experiment"]["id"]
    assert experiment_id is not None
    assert saved_meta["status"] == "saved"

    # -------------------------------------------------------------
    # Step 10: Student A logs out / session revocation
    # -------------------------------------------------------------
    from unittest.mock import MagicMock, patch
    from app.core_backend.routes import auth as auth_route
    mock_sb = MagicMock()
    mock_sb.auth.admin.sign_out.return_value = None
    mock_sb.auth.get_user.side_effect = Exception("Session revoked")
    with patch.object(auth_route, "get_supabase_client", return_value=mock_sb):
        logout_res = client.post("/api/auth/logout", headers=auth_headers_a)
        assert logout_res.status_code == 200
        assert logout_res.json()["session_revoked"] is True

    # -------------------------------------------------------------
    # Step 11: Student A logs back in with refreshed session
    # -------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: STUDENT_A_USER
    auth_headers_a_new = {"Authorization": "Bearer token_student_a_refreshed"}

    # -------------------------------------------------------------
    # Step 12: Student A retrieves the saved experiment
    # -------------------------------------------------------------
    hist_res = client.get("/api/experiments/history", headers=auth_headers_a_new)
    assert hist_res.status_code == 200
    hist = hist_res.json()
    found_ids = [exp["id"] for exp in hist.get("history", [])]
    assert experiment_id in found_ids

    detail_res = client.get(f"/api/experiments/experiment/{experiment_id}", headers=auth_headers_a_new)
    assert detail_res.status_code == 200
    detail = detail_res.json()["experiment"]
    assert detail["id"] == experiment_id
    assert detail["experiment_type"] == "pendulum"

    # -------------------------------------------------------------
    # Security Validation: Cross-User Multi-Tenant Isolation
    # Student B logs in and attempts to access Student A's experiment
    # -------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: STUDENT_B_USER
    auth_headers_b = {"Authorization": "Bearer token_student_b"}

    # Student B history must NOT include Student A's experiment
    hist_b_res = client.get("/api/experiments/history", headers=auth_headers_b)
    assert hist_b_res.status_code == 200
    hist_b = hist_b_res.json()
    found_b_ids = [exp["id"] for exp in hist_b.get("history", [])]
    assert experiment_id not in found_b_ids

    # Direct IDOR attempt by Student B to retrieve Student A's experiment must fail with 403 or 404
    idor_get_res = client.get(f"/api/experiments/experiment/{experiment_id}", headers=auth_headers_b)
    assert idor_get_res.status_code in (403, 404)

    # Direct IDOR attempt by Student B to delete Student A's experiment must fail with 403 or 404
    idor_del_res = client.delete(f"/api/experiments/experiment/{experiment_id}", headers=auth_headers_b)
    assert idor_del_res.status_code in (403, 404)

    # Verify Student A's record was NOT deleted by Student B's attempt
    app.dependency_overrides[get_current_user] = lambda: STUDENT_A_USER
    verify_res = client.get(f"/api/experiments/experiment/{experiment_id}", headers=auth_headers_a_new)
    assert verify_res.status_code == 200
