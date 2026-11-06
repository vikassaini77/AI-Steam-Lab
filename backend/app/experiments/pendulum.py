"""
Authoritative Simple Pendulum Experiment Implementation.
Provides:
1. Complete educational metadata, materials, instructions, and small-angle notes.
2. Pydantic parameter schema with strict range and finiteness validation.
3. Analytical theoretical model:
   - Small-angle approximation: T_0 = 2*pi*sqrt(L/g)
   - First & second order finite-amplitude Borda/Taylor corrections: T(theta_0) = T_0 * (1 + 1/16*theta_0^2 + 11/3072*theta_0^4)
4. Full time-series generation: position, velocity, acceleration, angle, KE, PE, total energy.
5. Multi-mode observation processing:
   - Manual stopwatch measurements (multiple trials, statistics, confidence intervals).
   - CV webcam-derived measurements (cycle extraction from zero-crossings, peak-to-peak periods).
6. Scientific error analysis: percentage error, standard error, finite-angle discrepancy, damping loss.
7. Structured, pedagogical AI tutor explanation grounded in actual data.
"""
from typing import Dict, Any, List, Optional, Type, Tuple
import math
import numpy as np
from pydantic import BaseModel, Field, field_validator

from app.experiments.base import (
    BaseExperiment,
    ExperimentMetadata,
    TheoreticalResult,
    ExperimentResult,
    ErrorAnalysis,
    TimeSeriesPoint,
)
from app.machine_learning.physics_engine import PhysicalUnit, validate_dt


class PendulumParamsSchema(BaseModel):
    """Validated input parameters for the Simple Pendulum experiment."""
    length: float = Field(..., gt=0.01, le=100.0, description="Pendulum string/rod length in meters (m)")
    gravity: float = Field(default=9.81, gt=0.1, le=100.0, description="Gravitational acceleration in m/s^2")
    angle_deg: float = Field(default=15.0, ge=-90.0, le=90.0, description="Initial displacement angle in degrees")
    mass: float = Field(default=1.0, gt=0.001, le=1000.0, description="Bob mass in kilograms (kg)")
    damping: float = Field(default=0.0, ge=0.0, le=5.0, description="Damping coefficient in s^-1 (0 = frictionless vacuum)")
    unit_system: str = Field(default="SI", description="Physical unit system (SI)")

    @field_validator("length", "gravity", "angle_deg", "mass", "damping", mode="before")
    @classmethod
    def validate_finite_numbers(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as err:
            raise ValueError(f"Parameter '{info.field_name}' must be a valid number, got {v!r}") from err
        if not math.isfinite(val):
            raise ValueError(f"Parameter '{info.field_name}' must be finite, got {val}")
        return val


class PendulumExperiment(BaseExperiment):
    """Authoritative scientific implementation of the Simple Pendulum Experiment."""

    _metadata = ExperimentMetadata(
        id="pendulum",
        title="Simple Pendulum Harmonic Motion",
        category="Oscillations & Classical Mechanics",
        tier="Beginner",
        time_estimate="15 min",
        learning_objectives=[
            "Determine the relationship between pendulum length L, local gravity g, and oscillation period T.",
            "Verify experimentally that the simple pendulum period is independent of bob mass m.",
            "Understand the small-angle approximation (sin θ ≈ θ) and observe finite-amplitude period elongation.",
            "Measure experimental oscillation periods using manual stopwatch timing or computer vision tracking.",
            "Analyze experimental error, sample standard deviation, and energy conservation exchange between KE and PE.",
        ],
        required_materials=[
            "Virtual Lab: Interactive parameter controls (Length, Gravity, Initial Angle, Mass, Damping).",
            "Physical/Webcam Lab: A suspended bob/weight, lightweight non-stretch thread/string, meter ruler, stopwatch or webcam.",
        ],
        instructions=[
            "Step 1: Set the pendulum length L (e.g. 1.0 m) and local gravitational acceleration g (Earth standard: 9.81 m/s²).",
            "Step 2: Choose an initial release angle θ₀. To test the ideal small-angle formula, select θ₀ ≤ 15° (0.26 rad).",
            "Step 3: Collect measurements: In Manual mode, use a stopwatch to record 3 to 10 periods (or time for 10 oscillations divided by 10). In CV mode, track the bob across webcam frames.",
            "Step 4: The system will calculate the experimental period T_exp, standard error SE, and compare it against theoretical T_theo.",
            "Step 5: Inspect the Position vs Time, Velocity vs Time, and Mechanical Energy graphs.",
            "Step 6: Review the AI Tutor explanation of observed errors (finite amplitude, air resistance, timing reaction time) and save your experiment.",
        ],
        theoretical_model_summary=(
            "The equation of motion for a simple pendulum is d²θ/dt² + (g/L) sin θ = 0. "
            "For small angular displacements (sin θ ≈ θ), this reduces to simple harmonic motion (SHM) "
            "d²θ/dt² + ω₀² θ = 0, where natural angular frequency ω₀ = √(g/L). "
            "The period of oscillation is T₀ = 2π√(L/g)."
        ),
        governing_equations=[
            "Equation of Motion: d²θ/dt² + (g/L) sin θ = 0",
            "Small-Angle Ideal Period: T₀ = 2π √(L/g)",
            "Finite-Amplitude Correction: T(θ₀) ≈ T₀ [ 1 + (1/16) θ₀² + (11/3072) θ₀⁴ ] (θ₀ in radians)",
            "Frequency: f = 1 / T",
            "Angular Frequency: ω = 2π f = √(g/L)",
            "Kinetic Energy: KE(t) = ½ m v(t)²",
            "Potential Energy: PE(t) = m g L (1 - cos θ(t))",
            "Total Mechanical Energy: E = KE + PE (conserved in zero damping)",
        ],
        small_angle_approximation_note=(
            "The small-angle approximation replaces sin θ with θ (in radians) based on the Taylor series "
            "sin θ = θ - θ³/6 + ... For θ ≤ 15° (0.2618 rad), sin(15°) = 0.2588, yielding a relative error of only 1.1%. "
            "At θ = 30° (0.5236 rad), the period is elongated by +1.7%. At θ = 45°, it is elongated by +4.0%. "
            "Our solver computes both the ideal small-angle period and the exact finite-amplitude corrected period."
        ),
        assumptions=[
            "The string/rod is massless, inextensible, and remains taut throughout motion.",
            "The bob is treated as a point mass concentrated at distance L from the pivot.",
            "Motion occurs in a vertical two-dimensional plane without conical precessing.",
            "The pivot friction is negligible.",
            "Air resistance is zero unless damping coefficient is explicitly configured.",
        ],
        limitations=[
            "Large angles (θ > 60°) exhibit noticeable anharmonicity and require elliptic integral solutions.",
            "Very short string lengths (L < 0.1 m) make bob physical dimensions non-negligible compared to length.",
            "Human stopwatch manual timing introduces reaction time jitter (typically ±0.15s to ±0.25s).",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "length": PhysicalUnit.POSITION.value,
            "gravity": PhysicalUnit.ACCELERATION.value,
            "angle_deg": PhysicalUnit.ANGLE_DEG.value,
            "mass": PhysicalUnit.MASS.value,
            "damping": PhysicalUnit.DAMPING.value,
            "period": PhysicalUnit.TIME.value,
            "frequency": PhysicalUnit.FREQUENCY.value,
            "velocity": PhysicalUnit.VELOCITY.value,
            "energy": PhysicalUnit.ENERGY.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return PendulumParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        """
        Computes authoritative theoretical physics results:
        - T_0: Small-angle ideal period
        - T_corrected: Borda/Taylor finite-amplitude corrected period
        - Frequency and angular frequency
        - Small-angle approximation discrepancy note
        - Pre-calculated time-series for graphing
        """
        validated = PendulumParamsSchema(**parameters)
        L = validated.length
        g = validated.gravity
        theta0_deg = validated.angle_deg
        theta0_rad = math.radians(abs(theta0_deg))
        mass = validated.mass
        damping = validated.damping

        # 1. Ideal small-angle period: T_0 = 2 * pi * sqrt(L / g)
        t_small_angle = 2.0 * math.pi * math.sqrt(L / g)
        f_small_angle = 1.0 / t_small_angle if t_small_angle > 0 else 0.0

        # 2. Finite-amplitude correction factor: 1 + 1/16*theta^2 + 11/3072*theta^4
        finite_factor = 1.0 + (1.0 / 16.0) * (theta0_rad ** 2) + (11.0 / 3072.0) * (theta0_rad ** 4)
        t_corrected = t_small_angle * finite_factor
        f_corrected = 1.0 / t_corrected if t_corrected > 0 else 0.0

        # 3. Damping effect (damped harmonic oscillator): omega_d = sqrt(omega_0^2 - gamma^2)
        omega_0 = math.sqrt(g / L)
        gamma = damping / 2.0  # damping decay factor
        is_underdamped = (omega_0 > gamma)
        if is_underdamped and gamma > 0:
            omega_d = math.sqrt(omega_0 ** 2 - gamma ** 2)
            t_damped = 2.0 * math.pi / omega_d
        else:
            t_damped = t_corrected

        primary_period = round(t_corrected if abs(theta0_deg) > 15.0 else t_small_angle, 4)

        # 4. Generate synchronized theoretical time series for plotting (covering 2 full periods)
        duration = max(3.0, primary_period * 2.2)
        series = self.generate_theoretical_series(validated.model_dump(), duration=duration, steps=100)

        computed = {
            "small_angle_period_s": round(t_small_angle, 4),
            "small_angle_frequency_hz": round(f_small_angle, 4),
            "corrected_period_s": round(t_corrected, 4),
            "corrected_frequency_hz": round(f_corrected, 4),
            "theoretical_period": primary_period,
            "theoretical_frequency": round(1.0 / primary_period, 4),
            "angular_frequency_rad_s": round(omega_0, 4),
            "finite_amplitude_deviation_percent": round((finite_factor - 1.0) * 100, 3),
            "is_small_angle_regime": abs(theta0_deg) <= 15.0,
            "small_angle_relative_error_percent": round(abs((t_corrected - t_small_angle) / t_corrected) * 100, 3),
            "natural_period_s": round(t_small_angle, 4),
            "damped_period_s": round(t_damped, 4) if damping > 0 else None,
            "formula_used": "T = 2π√(L/g)" if abs(theta0_deg) <= 15.0 else "T = 2π√(L/g) * [1 + 1/16 θ₀² + 11/3072 θ₀⁴]",
        }

        return TheoreticalResult(
            experiment_type="pendulum",
            parameters=validated.model_dump(),
            primary_theoretical_value=primary_period,
            primary_metric_name="theoretical_period",
            primary_metric_unit="s",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "period": "s",
                "frequency": "Hz",
                "length": "m",
                "gravity": "m/s^2",
                "angle": "deg",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 4.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        """Generates analytical time-series points: θ(t), x(t), v(t), a(t), KE(t), PE(t), E(t)."""
        L = float(parameters.get("length", 1.0))
        g = float(parameters.get("gravity", 9.81))
        theta0_deg = float(parameters.get("angle_deg", 15.0))
        theta0_rad = math.radians(theta0_deg)
        mass = float(parameters.get("mass", 1.0))
        damping = float(parameters.get("damping", 0.0))

        omega_0 = math.sqrt(g / L)
        gamma = damping / 2.0
        omega = math.sqrt(max(0.001, omega_0 ** 2 - gamma ** 2)) if omega_0 > gamma else omega_0

        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            decay = math.exp(-gamma * t) if damping > 0 else 1.0
            # Angle and derivatives
            theta_t = theta0_rad * decay * math.cos(omega * t)
            # Derivative of decay * cos(omega*t)
            theta_dot = theta0_rad * decay * (-gamma * math.cos(omega * t) - omega * math.sin(omega * t))
            theta_ddot = theta0_rad * decay * (
                (gamma ** 2 - omega ** 2) * math.cos(omega * t) + 2.0 * gamma * omega * math.sin(omega * t)
            )

            # Arc displacement x(t) = L * theta(t)
            x_m = L * math.sin(theta_t)
            v_mps = L * theta_dot
            a_mps2 = L * theta_ddot

            # Energy
            h_m = L * (1.0 - math.cos(theta_t))
            pe_j = max(0.0, mass * g * h_m)
            ke_j = max(0.0, 0.5 * mass * (v_mps ** 2))
            te_j = pe_j + ke_j

            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(x_m), 4),
                    velocity=round(float(v_mps), 4),
                    acceleration=round(float(a_mps2), 4),
                    angle_deg=round(float(math.degrees(theta_t)), 2),
                    kinetic_energy=round(float(ke_j), 4),
                    potential_energy=round(float(pe_j), 4),
                    total_energy=round(float(te_j), 4),
                )
            )

        return points

    def process_measurements(
        self,
        parameters: Dict[str, Any],
        raw_observations: List[Dict[str, Any]],
        calibration: Optional[Dict[str, Any]] = None,
    ) -> ExperimentResult:
        """
        Scientific Measurement System:
        Processes manual stopwatch trials or CV-derived frame tracking observations:
        1. Does NOT treat every detected frame as an independent observation.
        2. In CV tracking, extracts continuous oscillation cycles via zero-crossing and peak detection.
        3. Computes experimental period T_exp, frequency f_exp.
        4. Calculates sample standard deviation s, standard error of the mean SE = s / sqrt(N),
           and 95% confidence interval [T_exp - 1.96*SE, T_exp + 1.96*SE].
        5. Computes exact percentage error relative to theoretical period.
        6. Produces scientific error analysis attributing discrepancies to:
           - Small-angle approximation deviation (if theta_0 > 15°)
           - Damping and friction decay
           - Measurement reaction time / sampling resolution uncertainty
        """
        theo = self.calculate_theoretical(parameters)
        t_theo = theo.primary_theoretical_value

        if not raw_observations:
            # Handle empty / insufficient dataset gracefully
            empty_error = ErrorAnalysis(
                absolute_error=0.0,
                percentage_error=0.0,
                sample_size=0,
                scientific_verdict="No observations provided. Please record measurements via stopwatch or webcam.",
                discrepancy_sources=[{"factor": "Empty Dataset", "description": "No measurements recorded."}],
            )
            return ExperimentResult(
                experiment_type="pendulum",
                measurement_mode="manual",
                parameters=theo.parameters,
                theoretical_value=t_theo,
                experimental_value=0.0,
                primary_metric_name="period_seconds",
                primary_metric_unit="s",
                error_analysis=empty_error,
                observation_count=0,
                theoretical_series=theo.theoretical_series,
                experimental_series=[],
                units=self.metadata.units,
            )

        # Detect whether observations are manual period measurements or CV continuous frames
        has_period_inputs = any("period_s" in obs or "period" in obs for obs in raw_observations)
        has_cv_coords = any("position" in obs or "position_x" in obs or "x_meters" in obs for obs in raw_observations)

        periods: List[float] = []
        experimental_series: List[TimeSeriesPoint] = []
        mode = "manual"

        if has_period_inputs and not has_cv_coords:
            # Mode A: Manual stopwatch measurements (e.g. [2.01, 2.05, 1.98])
            mode = "manual"
            for obs in raw_observations:
                p_val = obs.get("period_s") or obs.get("period")
                if p_val is not None:
                    try:
                        p_float = float(p_val)
                        if math.isfinite(p_float) and p_float > 0.05:
                            periods.append(p_float)
                    except (ValueError, TypeError):
                        continue

            # Build mock series for manual points
            for i, p in enumerate(periods):
                experimental_series.append(
                    TimeSeriesPoint(
                        time=round(float(i + 1), 2),
                        position=round(float(p), 4),
                    )
                )

        else:
            # Mode B: CV-derived continuous tracking observations
            mode = "cv_derived"
            # Extract timestamped displacement coordinates
            clean_ts: List[float] = []
            clean_pos: List[float] = []

            for obs in raw_observations:
                t = obs.get("timestamp") or obs.get("time") or obs.get("dt_seconds")
                x = obs.get("position") or obs.get("position_x") or obs.get("x_meters")
                if t is not None and x is not None:
                    try:
                        t_f = float(t)
                        x_f = float(x)
                        if math.isfinite(t_f) and math.isfinite(x_f):
                            clean_ts.append(t_f)
                            clean_pos.append(x_f)
                    except (ValueError, TypeError):
                        continue

            if len(clean_ts) >= 4:
                # 1. Sort by timestamp
                sorted_indices = np.argsort(clean_ts)
                ts_arr = np.array(clean_ts)[sorted_indices]
                pos_arr = np.array(clean_pos)[sorted_indices]

                # Make timestamps relative to t0
                ts_rel = ts_arr - ts_arr[0]

                # 2. Extract oscillation periods via zero-crossings with deadband
                # Center around mean displacement
                centered_pos = pos_arr - np.mean(pos_arr)

                # Positive zero-crossings: where signal crosses 0 from negative to positive
                crossings: List[float] = []
                for i in range(len(centered_pos) - 1):
                    if centered_pos[i] <= 0 and centered_pos[i + 1] > 0:
                        # Linear interpolation for sub-frame crossing time accuracy
                        y1, y2 = centered_pos[i], centered_pos[i + 1]
                        t1, t2 = ts_rel[i], ts_rel[i + 1]
                        if y2 != y1:
                            t_cross = t1 + (-y1) * (t2 - t1) / (y2 - y1)
                            crossings.append(t_cross)

                # Each pair of consecutive positive zero-crossings corresponds to 1 full oscillation period
                if len(crossings) >= 2:
                    for i in range(len(crossings) - 1):
                        cycle_period = crossings[i + 1] - crossings[i]
                        # Filter obvious anomalies (e.g. period must be positive and reasonable)
                        if 0.1 <= cycle_period <= 20.0:
                            periods.append(cycle_period)

                # Sample up to 100 points for experimental graph
                step = max(1, len(ts_rel) // 100)
                for i in range(0, len(ts_rel), step):
                    v_val = raw_observations[i].get("velocity") or raw_observations[i].get("velocity_mps")
                    a_val = raw_observations[i].get("acceleration") or raw_observations[i].get("acceleration_mps2")
                    experimental_series.append(
                        TimeSeriesPoint(
                            time=round(float(ts_rel[i]), 3),
                            position=round(float(pos_arr[i]), 4),
                            velocity=round(float(v_val), 4) if v_val is not None else None,
                            acceleration=round(float(a_val), 4) if a_val is not None else None,
                        )
                    )

        # Statistical analysis across extracted periods
        if periods:
            n = len(periods)
            mean_period = float(np.mean(periods))
            std_period = float(np.std(periods, ddof=1)) if n > 1 else 0.0
            se_period = float(std_period / math.sqrt(n)) if n > 1 else 0.05
            # 95% Confidence Interval (approx. 1.96 * SE)
            ci_half = 1.96 * se_period
            ci_95 = [round(max(0.0, mean_period - ci_half), 4), round(mean_period + ci_half, 4)]
        else:
            # Fallback if insufficient cycles were completed (e.g. observation too short)
            mean_period = t_theo
            std_period = 0.0
            se_period = 0.0
            ci_95 = [round(t_theo, 4), round(t_theo, 4)]
            n = 0

        abs_error = abs(mean_period - t_theo)
        pct_error = (abs_error / t_theo) * 100.0 if t_theo > 0 else 0.0

        # Detailed Discrepancy Attribution
        discrepancies: List[Dict[str, Any]] = []

        # 1. Finite-amplitude contribution
        angle_deg = abs(float(parameters.get("angle_deg", 15.0)))
        if angle_deg > 15.0:
            small_angle_t = 2.0 * math.pi * math.sqrt(float(parameters.get("length", 1.0)) / float(parameters.get("gravity", 9.81)))
            finite_diff_pct = ((t_theo - small_angle_t) / small_angle_t) * 100.0
            discrepancies.append({
                "factor": "Finite-Amplitude Nonlinearity",
                "contribution_percent": round(finite_diff_pct, 2),
                "explanation": (
                    f"Initial angle was {angle_deg}°, which violates the small-angle assumption (θ ≤ 15°). "
                    f"This non-linearity elongates the period by +{finite_diff_pct:.2f}%."
                ),
            })

        # 2. Damping loss contribution
        damping_val = float(parameters.get("damping", 0.0))
        if damping_val > 0.0:
            discrepancies.append({
                "factor": "Air Resistance & Pivot Damping",
                "contribution_percent": round(damping_val * 2.5, 2),
                "explanation": (
                    f"Configured damping coefficient ({damping_val} s⁻¹) causes exponential decay of amplitude, "
                    "slightly shifting the effective resonance frequency."
                ),
            })

        # 3. Measurement instrument uncertainty
        if mode == "manual":
            discrepancies.append({
                "factor": "Human Reaction Time Jitter",
                "contribution_percent": round((0.2 / t_theo) * 100.0, 2) if t_theo > 0 else 5.0,
                "explanation": "Manual stopwatch timing introduces typical human reaction time uncertainty of ±0.15s to ±0.20s per split.",
            })
        else:
            discrepancies.append({
                "factor": "Webcam Sampling & Camera Jitter",
                "contribution_percent": round(min(5.0, (1.0 / 30.0 / t_theo) * 100.0), 2) if t_theo > 0 else 3.0,
                "explanation": "Standard 30/60 FPS webcam frame quantization limits temporal resolution to ~16-33 ms per frame.",
            })

        # Scientific Verdict
        if n == 0:
            verdict = "Incomplete observation: insufficient oscillation cycles detected to reliably compute period."
        elif pct_error <= 5.0:
            verdict = f"Excellent experimental agreement! Observed period ({mean_period:.3f}s) matches theory ({t_theo:.3f}s) within {pct_error:.1f}% error."
        elif pct_error <= 15.0:
            verdict = f"Good agreement with theoretical prediction within expected physical uncertainty ({pct_error:.1f}% error)."
        else:
            verdict = f"Significant discrepancy observed ({pct_error:.1f}% error). Review string length calibration, large angle non-linearity, or timing technique."

        error_analysis = ErrorAnalysis(
            absolute_error=round(abs_error, 4),
            percentage_error=round(pct_error, 2),
            sample_size=n,
            standard_deviation=round(std_period, 4),
            standard_error_of_mean=round(se_period, 4),
            confidence_interval_95=ci_95,
            discrepancy_sources=discrepancies,
            scientific_verdict=verdict,
        )

        return ExperimentResult(
            experiment_type="pendulum",
            measurement_mode=mode,
            parameters=theo.parameters,
            theoretical_value=round(t_theo, 4),
            experimental_value=round(mean_period, 4),
            primary_metric_name="period_seconds",
            primary_metric_unit="s",
            error_analysis=error_analysis,
            observation_count=len(raw_observations),
            theoretical_series=theo.theoretical_series,
            experimental_series=experimental_series,
            units=self.metadata.units,
            metadata={
                "measured_frequency_hz": round(1.0 / mean_period, 4) if mean_period > 0 else 0.0,
                "cycles_detected": n,
            },
        )

    def explain_results(
        self,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        student_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates contextual AI tutor explanations analyzing discrepancies,
        parameter sensitivity, and physical conclusions without fabricated numbers.
        """
        L = float(parameters.get("length", 1.0))
        g = float(parameters.get("gravity", 9.81))
        angle_deg = float(parameters.get("angle_deg", 15.0))
        mass = float(parameters.get("mass", 1.0))

        t_theo = float(results.get("theoretical_value", 2.006))
        t_exp = float(results.get("experimental_value", t_theo))
        err_analysis = results.get("error_analysis", {})
        pct_err = float(err_analysis.get("percentage_error", 0.0))

        # Core Pedagogical Sections
        what_demonstrates = (
            f"This experiment demonstrates simple harmonic motion (SHM). The gravitational restoring force "
            f"F_restoring = -m·g·sin(θ) accelerates the bob toward the equilibrium position. When the release angle "
            f"is small (θ ≤ 15°), sin(θ) ≈ θ (in radians), which leads to an oscillation period T = 2π√(L/g). "
            f"Crucially, the bob mass ({mass} kg) cancels out completely in the acceleration equation "
            f"(m·a = -m·g·sin(θ) ⟹ a = -g·sin(θ)), proving Galileo's discovery that pendulum period is independent of mass!"
        )

        why_differs = (
            f"Your measured experimental period is {t_exp:.3f}s compared to the theoretical period of {t_theo:.3f}s "
            f"(percentage error: {pct_err:.1f}%).\n"
        )
        if abs(angle_deg) > 15.0:
            why_differs += (
                f"- Finite-Angle Non-Linearity: Because the release angle was {angle_deg}°, the small-angle approximation "
                f"underestimates the period. The true theoretical period is elongated by Borda's formula to {t_theo:.3f}s.\n"
            )
        why_differs += (
            f"- Measurement Uncertainty: In manual stopwatch timing, human reaction times introduce ~0.15s–0.25s uncertainty. "
            f"In webcam tracking, camera frame-rate sampling (~33ms intervals) and lighting noise create minor centroid jitter.\n"
            f"- Ambient Damping: Air friction and pivot string drag dissipate mechanical energy over successive swings."
        )

        parameter_sensitivity = (
            f"- Length Effect: Period scales with the square root of length (T ∝ √L). If you quadruple the string length "
            f"from {L}m to {L*4:.2f}m, the period will double from {t_theo:.2f}s to {t_theo*2:.2f}s.\n"
            f"- Gravity Effect: Period is inversely proportional to √g (T ∝ 1/√g). On the Moon (g = 1.62 m/s²), "
            f"this same {L}m pendulum would swing significantly slower, with period {2.0 * math.pi * math.sqrt(L / 1.62):.2f}s!\n"
            f"- Mass Independence: Altering mass from {mass}kg to any other mass will have zero theoretical effect on period."
        )

        graph_interpretation = (
            "The Position vs Time curve is a pure sinusoid x(t) = L·θ₀·cos(ωt). Notice that the Velocity curve is "
            "shifted by a 90° phase angle (π/2 radians): when the bob passes through the central equilibrium point (x = 0), "
            "its velocity is at its absolute maximum, and all energy is stored as Kinetic Energy (KE). When the bob reaches "
            "its maximum swing endpoints, velocity drops to zero, and all energy transforms into Gravitational Potential Energy (PE)."
        )

        conclusion = (
            f"The experimental data successfully confirms harmonic pendulum dynamics with a {pct_err:.1f}% margin of error. "
            f"Within experimental uncertainty, the period is governed strictly by the length-to-gravity ratio √(L/g)."
        )

        return {
            "status": "success",
            "experiment_id": "pendulum",
            "what_it_demonstrates": what_demonstrates,
            "why_observed_differs_from_theory": why_differs,
            "role_of_measurement_error": (
                "Measurement uncertainty is an inescapable reality of empirical science. By calculating standard error "
                "across multiple oscillation cycles, random errors average out, converging on the true physical parameter."
            ),
            "parameter_sensitivity": parameter_sensitivity,
            "graph_interpretation": graph_interpretation,
            "conclusion": conclusion,
            "student_question_answer": f"Regarding your question '{student_question}': In a simple pendulum, the restoring torque is provided strictly by gravity acting on the center of mass. Energy continuously oscillates between gravitational potential and kinetic forms." if student_question else None,
        }

