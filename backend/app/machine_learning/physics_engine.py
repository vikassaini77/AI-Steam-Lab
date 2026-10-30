"""
authoritative Physics Engine for NeuroLab AI
Provides:
1. Strict numerical input validation for time intervals (dt > 0, finite), positions, and velocities.
2. Vector and scalar kinematics calculations.
3. Explicit physical units definitions.
4. Handling of measurement noise and frame-rate variation (variable dt).
5. Clear separation between observed experimental motion and theoretical physics predictions.
6. Analytical physics solvers (Free-fall, Pendulum, Collision, Harmonic Motion).
"""
import math
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np


class PhysicalUnit(str, Enum):
    """Standard SI units for physical quantities."""
    POSITION = "m"                # meters
    TIME = "s"                    # seconds
    VELOCITY = "m/s"              # meters per second (speed or vector velocity)
    ACCELERATION = "m/s^2"        # meters per second squared
    MASS = "kg"                   # kilograms
    FORCE = "N"                   # Newtons (kg * m / s^2)
    ENERGY = "J"                  # Joules (kg * m^2 / s^2)
    MOMENTUM = "kg*m/s"           # Kilogram-meters per second
    FREQUENCY = "Hz"              # Hertz (1 / s)
    ANGLE = "rad"                 # radians
    ANGLE_DEG = "deg"             # degrees
    DAMPING = "s^-1"              # damping ratio / coefficient


def validate_dt(dt: float) -> float:
    """
    Validates that a time interval dt is finite and strictly positive (> 0).

    Raises:
        ValueError: If dt <= 0 or not finite (NaN, +Inf, -Inf).
    """
    try:
        val = float(dt)
    except (TypeError, ValueError) as err:
        raise ValueError(f"dt must be a valid float, got {dt!r}") from err

    if not math.isfinite(val) or val <= 0:
        raise ValueError(f"dt must be finite and positive (> 0), got {val}")
    return val


def validate_coordinates(p: Any, name: str = "Position") -> np.ndarray:
    """
    Validates coordinate array or sequence.
    Must be a non-empty, finite float numpy array.

    Raises:
        ValueError: If array is empty, malformed, or contains NaN/Inf.
    """
    try:
        arr = np.asarray(p, dtype=float)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} cannot be converted to a float array") from err

    if arr.size == 0:
        raise ValueError(f"Invalid position dimensions: {name} cannot be empty")

    if not np.isfinite(arr).all():
        raise ValueError(f"Positions must be finite: {name} contains non-finite values (NaN/Inf)")
    return arr


def validate_velocity_input(v: Any, name: str = "Velocity") -> Union[float, np.ndarray]:
    """
    Validates scalar or vector velocity inputs.
    Must be finite.

    Raises:
        ValueError: If input is empty or non-finite.
    """
    if isinstance(v, (int, float, np.floating, np.integer)):
        val = float(v)
        if not math.isfinite(val):
            raise ValueError(f"Velocities must be finite: {name} is {val}")
        return val

    try:
        arr = np.asarray(v, dtype=float)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{name} cannot be converted to float") from err

    if arr.size == 0:
        raise ValueError(f"Invalid velocity dimensions: {name} cannot be empty")

    if not np.isfinite(arr).all():
        raise ValueError(f"Velocities must be finite: {name} contains non-finite values (NaN/Inf)")
    return arr


class PhysicsEngine:
    """
    High-precision physics engine supporting theoretical modeling,
    numerical differentiation, and observational kinematics.
    """
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def calculate_velocity(self, p1: Any, p2: Any, dt: float) -> float:
        """
        Calculates scalar speed (magnitude of displacement divided by dt).
        
        Units:
            p1, p2: meters (m)
            dt: seconds (s)
            Return: meters per second (m/s)

        Raises:
            ValueError: If dt <= 0, non-finite, coordinates empty, shapes mismatch,
                        or positions contain NaN/Inf.
        """
        dt_val = validate_dt(dt)
        a = validate_coordinates(p1, "p1")
        b = validate_coordinates(p2, "p2")

        if a.shape != b.shape:
            raise ValueError(
                f"Invalid position dimensions: p1 shape {a.shape} != p2 shape {b.shape}"
            )

        return float(np.linalg.norm(b - a) / dt_val)

    def calculate_velocity_vector(self, p1: Any, p2: Any, dt: float) -> np.ndarray:
        """
        Calculates signed velocity vector (displacement divided by dt).
        
        Units:
            p1, p2: meters (m)
            dt: seconds (s)
            Return: vector in meters per second (m/s)
        """
        dt_val = validate_dt(dt)
        a = validate_coordinates(p1, "p1")
        b = validate_coordinates(p2, "p2")

        if a.shape != b.shape:
            raise ValueError(
                f"Invalid position dimensions: p1 shape {a.shape} != p2 shape {b.shape}"
            )

        return (b - a) / dt_val

    def calculate_acceleration(
        self, v1: Union[float, Sequence[float], np.ndarray],
        v2: Union[float, Sequence[float], np.ndarray],
        dt: float
    ) -> float:
        """
        Calculates acceleration from two velocities and time interval dt.
        Supports scalar velocities (returns signed scalar acceleration) or
        vector velocities (returns Euclidean magnitude of acceleration vector).

        Units:
            v1, v2: meters per second (m/s)
            dt: seconds (s)
            Return: meters per second squared (m/s^2)
        """
        dt_val = validate_dt(dt)
        val_v1 = validate_velocity_input(v1, "v1")
        val_v2 = validate_velocity_input(v2, "v2")

        # Scalar case
        if isinstance(val_v1, float) and isinstance(val_v2, float):
            return float((val_v2 - val_v1) / dt_val)

        # Vector case
        arr_v1 = np.asarray(val_v1, dtype=float)
        arr_v2 = np.asarray(val_v2, dtype=float)
        if arr_v1.shape != arr_v2.shape:
            raise ValueError(
                f"Invalid velocity dimensions: v1 shape {arr_v1.shape} != v2 shape {arr_v2.shape}"
            )
        return float(np.linalg.norm(arr_v2 - arr_v1) / dt_val)

    def calculate_acceleration_vector(self, v1: Any, v2: Any, dt: float) -> np.ndarray:
        """
        Calculates signed acceleration vector: (v2 - v1) / dt.

        Units:
            v1, v2: meters per second (m/s)
            dt: seconds (s)
            Return: vector in meters per second squared (m/s^2)
        """
        dt_val = validate_dt(dt)
        arr_v1 = np.asarray(validate_velocity_input(v1, "v1"), dtype=float)
        arr_v2 = np.asarray(validate_velocity_input(v2, "v2"), dtype=float)

        if arr_v1.shape != arr_v2.shape:
            raise ValueError(
                f"Invalid velocity dimensions: v1 shape {arr_v1.shape} != v2 shape {arr_v2.shape}"
            )
        return (arr_v2 - arr_v1) / dt_val

    def harmonic_motion(self, t: float, A: float, omega: float, phi: float) -> float:
        """
        Theoretical simple harmonic motion position: x(t) = A * cos(omega * t + phi).

        Units:
            t: seconds (s)
            A: amplitude (m)
            omega: angular frequency (rad/s)
            phi: initial phase (rad)
            Return: position (m)
        """
        for name, val in [("t", t), ("A", A), ("omega", omega), ("phi", phi)]:
            if not isinstance(val, (int, float, np.floating, np.integer)) or not math.isfinite(val):
                raise ValueError(f"Harmonic parameter '{name}' must be a finite real number, got {val!r}")

        if A < 0:
            raise ValueError(f"Amplitude A must be non-negative, got {A}")
        if omega < 0:
            raise ValueError(f"Angular frequency omega must be non-negative, got {omega}")

        return float(A * np.cos(omega * t + phi))

    # =========================================================================
    # Observational Trajectory Kinematics (Measurement Noise & Frame Jitter)
    # =========================================================================

    def analyze_observed_trajectory(
        self,
        timestamps: Sequence[float],
        positions: Sequence[Any],
        filter_noise: bool = True,
        smoothing_window: int = 3,
    ) -> Dict[str, Any]:
        """
        Analyzes observed experimental motion from discrete tracking detections.
        Handles:
        1. Variable frame-rates and frame jitter (arbitrary dt_i).
        2. Measurement noise through moving-average smoothing.
        3. Strict monotonically increasing timestamps check.

        Args:
            timestamps: List/array of timestamps in seconds (strictly increasing).
            positions: List/array of 1D, 2D, or 3D positions in meters.
            filter_noise: If True, applies moving average smoothing to coordinates.
            smoothing_window: Odd integer window size for smoothing (default 3).

        Returns:
            Dictionary containing observed motion metrics, sampling statistics, and units.
        """
        t_arr = np.asarray(timestamps, dtype=float)
        if t_arr.ndim != 1 or t_arr.size < 2:
            raise ValueError("timestamps must be a 1D sequence with at least 2 points")
        if not np.isfinite(t_arr).all():
            raise ValueError("All timestamps must be finite real numbers")

        dt_series = np.diff(t_arr)
        if (dt_series <= 0).any():
            raise ValueError("timestamps must be strictly monotonically increasing (dt > 0)")

        pos_arr = np.asarray(positions, dtype=float)
        if pos_arr.shape[0] != t_arr.shape[0]:
            raise ValueError(
                f"Length mismatch: {t_arr.shape[0]} timestamps vs {pos_arr.shape[0]} positions"
            )
        if not np.isfinite(pos_arr).all():
            raise ValueError("Positions must be finite (cannot contain NaN or Inf)")

        # Smooth coordinates if requested to mitigate CV pixel jitter
        proc_pos = pos_arr.copy()
        if filter_noise and pos_arr.shape[0] >= smoothing_window and smoothing_window >= 3:
            w = smoothing_window if smoothing_window % 2 == 1 else smoothing_window + 1
            half = w // 2
            # Moving average smoothing with edge replication
            pad_width = [(half, half)] + [(0, 0)] * (pos_arr.ndim - 1)
            padded = np.pad(pos_arr, pad_width, mode="edge")
            smoothed = np.empty_like(pos_arr)
            for i in range(pos_arr.shape[0]):
                smoothed[i] = np.mean(padded[i : i + w], axis=0)
            proc_pos = smoothed

        # Instantaneous speeds and velocity vectors
        displacements = np.diff(proc_pos, axis=0)
        dt_col = dt_series if displacements.ndim == 1 else dt_series[:, np.newaxis]
        vel_vectors = displacements / dt_col

        if displacements.ndim == 1:
            speeds = np.abs(vel_vectors)
        else:
            speeds = np.linalg.norm(vel_vectors, axis=1)

        # Instantaneous accelerations (requires at least 3 points)
        accelerations = np.array([])
        if len(speeds) >= 2:
            dt_acc = 0.5 * (dt_series[:-1] + dt_series[1:])
            d_speeds = np.diff(speeds)
            accelerations = d_speeds / dt_acc

        mean_dt = float(np.mean(dt_series))
        std_dt = float(np.std(dt_series))
        mean_fps = float(1.0 / mean_dt) if mean_dt > 0 else 0.0

        return {
            "nature": "observed_experimental_motion",
            "point_count": int(len(t_arr)),
            "sampling_statistics": {
                "mean_dt_seconds": round(mean_dt, 6),
                "std_dt_seconds": round(std_dt, 6),
                "frame_rate_jitter_percent": round(float((std_dt / mean_dt) * 100), 2) if mean_dt > 0 else 0.0,
                "mean_fps": round(mean_fps, 2),
            },
            "metrics": {
                "mean_speed": round(float(np.mean(speeds)), 4) if len(speeds) > 0 else 0.0,
                "max_speed": round(float(np.max(speeds)), 4) if len(speeds) > 0 else 0.0,
                "mean_acceleration": round(float(np.mean(accelerations)), 4) if len(accelerations) > 0 else 0.0,
                "max_acceleration": round(float(np.max(accelerations)), 4) if len(accelerations) > 0 else 0.0,
            },
            "instantaneous_speeds": [round(float(s), 4) for s in speeds],
            "instantaneous_accelerations": [round(float(a), 4) for a in accelerations],
            "units": {
                "positions": PhysicalUnit.POSITION.value,
                "timestamps": PhysicalUnit.TIME.value,
                "speeds": PhysicalUnit.VELOCITY.value,
                "accelerations": PhysicalUnit.ACCELERATION.value,
            },
        }

    # =========================================================================
    # Distinguish Observed Motion from Theoretical Predictions
    # =========================================================================

    def compare_observed_vs_theoretical(
        self,
        observed_timestamps: Sequence[float],
        observed_positions: Sequence[float],
        theoretical_positions: Sequence[float],
        tolerance_meters: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Quantitatively compares observed experimental motion against theoretical model predictions.
        Computes RMSE, MAE, R^2 goodness-of-fit, and physical consistency verdict.

        Units:
            positions: meters (m)
            timestamps: seconds (s)
        """
        obs_t = np.asarray(observed_timestamps, dtype=float)
        obs_y = np.asarray(observed_positions, dtype=float)
        theo_y = np.asarray(theoretical_positions, dtype=float)

        if obs_y.shape != theo_y.shape or obs_y.size == 0:
            raise ValueError(
                f"Observed positions shape {obs_y.shape} must match theoretical positions shape {theo_y.shape}"
            )
        if not np.isfinite(obs_y).all() or not np.isfinite(theo_y).all():
            raise ValueError("All observed and theoretical positions must be finite")

        residuals = obs_y - theo_y
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals**2)))
        max_err = float(np.max(np.abs(residuals)))

        # Coefficient of determination R^2
        ss_res = float(np.sum(residuals**2))
        ss_tot = float(np.sum((obs_y - np.mean(obs_y))**2))
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 1.0

        is_consistent = bool(rmse <= tolerance_meters)

        return {
            "comparison": "observed_vs_theoretical",
            "rmse_meters": round(rmse, 4),
            "mae_meters": round(mae, 4),
            "max_error_meters": round(max_err, 4),
            "r_squared": round(r_squared, 4),
            "tolerance_meters": tolerance_meters,
            "is_consistent_with_theory": is_consistent,
            "units": {
                "rmse": PhysicalUnit.POSITION.value,
                "mae": PhysicalUnit.POSITION.value,
                "residuals": PhysicalUnit.POSITION.value,
            },
            "residuals": [round(float(r), 4) for r in residuals],
        }

    # =========================================================================
    # Analytical Theoretical Solvers
    # =========================================================================

    @staticmethod
    def solve_free_fall(height: float, mass: float = 1.0, gravity: float = 9.81) -> Dict[str, Any]:
        """
        Solves free-fall kinematic equations with full parameter validation.
        
        Units:
            height: meters (m)
            mass: kilograms (kg)
            gravity: meters per second squared (m/s^2)
        """
        for name, val in [("height", height), ("mass", mass), ("gravity", gravity)]:
            if not isinstance(val, (int, float, np.floating, np.integer)) or not math.isfinite(val):
                raise ValueError(f"Free-fall parameter '{name}' must be a finite real number, got {val!r}")

        if height <= 0:
            raise ValueError(f"Height must be strictly positive (> 0), got {height}")
        if mass <= 0:
            raise ValueError(f"Mass must be strictly positive (> 0), got {mass}")
        if gravity <= 0:
            raise ValueError(f"Gravity must be strictly positive (> 0), got {gravity}")

        tof = np.sqrt(2 * height / gravity)
        v_final = np.sqrt(2 * gravity * height)
        time_steps = np.linspace(0, tof, 20)
        series = [
            {
                "time": round(float(t), 3),
                "position": round(float(max(0.0, height - 0.5 * gravity * t**2)), 3),
                "velocity": round(float(gravity * t), 3),
            }
            for t in time_steps
        ]
        return {
            "nature": "theoretical_physics_prediction",
            "parameters": {"height": height, "mass": mass, "gravity": gravity},
            "time_of_flight": round(float(tof), 4),
            "final_velocity": round(float(v_final), 4),
            "series": series,
            "units": {
                "height": PhysicalUnit.POSITION.value,
                "mass": PhysicalUnit.MASS.value,
                "gravity": PhysicalUnit.ACCELERATION.value,
                "time_of_flight": PhysicalUnit.TIME.value,
                "final_velocity": PhysicalUnit.VELOCITY.value,
            },
        }

    @staticmethod
    def solve_pendulum(
        length: float, angle_deg: float, mass: float = 1.0, gravity: float = 9.81, damping: float = 0.0
    ) -> Dict[str, Any]:
        """
        Solves theoretical pendulum period and frequency.

        Units:
            length: meters (m)
            angle_deg: degrees (deg)
            mass: kilograms (kg)
            gravity: meters per second squared (m/s^2)
            damping: seconds^-1 (s^-1)
        """
        for name, val in [("length", length), ("angle_deg", angle_deg), ("mass", mass), ("gravity", gravity), ("damping", damping)]:
            if not isinstance(val, (int, float, np.floating, np.integer)) or not math.isfinite(val):
                raise ValueError(f"Pendulum parameter '{name}' must be a finite real number, got {val!r}")

        if length <= 0:
            raise ValueError(f"Pendulum length must be strictly positive (> 0), got {length}")
        if mass <= 0:
            raise ValueError(f"Mass must be strictly positive (> 0), got {mass}")
        if gravity <= 0:
            raise ValueError(f"Gravity must be strictly positive (> 0), got {gravity}")
        if damping < 0:
            raise ValueError(f"Damping coefficient must be non-negative (>= 0), got {damping}")

        period = 2 * np.pi * np.sqrt(length / gravity)
        frequency = 1.0 / period
        return {
            "nature": "theoretical_physics_prediction",
            "theoretical_period": round(float(period), 4),
            "theoretical_frequency": round(float(frequency), 4),
            "parameters": {
                "length": length,
                "angle_deg": angle_deg,
                "mass": mass,
                "gravity": gravity,
                "damping": damping,
            },
            "units": {
                "theoretical_period": PhysicalUnit.TIME.value,
                "theoretical_frequency": PhysicalUnit.FREQUENCY.value,
                "length": PhysicalUnit.POSITION.value,
                "angle_deg": PhysicalUnit.ANGLE_DEG.value,
                "gravity": PhysicalUnit.ACCELERATION.value,
            },
        }

    @staticmethod
    def solve_collision(
        mass_a: float, mass_b: float, vel_a: float, vel_b: float, collision_type: str = "Elastic"
    ) -> Dict[str, Any]:
        """
        Solves 1D collision momentum and energy conservation.

        Units:
            mass_a, mass_b: kilograms (kg)
            vel_a, vel_b: meters per second (m/s)
        """
        for name, val in [("mass_a", mass_a), ("mass_b", mass_b), ("vel_a", vel_a), ("vel_b", vel_b)]:
            if not isinstance(val, (int, float, np.floating, np.integer)) or not math.isfinite(val):
                raise ValueError(f"Collision parameter '{name}' must be a finite real number, got {val!r}")

        if mass_a <= 0 or mass_b <= 0:
            raise ValueError(f"Masses must be strictly positive (> 0), got mass_a={mass_a}, mass_b={mass_b}")

        c_type = collision_type.strip().lower()
        if c_type not in ("elastic", "inelastic"):
            raise ValueError(f"Unsupported collision type '{collision_type}'. Must be 'Elastic' or 'Inelastic'.")

        p_init = mass_a * vel_a + mass_b * vel_b
        ke_init = 0.5 * mass_a * vel_a**2 + 0.5 * mass_b * vel_b**2

        if c_type == "elastic":
            v_a_final = ((mass_a - mass_b) * vel_a + 2 * mass_b * vel_b) / (mass_a + mass_b)
            v_b_final = ((mass_b - mass_a) * vel_b + 2 * mass_a * vel_a) / (mass_a + mass_b)
        else:  # Inelastic
            v_common = p_init / (mass_a + mass_b)
            v_a_final = v_common
            v_b_final = v_common

        ke_final = 0.5 * mass_a * v_a_final**2 + 0.5 * mass_b * v_b_final**2
        energy_loss = max(0.0, ke_init - ke_final)

        return {
            "nature": "theoretical_physics_prediction",
            "initial": {"momentum": round(float(p_init), 2), "kinetic_energy": round(float(ke_init), 2)},
            "final": {
                "momentum": round(float(p_init), 2),
                "vel_a": round(float(v_a_final), 2),
                "vel_b": round(float(v_b_final), 2),
                "kinetic_energy": round(float(ke_final), 2),
            },
            "energy_loss_joules": round(float(energy_loss), 4),
            "units": {
                "momentum": PhysicalUnit.MOMENTUM.value,
                "kinetic_energy": PhysicalUnit.ENERGY.value,
                "energy_loss_joules": PhysicalUnit.ENERGY.value,
                "velocity": PhysicalUnit.VELOCITY.value,
            },
        }
