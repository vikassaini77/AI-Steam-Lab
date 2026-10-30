"""
Test Suite for Problem 27: The physics engine needs numerical validation
File: backend/app/machine_learning/physics_engine.py

Validates:
1. Finite, strictly positive time intervals (dt > 0, rejection of 0, negative, NaN, Inf).
2. Coordinate input shape validation (mismatched dimensions, empty sequences).
3. Rejection of non-finite positions and velocities (NaN, Inf).
4. Physical unit definitions across all quantities.
5. Tolerance-based tests against known analytical solutions (kinematics, free-fall, pendulum, harmonic motion, collision).
6. Handling of frame-rate variation (variable dt) and measurement noise.
7. Explicit distinction between observed experimental motion and theoretical predictions.
"""
import math
import numpy as np
import pytest

from app.machine_learning.physics_engine import (
    PhysicsEngine,
    PhysicalUnit,
    validate_dt,
    validate_coordinates,
    validate_velocity_input,
)


@pytest.fixture
def engine():
    return PhysicsEngine()


# =============================================================================
# 1. Finite, Positive Time Intervals (validate_dt)
# =============================================================================

def test_validate_dt_rejects_zero_and_negative():
    """dt <= 0 must raise ValueError."""
    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(0.0)

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(-0.01)

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(-100.0)


def test_validate_dt_rejects_non_finite_values():
    """NaN, +Inf, -Inf must raise ValueError."""
    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(float("nan"))

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(float("inf"))

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        validate_dt(-float("inf"))


def test_validate_dt_rejects_non_numeric():
    """Non-numeric types must raise ValueError."""
    with pytest.raises(ValueError, match="dt must be a valid float"):
        validate_dt("invalid_string")  # type: ignore

    with pytest.raises(ValueError, match="dt must be a valid float"):
        validate_dt(None)  # type: ignore


def test_validate_dt_accepts_positive_finite():
    """Valid positive finite dt returns float."""
    assert validate_dt(0.016) == 0.016
    assert validate_dt(1.0) == 1.0
    assert validate_dt(1e-6) == 1e-6


# =============================================================================
# 2. Coordinate & Velocity Shape and Dimension Validation
# =============================================================================

def test_calculate_velocity_rejects_invalid_dt(engine):
    """calculate_velocity must enforce dt validation."""
    p1 = [0.0, 0.0]
    p2 = [1.0, 1.0]

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        engine.calculate_velocity(p1, p2, dt=0.0)

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        engine.calculate_velocity(p1, p2, dt=-0.05)

    with pytest.raises(ValueError, match="dt must be finite and positive"):
        engine.calculate_velocity(p1, p2, dt=float("nan"))


def test_calculate_velocity_rejects_mismatched_dimensions(engine):
    """Positions with different dimensions (e.g. 2D vs 3D) must raise ValueError."""
    p1_2d = [0.0, 0.0]
    p2_3d = [1.0, 1.0, 1.0]

    with pytest.raises(ValueError, match="Invalid position dimensions"):
        engine.calculate_velocity(p1_2d, p2_3d, dt=0.1)

    with pytest.raises(ValueError, match="Invalid position dimensions"):
        engine.calculate_velocity_vector(p1_2d, p2_3d, dt=0.1)


def test_calculate_velocity_rejects_empty_coordinates(engine):
    """Empty coordinate sequences must raise ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        engine.calculate_velocity([], [1.0, 2.0], dt=0.1)

    with pytest.raises(ValueError, match="cannot be empty"):
        engine.calculate_velocity([1.0, 2.0], [], dt=0.1)


def test_calculate_acceleration_rejects_mismatched_vector_dimensions(engine):
    """Acceleration between velocity vectors of different shapes must raise ValueError."""
    v1 = [1.0, 2.0]
    v2 = [1.0, 2.0, 3.0]

    with pytest.raises(ValueError, match="Invalid velocity dimensions"):
        engine.calculate_acceleration(v1, v2, dt=0.1)

    with pytest.raises(ValueError, match="Invalid velocity dimensions"):
        engine.calculate_acceleration_vector(v1, v2, dt=0.1)


# =============================================================================
# 3. Non-Finite Values Rejection (Positions & Velocities)
# =============================================================================

def test_calculate_velocity_rejects_nan_and_inf(engine):
    """Non-finite positions (NaN or Inf) must raise ValueError."""
    # NaN in p1
    with pytest.raises(ValueError, match="Positions must be finite"):
        engine.calculate_velocity([float("nan"), 0.0], [1.0, 2.0], dt=0.1)

    # +Inf in p2
    with pytest.raises(ValueError, match="Positions must be finite"):
        engine.calculate_velocity([0.0, 0.0], [float("inf"), 2.0], dt=0.1)

    # -Inf in p1
    with pytest.raises(ValueError, match="Positions must be finite"):
        engine.calculate_velocity_vector([-float("inf"), 0.0], [1.0, 2.0], dt=0.1)


def test_calculate_acceleration_rejects_non_finite_velocities(engine):
    """Non-finite velocities in acceleration calculations must raise ValueError."""
    # Scalar NaN
    with pytest.raises(ValueError, match="Velocities must be finite"):
        engine.calculate_acceleration(float("nan"), 10.0, dt=1.0)

    # Scalar Inf
    with pytest.raises(ValueError, match="Velocities must be finite"):
        engine.calculate_acceleration(5.0, float("inf"), dt=1.0)

    # Vector NaN
    with pytest.raises(ValueError, match="Velocities must be finite"):
        engine.calculate_acceleration_vector([1.0, float("nan")], [2.0, 3.0], dt=1.0)


def test_harmonic_motion_rejects_invalid_parameters(engine):
    """Harmonic motion must reject non-finite and negative physical parameters."""
    # Non-finite t
    with pytest.raises(ValueError, match="Harmonic parameter 't' must be a finite real number"):
        engine.harmonic_motion(float("nan"), A=1.0, omega=2.0, phi=0.0)

    # Negative amplitude
    with pytest.raises(ValueError, match="Amplitude A must be non-negative"):
        engine.harmonic_motion(1.0, A=-5.0, omega=2.0, phi=0.0)

    # Negative angular frequency
    with pytest.raises(ValueError, match="Angular frequency omega must be non-negative"):
        engine.harmonic_motion(1.0, A=1.0, omega=-2.0, phi=0.0)


def test_solvers_reject_non_finite_and_unphysical_inputs():
    """Theoretical solvers must reject unphysical values."""
    # Free-fall height <= 0 or NaN
    with pytest.raises(ValueError, match="Height must be strictly positive"):
        PhysicsEngine.solve_free_fall(height=-10.0)
    with pytest.raises(ValueError, match="Free-fall parameter 'height' must be a finite real number"):
        PhysicsEngine.solve_free_fall(height=float("nan"))

    # Pendulum length <= 0 or damping < 0
    with pytest.raises(ValueError, match="Pendulum length must be strictly positive"):
        PhysicsEngine.solve_pendulum(length=-1.0, angle_deg=10.0)
    with pytest.raises(ValueError, match="Damping coefficient must be non-negative"):
        PhysicsEngine.solve_pendulum(length=1.0, angle_deg=10.0, damping=-0.5)

    # Collision invalid masses or unsupported type
    with pytest.raises(ValueError, match="Masses must be strictly positive"):
        PhysicsEngine.solve_collision(mass_a=-1.0, mass_b=2.0, vel_a=1.0, vel_b=0.0)
    with pytest.raises(ValueError, match="Unsupported collision type"):
        PhysicsEngine.solve_collision(mass_a=1.0, mass_b=2.0, vel_a=1.0, vel_b=0.0, collision_type="Explosive")


# =============================================================================
# 4. Physical Unit Definitions
# =============================================================================

def test_physical_units_constants():
    """Verifies standard SI physical units are formally defined."""
    assert PhysicalUnit.POSITION.value == "m"
    assert PhysicalUnit.TIME.value == "s"
    assert PhysicalUnit.VELOCITY.value == "m/s"
    assert PhysicalUnit.ACCELERATION.value == "m/s^2"
    assert PhysicalUnit.MASS.value == "kg"
    assert PhysicalUnit.ENERGY.value == "J"
    assert PhysicalUnit.MOMENTUM.value == "kg*m/s"
    assert PhysicalUnit.FREQUENCY.value == "Hz"


def test_solvers_return_units_metadata():
    """All solvers must attach explicit unit dictionaries to their results."""
    ff = PhysicsEngine.solve_free_fall(height=20.0, mass=2.0, gravity=9.8)
    assert ff["units"]["height"] == "m"
    assert ff["units"]["gravity"] == "m/s^2"
    assert ff["units"]["final_velocity"] == "m/s"
    assert ff["units"]["time_of_flight"] == "s"

    pen = PhysicsEngine.solve_pendulum(length=2.0, angle_deg=15.0)
    assert pen["units"]["theoretical_period"] == "s"
    assert pen["units"]["theoretical_frequency"] == "Hz"
    assert pen["units"]["length"] == "m"

    col = PhysicsEngine.solve_collision(mass_a=1.0, mass_b=1.0, vel_a=2.0, vel_b=0.0)
    assert col["units"]["momentum"] == "kg*m/s"
    assert col["units"]["kinetic_energy"] == "J"


# =============================================================================
# 5. Tolerance-Based Tests Against Analytical Solutions
# =============================================================================

def test_constant_velocity_analytical_solution(engine):
    """
    Test 1D and 3D motion under known constant velocity v = 15.0 m/s.
    """
    v_true = 15.0  # m/s
    dt = 0.4  # s
    x1 = 10.0
    x2 = x1 + v_true * dt  # 16.0

    speed = engine.calculate_velocity([x1], [x2], dt)
    assert math.isclose(speed, v_true, rel_tol=1e-9)

    # 3D vector motion: displacement along [3, 4, 12] scaled by factor
    # Magnitude of [3, 4, 12] is 13.
    dir_vec = np.array([3.0, 4.0, 12.0]) / 13.0
    p1 = np.array([10.0, 20.0, 30.0])
    p2 = p1 + dir_vec * (v_true * dt)

    v_calc_scalar = engine.calculate_velocity(p1, p2, dt)
    assert math.isclose(v_calc_scalar, v_true, rel_tol=1e-9)

    v_calc_vector = engine.calculate_velocity_vector(p1, p2, dt)
    expected_vec = dir_vec * v_true
    np.testing.assert_allclose(v_calc_vector, expected_vec, rtol=1e-9)


def test_constant_acceleration_analytical_solution(engine):
    """
    Test motion under known constant acceleration a = 9.81 m/s^2.
    """
    a_true = 9.81
    dt = 0.5
    v1 = 4.0
    v2 = v1 + a_true * dt

    a_calc = engine.calculate_acceleration(v1, v2, dt)
    assert math.isclose(a_calc, a_true, rel_tol=1e-9)

    # Vector acceleration
    v1_vec = np.array([2.0, 5.0, 0.0])
    acc_vec = np.array([1.5, -9.81, 0.0])
    v2_vec = v1_vec + acc_vec * dt

    a_calc_vec = engine.calculate_acceleration_vector(v1_vec, v2_vec, dt)
    np.testing.assert_allclose(a_calc_vec, acc_vec, rtol=1e-9)


def test_free_fall_analytical_kinematics():
    """
    Verifies free fall analytical formulas:
    t_f = sqrt(2h / g), v_f = sqrt(2gh).
    """
    h = 45.0
    g = 9.8
    expected_tof = math.sqrt(2 * h / g)  # ~3.0304576
    expected_vf = math.sqrt(2 * g * h)   # ~29.69848

    res = PhysicsEngine.solve_free_fall(height=h, gravity=g)
    assert math.isclose(res["time_of_flight"], expected_tof, abs_tol=1e-3)
    assert math.isclose(res["final_velocity"], expected_vf, abs_tol=1e-3)


def test_harmonic_motion_analytical_finite_difference(engine):
    """
    Verifies x(t) = A cos(omega * t) matches analytical velocity
    v(t) = -A * omega * sin(omega * t) via central finite differences.
    """
    A = 2.5
    omega = 3.0
    phi = 0.5
    t = 1.2
    dt = 1e-5  # small dt for central differences

    x_plus = engine.harmonic_motion(t + dt, A, omega, phi)
    x_minus = engine.harmonic_motion(t - dt, A, omega, phi)

    numerical_v = (x_plus - x_minus) / (2 * dt)
    analytical_v = -A * omega * math.sin(omega * t + phi)

    assert math.isclose(numerical_v, analytical_v, rel_tol=1e-6)


def test_elastic_collision_conservation_laws():
    """
    Verifies analytical conservation of both linear momentum and kinetic energy in 1D.
    """
    ma, mb = 3.0, 2.0
    va, vb = 4.0, -1.0

    res = PhysicsEngine.solve_collision(mass_a=ma, mass_b=mb, vel_a=va, vel_b=vb, collision_type="Elastic")

    p_init = ma * va + mb * vb  # 12 - 2 = 10.0
    ke_init = 0.5 * ma * va**2 + 0.5 * mb * vb**2  # 24 + 1 = 25.0

    assert math.isclose(res["initial"]["momentum"], p_init, abs_tol=1e-2)
    assert math.isclose(res["final"]["momentum"], p_init, abs_tol=1e-2)
    assert math.isclose(res["initial"]["kinetic_energy"], ke_init, abs_tol=1e-2)
    assert math.isclose(res["final"]["kinetic_energy"], ke_init, abs_tol=1e-2)
    assert res["energy_loss_joules"] == 0.0


# =============================================================================
# 6. Measurement Noise & Frame-Rate Variation (Variable dt)
# =============================================================================

def test_analyze_observed_trajectory_with_frame_rate_jitter(engine):
    """
    Tests handling of variable frame rates (non-constant dt_i) and noise filtering.
    """
    np.random.seed(42)
    # Simulate variable timestamps around 30 FPS (mean dt ~ 0.0333s)
    n_points = 50
    dt_intervals = np.random.uniform(0.028, 0.038, size=n_points - 1)
    timestamps = np.concatenate(([0.0], np.cumsum(dt_intervals)))

    # Constant velocity motion x(t) = v * t + noise
    v_actual = 2.0  # m/s
    clean_positions = v_actual * timestamps
    noise = np.random.normal(0.0, 0.005, size=n_points)  # 5mm noise
    observed_positions = clean_positions + noise

    result = engine.analyze_observed_trajectory(
        timestamps=timestamps,
        positions=observed_positions,
        filter_noise=True,
        smoothing_window=5,
    )

    assert result["nature"] == "observed_experimental_motion"
    assert result["point_count"] == n_points
    # Frame rate jitter statistics
    stats = result["sampling_statistics"]
    assert 25.0 < stats["mean_fps"] < 35.0
    assert stats["std_dt_seconds"] > 0
    assert stats["frame_rate_jitter_percent"] > 0

    # Mean smoothed velocity should be close to actual velocity 2.0 m/s
    assert math.isclose(result["metrics"]["mean_speed"], v_actual, rel_tol=0.10)


def test_analyze_observed_trajectory_rejects_non_monotonic_timestamps(engine):
    """Timestamps with zero or negative intervals must be rejected."""
    # Decreasing timestamp
    with pytest.raises(ValueError, match="strictly monotonically increasing"):
        engine.analyze_observed_trajectory(
            timestamps=[0.0, 0.1, 0.05, 0.2],
            positions=[0.0, 1.0, 2.0, 3.0],
        )

    # Identical timestamp (dt == 0)
    with pytest.raises(ValueError, match="strictly monotonically increasing"):
        engine.analyze_observed_trajectory(
            timestamps=[0.0, 0.1, 0.1, 0.2],
            positions=[0.0, 1.0, 2.0, 3.0],
        )


# =============================================================================
# 7. Distinguish Observed Motion from Theoretical Physics Predictions
# =============================================================================

def test_distinguish_observed_and_theoretical_signatures(engine):
    """Verifies that observed results and theoretical results carry distinct nature tags."""
    theoretical = engine.solve_free_fall(height=10.0)
    assert theoretical["nature"] == "theoretical_physics_prediction"

    observed = engine.analyze_observed_trajectory(
        timestamps=[0.0, 0.1, 0.2, 0.3],
        positions=[10.0, 9.95, 9.80, 9.55],
    )
    assert observed["nature"] == "observed_experimental_motion"


def test_compare_observed_vs_theoretical_consistent_motion(engine):
    """
    Compares observations closely tracking theoretical predictions.
    Should yield low RMSE, high R^2, and is_consistent_with_theory is True.
    """
    g = 9.81
    h = 20.0
    timestamps = np.linspace(0.0, 1.5, 30)
    # Theoretical position: y(t) = h - 0.5 * g * t^2
    theoretical_y = h - 0.5 * g * timestamps**2

    # Observed motion with small 2cm sensor noise
    np.random.seed(123)
    observed_y = theoretical_y + np.random.normal(0.0, 0.02, size=len(timestamps))

    comp = engine.compare_observed_vs_theoretical(
        observed_timestamps=timestamps,
        observed_positions=observed_y,
        theoretical_positions=theoretical_y,
        tolerance_meters=0.10,
    )

    assert comp["comparison"] == "observed_vs_theoretical"
    assert comp["rmse_meters"] < 0.05
    assert comp["mae_meters"] < 0.05
    assert comp["r_squared"] > 0.99
    assert comp["is_consistent_with_theory"] is True


def test_compare_observed_vs_theoretical_inconsistent_motion(engine):
    """
    Compares unphysical or deviating motion (e.g. anti-gravity).
    Should yield high RMSE and is_consistent_with_theory is False.
    """
    timestamps = np.linspace(0.0, 1.0, 20)
    theoretical_y = 10.0 - 0.5 * 9.81 * timestamps**2
    # Object miraculously moves UPWARD instead of falling
    unphysical_observed_y = 10.0 + 5.0 * timestamps

    comp = engine.compare_observed_vs_theoretical(
        observed_timestamps=timestamps,
        observed_positions=unphysical_observed_y,
        theoretical_positions=theoretical_y,
        tolerance_meters=0.10,
    )

    assert comp["is_consistent_with_theory"] is False
    assert comp["rmse_meters"] > 1.0

