import math
import pytest
from app.machine_learning.cv_service import TrajectoryTracker, KinematicsResult
from app.core_backend.database.supabase_db import DatabaseManager


# ==============================================================================
# 1. TrajectoryTracker Analytical Trajectory Tests
# ==============================================================================

def test_trajectory_tracker_uniform_linear_motion():
    """
    Analytical Test: Object moving horizontally at constant velocity vx = 2.0 m/s.
    px_to_meters = 0.01 (100 px = 1 meter).
    x(t) = 200 * t (px) -> 2.0 * t (m).
    After filter warmup, velocity_x should approach 2.0 m/s, velocity_y ~ 0, and acceleration ~ 0.
    """
    tracker = TrajectoryTracker(pos_filter_alpha=1.0, vel_filter_beta=1.0)
    dt = 0.1  # 10 Hz
    t0 = 1000.0
    scale = 0.01
    v0_m = 2.0

    res = None
    for i in range(15):
        t = t0 + i * dt
        cx = int(round((v0_m / scale) * (i * dt)))
        cy = 150
        res = tracker.update((cx, cy), timestamp_seconds=t, px_to_meters=scale)

    assert res is not None
    # Velocity x should equal 2.0 m/s
    assert pytest.approx(res.details["velocity_x_mps"], abs=0.05) == 2.0
    # Velocity y should be 0
    assert pytest.approx(res.details["velocity_y_mps"], abs=0.01) == 0.0
    # Acceleration magnitude should be approximately 0
    assert pytest.approx(res.acceleration_mps2, abs=0.05) == 0.0
    # Vector direction is preserved
    assert res.details["velocity_x_mps"] > 0


def test_trajectory_tracker_vector_direction_reversal():
    """
    Direction Preservation: Object moves right (vx > 0), stops, then reverses left (vx < 0).
    Verifies that directional vector signs are preserved and acceleration reflects the reversal.
    """
    tracker = TrajectoryTracker(pos_filter_alpha=1.0, vel_filter_beta=1.0)
    scale = 0.01
    dt = 0.1
    t0 = 2000.0

    # Move right: x = 0 -> 200 px
    tracker.update((0, 100), timestamp_seconds=t0, px_to_meters=scale)
    res_right = tracker.update((20, 100), timestamp_seconds=t0 + dt, px_to_meters=scale)
    assert res_right.details["velocity_x_mps"] > 0, "Rightward motion must have positive velocity_x"

    # Reverse left: x = 200 -> 180 px
    res_left = tracker.update((0, 100), timestamp_seconds=t0 + 2 * dt, px_to_meters=scale)
    assert res_left.details["velocity_x_mps"] < 0, "Leftward motion must have negative velocity_x"
    # Acceleration during reversal should be negative (decelerating/reversing)
    assert res_left.details["acceleration_x_mps2"] < 0, "Leftward acceleration must be negative"


def test_trajectory_tracker_uniform_acceleration():
    """
    Analytical Test: Object with constant acceleration ax = 1.0 m/s^2.
    x(t) = 0.5 * a * t^2.
    v(t) = a * t.
    """
    tracker = TrajectoryTracker(pos_filter_alpha=1.0, vel_filter_beta=1.0)
    scale = 0.01
    a_target = 1.0
    dt = 0.1
    t0 = 3000.0

    for i in range(12):
        t_rel = i * dt
        x_m = 0.5 * a_target * (t_rel ** 2)
        cx = int(round(x_m / scale))
        res = tracker.update((cx, 200), timestamp_seconds=t0 + t_rel, px_to_meters=scale)

    assert res is not None
    # Acceleration should be close to 1.0 m/s^2
    assert pytest.approx(res.details["acceleration_x_mps2"], abs=0.2) == a_target


def test_trajectory_tracker_irregular_intervals_and_pauses():
    """
    Robustness: Handles near-zero dt (duplicate frames) and large pauses (>1.5s).
    """
    tracker = TrajectoryTracker()
    scale = 0.005
    t0 = 4000.0

    # Initial frame
    tracker.update((100, 100), timestamp_seconds=t0, px_to_meters=scale)

    # Frame 2: regular step
    res2 = tracker.update((110, 100), timestamp_seconds=t0 + 0.1, px_to_meters=scale)
    assert res2.velocity_mps > 0

    # Frame 3: near-zero interval (duplicate timestamp dt=0.0001s)
    res_dup = tracker.update((110, 100), timestamp_seconds=t0 + 0.1 + 0.0001, px_to_meters=scale)
    # Must not divide by near zero or blow up to infinity
    assert not math.isinf(res_dup.velocity_mps)
    assert not math.isnan(res_dup.velocity_mps)
    assert res_dup.acceleration_mps2 == 0.0

    # Frame 4: Large pause (dt = 3.0 seconds, camera paused or tab backgrounded)
    res_pause = tracker.update((200, 100), timestamp_seconds=t0 + 0.1 + 3.0, px_to_meters=scale)
    # Must re-anchor and reset velocity/acceleration to 0 rather than calculating 30 m/s
    assert res_pause.velocity_mps == 0.0
    assert res_pause.acceleration_mps2 == 0.0


def test_trajectory_tracker_calibration_validation():
    """
    Validation: Tests pixel-to-meter validation and out-of-bounds scale clamping.
    """
    tracker = TrajectoryTracker()

    # Valid calibration
    _, status, is_cal = tracker.validate_calibration(0.005)
    assert is_cal is True
    assert status == "calibrated"

    # Negative / zero scale
    scale, status, is_cal = tracker.validate_calibration(-0.01)
    assert is_cal is False
    assert status == "uncalibrated_default"
    assert scale == 0.005

    # Out of bounds scale (too large)
    scale, status, is_cal = tracker.validate_calibration(5.0)
    assert is_cal is False
    assert status == "uncalibrated_out_of_bounds"
    assert scale == 0.005


# ==============================================================================
# 2. Experiment Persistence and Deletion Lifecycle Tests
# ==============================================================================

def test_database_manager_experiment_persistence_and_deletion(tmp_path):
    """
    Persistence & Ownership:
    1. Saves experiment with strict user_id ownership and data_source.
    2. Queries experiments for owner and verifies persistence.
    3. Confirms user isolation (non-owner cannot see or delete).
    4. Deletes experiment as owner and confirms removal.
    """
    db_file = str(tmp_path / "test_persistence.json")
    manager = DatabaseManager(local_db_path=db_file)

    user_a = "user_student_alpha"
    user_b = "user_student_beta"

    exp_payload = {
        "id": "exp_persist_001",
        "user_id": user_a,
        "experiment_type": "pendulum",
        "data_source": "vision_tracking",
        "metrics": {"velocity_peak": 1.45, "is_calibrated": True},
        "timestamp": 1700000000,
    }

    # 1. Save experiment
    saved = manager.save_experiment(exp_payload, user_id=user_a)
    assert saved["id"] == "exp_persist_001"
    assert saved["user_id"] == user_a
    assert saved["data_source"] == "vision_tracking"

    # 2. Get experiments for user_a
    user_a_exps = manager.get_experiments(user_a)
    assert len(user_a_exps) == 1
    assert user_a_exps[0]["id"] == "exp_persist_001"
    assert user_a_exps[0]["data_source"] == "vision_tracking"

    # 3. Isolation: user_b cannot see user_a's experiment
    user_b_exps = manager.get_experiments(user_b)
    assert len(user_b_exps) == 0

    # 4. Unauthorized deletion: user_b attempts to delete user_a's experiment
    del_unauth = manager.delete_experiment("exp_persist_001", user_id=user_b)
    assert del_unauth is False
    # Ensure it is still intact
    assert manager.get_experiment_by_id("exp_persist_001") is not None

    # 5. Authorized deletion: user_a deletes their experiment
    del_auth = manager.delete_experiment("exp_persist_001", user_id=user_a)
    assert del_auth is True
    # Ensure it is now gone
    assert manager.get_experiment_by_id("exp_persist_001") is None
    assert len(manager.get_experiments(user_a)) == 0
