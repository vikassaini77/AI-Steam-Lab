"""
Test Suite for Problem 46: Model Versioning & Experiment Provenance Tracking.
Validates:
1. Model & version identifiers recorded on experiment saves and CV tracking.
2. Configuration, algorithm, and preprocessing versions stored.
3. Timestamp, frame metadata, calibration parameters, and measurement units recorded.
4. Inference status and error information captured.
5. Experiment input and output cryptographic provenance (SHA-256 hashes).
6. Privacy: Raw webcam footage is never stored by default without consent.
7. Verification: Reproduces stored experiment's derived metrics from recorded inputs and algorithm configuration.
8. Tamper detection: Modified inputs detect hash mismatch and delta during reproduction.
"""
import math
import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.models.provenance import (
    reproduce_experiment_metrics,
    compute_input_hash,
    compute_output_hash,
    strip_raw_footage,
)
from app.machine_learning.cv_service import CVTracker

client = TestClient(app)

TEST_USER = {
    "id": "physics_student_prov_01",
    "sub": "physics_student_prov_01",
    "role": "student",
}


@pytest.fixture(autouse=True)
def clean_db_and_auth():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    db = DatabaseManager()
    data = db._read_local()
    data["experiments"] = []
    db._write_local(data)

    yield

    app.dependency_overrides.clear()


# ==============================================================================
# 1. Model & Version Identifiers and Provenance Recording
# ==============================================================================

def test_save_experiment_records_full_provenance_and_model_versions():
    """
    Verifies that saving an experiment records:
    - Model and version identifiers (PhysicsEngine, v1.2.0).
    - Configuration, algorithm, and preprocessing versions.
    - Calibration parameters and measurement units.
    - Input and output cryptographic hashes.
    """
    payload = {
        "type": "free_fall",
        "height": 45.0,
        "mass": 2.5,
        "gravity": 9.81,
        "unit_system": "SI",
    }

    res = client.post("/api/experiments/save", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "saved"

    exp = data["experiment"]

    # 1. Model and version identifiers
    assert exp["model_name"] == "PhysicsEngine"
    assert "physics_engine" in exp["model_version"]
    assert exp["algorithm_version"] == "physics_engine_v1.0"
    assert exp["configuration_version"] == "config_v1.0"
    assert exp["preprocessing_version"] == "norm_v1.0"
    assert exp["computation_version"] == "kinematics_analytical_v1"

    # 2. Calibration and measurement units
    assert "calibration" in exp
    calib = exp["calibration"]
    assert calib["unit_system"] == "SI"
    assert "measurement_units" in calib
    assert calib["measurement_units"]["velocity"] == "meters/second (m/s)"
    assert calib["measurement_units"]["displacement"] == "meters (m)"

    # 3. Status and error information
    assert exp["inference_status"] == "completed"
    assert exp.get("error_info") is None

    # 4. Provenance audit lineage
    assert "provenance" in exp
    prov = exp["provenance"]
    assert prov["model"]["name"] == "PhysicsEngine"
    assert prov["reproducible"] is True
    assert "input_hash" in prov and len(prov["input_hash"]) == 64
    assert "output_hash" in prov and len(prov["output_hash"]) == 64
    assert "sqrt(2*g*h)" in prov["reproduction_formula"]
    assert "recorded_at" in prov


# ==============================================================================
# 2. Verification: Reproduce Stored Experiment Derived Metrics
# ==============================================================================

def test_reproduce_stored_free_fall_metrics():
    """
    Verification: Reproduces a stored free-fall experiment's derived metrics
    from its recorded inputs and algorithm configuration.
    """
    # 1. Save an experiment
    save_res = client.post(
        "/api/experiments/save",
        json={"type": "free_fall", "height": 80.0, "mass": 1.5, "gravity": 9.81},
    )
    assert save_res.status_code == 200
    exp_id = save_res.json()["experiment"]["id"]
    stored_results = save_res.json()["experiment"]["server_computed_results"]

    # 2. Call reproduction endpoint
    rep_res = client.post(f"/api/experiments/reproduce/{exp_id}")
    assert rep_res.status_code == 200
    report = rep_res.json()

    # 3. Verify reproduction
    assert report["reproduced"] is True
    assert report["experiment_id"] == exp_id
    assert report["experiment_type"] == "free_fall"
    assert report["max_absolute_delta"] < 1e-4
    assert report["input_hash_matches"] is True
    assert report["output_hash_matches"] is True

    # Confirm mathematical values match exactly
    recomputed = report["recomputed_metrics"]
    assert math.isclose(recomputed["final_velocity"], stored_results["final_velocity"], rel_tol=1e-5)
    assert math.isclose(recomputed["time_of_flight"], stored_results["time_of_flight"], rel_tol=1e-5)


def test_reproduce_stored_pendulum_metrics():
    """
    Verification: Reproduces a stored pendulum experiment's derived metrics.
    """
    save_res = client.post(
        "/api/experiments/save",
        json={"type": "pendulum", "length": 4.0, "angle_deg": 25.0, "damping": 0.05},
    )
    assert save_res.status_code == 200
    exp_id = save_res.json()["experiment"]["id"]

    rep_res = client.post(f"/api/experiments/reproduce/{exp_id}")
    assert rep_res.status_code == 200
    report = rep_res.json()

    assert report["reproduced"] is True
    assert report["max_absolute_delta"] < 1e-4
    assert report["input_hash_matches"] is True
    assert report["output_hash_matches"] is True


def test_reproduce_stored_collision_metrics():
    """
    Verification: Reproduces a stored elastic collision experiment's derived metrics.
    """
    save_res = client.post(
        "/api/experiments/save",
        json={
            "type": "collision",
            "mass_a": 2.0,
            "mass_b": 3.0,
            "vel_a": 5.0,
            "vel_b": -2.0,
            "collision_type": "elastic",
        },
    )
    assert save_res.status_code == 200
    exp_id = save_res.json()["experiment"]["id"]

    rep_res = client.post(f"/api/experiments/reproduce/{exp_id}")
    assert rep_res.status_code == 200
    report = rep_res.json()

    assert report["reproduced"] is True
    assert report["max_absolute_delta"] < 1e-4


def test_reproduction_detects_tampering_or_corrupted_inputs():
    """
    Confirms that if inputs are tampered with or modified after calculation,
    the reproduction engine detects the discrepancy and flags hash mismatch.
    """
    save_res = client.post(
        "/api/experiments/save",
        json={"type": "free_fall", "height": 50.0},
    )
    exp = save_res.json()["experiment"]

    # Tamper with recorded input: change height from 50 to 999
    tampered_record = dict(exp)
    tampered_record["input_data"] = dict(exp["input_data"])
    tampered_record["input_data"]["height"] = 999.0

    report = reproduce_experiment_metrics(tampered_record)

    # Input hash should NOT match original recorded hash
    assert report.input_hash_matches is False
    # Derived metrics will significantly differ
    assert report.max_absolute_delta > 10.0
    assert report.reproduced is False


# ==============================================================================
# 3. Privacy Policy: Never Store Raw Webcam Footage By Default
# ==============================================================================

def test_raw_webcam_footage_is_never_stored_without_consent():
    """
    Policy: Raw webcam footage or base64 frames must be stripped and never
    persisted into the experiment database record without explicit consent.
    """
    large_dummy_base64 = "data:image/jpeg;base64," + "A" * 50000

    payload = {
        "type": "free_fall",
        "height": 30.0,
        "consent_to_record": False,  # Explicitly NO consent
        "image": large_dummy_base64,
        "frame": large_dummy_base64,
        "parameters": {
            "webcam_base64": large_dummy_base64,
        },
    }

    res = client.post("/api/experiments/save", json=payload)
    assert res.status_code == 200
    exp = res.json()["experiment"]

    # Confirm raw footage is not in the stored record
    assert "image" not in exp
    assert "frame" not in exp
    assert "image" not in exp.get("input_data", {})
    assert "frame" not in exp.get("input_data", {})
    assert "webcam_base64" not in exp.get("input_data", {})

    # Confirm privacy flags in frame_metadata
    meta = exp["frame_metadata"]
    assert meta["raw_footage_stored"] is False
    assert meta["consent_to_record"] is False
    assert meta["retention_policy"] == "ephemeral_discard"


def test_strip_raw_footage_utility():
    """Verifies strip_raw_footage helper properly removes all media artifacts."""
    test_dict = {
        "height": 10.0,
        "image": "base64_data_here",
        "frame": "frame_data_here",
        "parameters": {
            "video": "mp4_buffer",
            "mass": 1.0,
        },
    }
    clean, stripped = strip_raw_footage(test_dict, consent_to_record=False)
    assert stripped is True
    assert "image" not in clean
    assert "frame" not in clean
    assert "video" not in clean["parameters"]
    assert clean["parameters"]["mass"] == 1.0


# ==============================================================================
# 4. Computer Vision Frame Tracking Provenance
# ==============================================================================

def test_cv_tracker_attaches_model_version_and_calibration():
    """
    Verifies that CV frame processing attaches model version, calibration scale,
    and privacy compliance flag (raw_footage_stored = False).
    """
    import numpy as np
    import cv2
    import base64

    # Create dummy 320x240 image with red circle
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.circle(img, (160, 120), 20, (0, 0, 255), -1)
    _, buf = cv2.imencode(".png", img)
    b64_str = base64.b64encode(buf.tobytes()).decode("utf-8")

    tracker = CVTracker()
    result = tracker.process_frame(
        base64_img=b64_str,
        tracking_method="color",
        color_target="red",
        px_to_meters=0.005,
    )

    # 1. Model and calibration metadata
    assert "model_version" in result
    assert "hsv_blob_tracker" in result["model_version"]
    assert result["configuration_version"] == "cv_config_v1.0"
    assert result["preprocessing_version"] == "bgr_to_hsv_v1"

    # 2. Calibration
    assert "calibration" in result
    assert result["calibration"]["px_to_meters"] == 0.005
    assert result["calibration"]["unit_system"] == "SI"

    # 3. Privacy flag: raw footage must NOT be stored
    assert result["raw_footage_stored"] is False
    assert result["provenance"]["raw_footage_stored"] is False
    assert result["provenance"]["retention_policy"] == "ephemeral_discard"

