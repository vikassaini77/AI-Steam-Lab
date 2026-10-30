"""
Test Suite for Problem 26: The experiment endpoint accepts arbitrary experiment types (P1)
Validates:
1. Rejects unsupported experiment types with HTTP 400.
2. Distinct schemas with physics validation for free-fall, pendulum, collision, and harmonic motion.
3. Rejection of missing required parameters (HTTP 422).
4. Rejection of invalid unit systems (HTTP 422).
5. Rejection of non-finite values (NaN, +Inf, -Inf) (HTTP 422).
6. Parameter bounds & coordinate ranges (negative height, length, mass, extreme angle).
7. Server-computed authoritative results overriding client-supplied metrics.
8. Separate persistence of input data, algorithm version, and computed results.
"""
import json
import math
import os
import pytest
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.supabase_db import DatabaseManager

client = TestClient(app)

TEST_USER = {"id": "physics_student_01", "sub": "physics_student_01", "role": "student"}


@pytest.fixture(autouse=True)
def override_auth_and_clean_db():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    db = DatabaseManager()
    data = db._read_local()
    data["experiments"] = []
    db._write_local(data)

    yield

    app.dependency_overrides.clear()


def test_unsupported_experiment_types_rejected_with_400():
    """
    Submitting an unsupported experiment type must return HTTP 400 Bad Request
    with an explicit error message listing supported types.
    """
    # 1. Analyze endpoint
    res_ana = client.post("/api/experiments/analyze/alchemy", json={"potions": 3})
    assert res_ana.status_code == 400
    assert "Unsupported experiment type: 'alchemy'" in res_ana.json()["detail"]
    assert "Supported types are: collision, free_fall, harmonic_motion, pendulum" in res_ana.json()["detail"]

    # 2. Save endpoint
    res_save = client.post("/api/experiments/save", json={"type": "perpetual_motion_engine"})
    assert res_save.status_code == 400
    assert "Unsupported experiment type: 'perpetual_motion_engine'" in res_save.json()["detail"]


def test_missing_required_parameters_rejected_with_422():
    """
    Submitting an experiment without its required parameters must be rejected with HTTP 422.
    """
    # 1. Free fall without height
    res_ff = client.post("/api/experiments/analyze/free-fall", json={"mass": 2.0})
    assert res_ff.status_code == 422
    assert "Physics schema validation failed" in res_ff.json()["detail"]

    # 2. Pendulum without length
    res_pen = client.post("/api/experiments/analyze/pendulum", json={"angle_deg": 30.0})
    assert res_pen.status_code == 422
    assert "Physics schema validation failed" in res_pen.json()["detail"]

    # 3. Collision without initial velocities and masses
    res_col = client.post("/api/experiments/analyze/collision", json={"collision_type": "Elastic"})
    assert res_col.status_code == 422
    assert "Physics schema validation failed" in res_col.json()["detail"]


def test_invalid_units_rejected_with_422():
    """
    Submitting an unsupported unit system must be rejected with HTTP 422.
    """
    # Free fall with non-SI units
    res = client.post(
        "/api/experiments/analyze/free-fall",
        json={"height": 50.0, "unit_system": "imperial_furlongs_per_fortnight"},
    )
    assert res.status_code == 422
    assert "Unsupported unit system" in res.json()["detail"]

    # Pendulum with bogus unit system
    res_pen = client.post(
        "/api/experiments/analyze/pendulum",
        json={"length": 2.0, "unit_system": "cubits"},
    )
    assert res_pen.status_code == 422
    assert "Unsupported unit system" in res_pen.json()["detail"]


def test_non_finite_values_rejected_with_422():
    """
    Submitting non-finite values (NaN, +Infinity, -Infinity) must be rejected with HTTP 422.
    """
    headers = {"Content-Type": "application/json"}

    # 1. NaN in height
    res_nan = client.post(
        "/api/experiments/analyze/free-fall",
        content=json.dumps({"height": float("nan")}, allow_nan=True),
        headers=headers,
    )
    assert res_nan.status_code == 422
    assert "must be a finite real number" in res_nan.json()["detail"]

    # 2. Positive Infinity in height
    res_inf = client.post(
        "/api/experiments/analyze/free-fall",
        content=json.dumps({"height": float("inf")}, allow_nan=True),
        headers=headers,
    )
    assert res_inf.status_code == 422
    assert "must be a finite real number" in res_inf.json()["detail"]

    # 3. Negative Infinity in length
    res_ninf = client.post(
        "/api/experiments/analyze/pendulum",
        content=json.dumps({"length": -float("inf")}, allow_nan=True),
        headers=headers,
    )
    assert res_ninf.status_code == 422
    assert "must be a finite real number" in res_ninf.json()["detail"]

    # 4. NaN in collision velocity
    res_col_nan = client.post(
        "/api/experiments/analyze/collision",
        content=json.dumps({"mass_a": 1.0, "mass_b": 1.0, "vel_a": float("nan"), "vel_b": -1.0}, allow_nan=True),
        headers=headers,
    )
    assert res_col_nan.status_code == 422
    assert "must be a finite real number" in res_col_nan.json()["detail"]


def test_coordinate_ranges_and_parameter_bounds():
    """
    Validates physical coordinate ranges and parameter bounds.
    """
    # 1. Non-positive height (<= 0)
    res_neg_h = client.post("/api/experiments/analyze/free-fall", json={"height": -10.0})
    assert res_neg_h.status_code == 422

    # 2. Non-positive mass (<= 0)
    res_neg_m = client.post("/api/experiments/analyze/free-fall", json={"height": 10.0, "mass": 0.0})
    assert res_neg_m.status_code == 422

    # 3. Angle out of valid -180 to 180 degree bounds
    res_angle = client.post("/api/experiments/analyze/pendulum", json={"length": 2.0, "angle_deg": 270.0})
    assert res_angle.status_code == 422

    # 4. Negative damping coefficient
    res_damp = client.post("/api/experiments/analyze/pendulum", json={"length": 2.0, "damping": -0.5})
    assert res_damp.status_code == 422

    # 5. Invalid collision type
    res_col = client.post(
        "/api/experiments/analyze/collision",
        json={"mass_a": 1.0, "mass_b": 1.0, "vel_a": 2.0, "vel_b": -2.0, "collision_type": "QuantumWarp"},
    )
    assert res_col.status_code == 422
    assert "Must be 'Elastic' or 'Inelastic'" in res_col.json()["detail"]


def test_server_computed_results_override_client_supplied_metrics():
    """
    Validates that the server computes authoritative results from validated inputs
    and does NOT treat client-supplied metrics as authoritative scientific truth.
    """
    # Client sends a drop height of 20 meters, but fabricates an impossible velocity of 99999 m/s
    payload = {
        "type": "free_fall",
        "height": 20.0,
        "mass": 1.0,
        "gravity": 9.81,
        "metrics": {
            "fabricated_speed": 99999.0,
            "impossible_energy": -5000.0,
        },
    }

    res = client.post("/api/experiments/save", json=payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "saved"

    exp = res_data["experiment"]

    # 1. Authoritative server computation
    # Expected v = sqrt(2 * g * h) = sqrt(2 * 9.81 * 20) = sqrt(392.4) ≈ 19.809 m/s
    # Expected t = sqrt(2 * h / g) = sqrt(40 / 9.81) ≈ 2.019 s
    computed = exp["server_computed_results"]
    assert math.isclose(computed["final_velocity"], 19.809, rel_tol=1e-2)
    assert math.isclose(computed["time_of_flight"], 2.019, rel_tol=1e-2)

    # 2. Metrics in database contains authoritative server-computed results, not the fake 99999!
    assert exp["metrics"]["final_velocity"] == computed["final_velocity"]
    assert "fabricated_speed" not in exp["server_computed_results"]

    # 3. Client claims are safely retained under client_supplied_metrics for audit only
    assert exp["client_supplied_metrics"]["fabricated_speed"] == 99999.0


def test_separate_persistence_of_input_data_algorithm_version_and_results():
    """
    Validates that input data, algorithm version, and computed results
    are saved as distinct, structured fields in the database.
    """
    payload = {
        "type": "pendulum",
        "length": 3.0,
        "angle_deg": 30.0,
        "damping": 0.1,
    }

    res = client.post("/api/experiments/save", json=payload)
    assert res.status_code == 200
    exp = res.json()["experiment"]

    # Separated fields in persistent record
    assert "input_data" in exp
    assert exp["input_data"]["length"] == 3.0
    assert exp["input_data"]["angle_deg"] == 30.0
    assert exp["input_data"]["damping"] == 0.1

    assert "algorithm_version" in exp
    assert exp["algorithm_version"] == "physics_engine_v1.0"

    assert "server_computed_results" in exp
    assert exp["server_computed_results"]["theoretical_period"] > 0.0

    assert "client_supplied_metrics" in exp
    assert "timestamp" in exp
    assert exp["user_id"] == TEST_USER["id"]
