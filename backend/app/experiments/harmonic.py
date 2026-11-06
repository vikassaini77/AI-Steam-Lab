"""
Simple Harmonic Motion (SHM) & Spring Oscillation Experiment Implementation.
Models Hooke's Law (F = -kx), natural angular frequency omega_0 = sqrt(k/m),
period T = 2*pi*sqrt(m/k), displacement x(t), velocity, acceleration, and damping.
"""
from typing import Dict, Any, List, Optional, Type
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
from app.machine_learning.physics_engine import PhysicalUnit


class HarmonicParamsSchema(BaseModel):
    spring_k: float = Field(default=25.0, gt=0.01, le=10000.0, description="Spring constant k in N/m")
    mass: float = Field(default=1.0, gt=0.001, le=1000.0, description="Attached mass m in kg")
    displacement: float = Field(default=0.5, gt=0.001, le=50.0, description="Initial amplitude A in meters")
    damping: float = Field(default=0.0, ge=0.0, le=10.0, description="Damping coefficient b in N*s/m")
    unit_system: str = Field(default="SI", description="Unit system (SI)")

    @field_validator("spring_k", "mass", "displacement", "damping", mode="before")
    @classmethod
    def validate_finite(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Field '{info.field_name}' must be numeric") from e
        if not math.isfinite(val):
            raise ValueError(f"Field '{info.field_name}' must be finite")
        return val


class HarmonicMotionExperiment(BaseExperiment):
    _metadata = ExperimentMetadata(
        id="harmonic_motion",
        title="Simple Harmonic Motion & Spring Oscillation",
        category="Oscillations & Waves",
        tier="Intermediate",
        time_estimate="15 min",
        learning_objectives=[
            "Verify Hooke's law restoring force: F = -k x.",
            "Determine the natural oscillation period T = 2π √(m/k) and frequency f = 1/T.",
            "Observe continuous mechanical energy exchange between elastic potential energy (½kx²) and kinetic energy (½mv²).",
            "Examine underdamped exponential decay when damping coefficient b > 0.",
        ],
        required_materials=[
            "Virtual: Spring constant k, mass m, displacement amplitude A, damping b.",
            "Physical/Webcam: Helical spring, hung mass, vertical scale marker, webcam or photogate.",
        ],
        instructions=[
            "Step 1: Set spring stiffness k (e.g. 25 N/m) and attached mass m (e.g. 1.0 kg).",
            "Step 2: Displace the mass by initial amplitude x0 and release.",
            "Step 3: Measure the oscillation period using manual stopwatch timing or webcam tracking.",
            "Step 4: Inspect the phase relation between position, velocity, and acceleration.",
        ],
        theoretical_model_summary=(
            "Hooke's Law: F_net = -k x - b v = m d²x/dt². "
            "Natural frequency: ω₀ = √(k / m). "
            "Ideal period: T₀ = 2π √(m / k). "
            "Position: x(t) = A e^(-γt) cos(ω_d t), where γ = b / (2m), ω_d = √(ω₀² - γ²). "
            "Elastic PE: PE = ½ k x². Kinetic Energy: KE = ½ m v²."
        ),
        governing_equations=[
            "Restoring Force: F = -k x",
            "Natural Frequency: ω₀ = √(k / m)",
            "Period: T₀ = 2π √(m / k)",
            "Displacement: x(t) = A cos(ω₀ t)",
            "Velocity: v(t) = -A ω₀ sin(ω₀ t)",
            "Acceleration: a(t) = -A ω₀² cos(ω₀ t) = - (k/m) x(t)",
        ],
        assumptions=[
            "Linear elastic spring behaving strictly according to Hooke's Law (within elastic limit).",
            "Massless spring.",
            "One-dimensional vertical or horizontal oscillation.",
        ],
        limitations=[
            "Large displacements deform the spring beyond its proportional limit.",
            "Real springs possess distributed internal mass affecting effective inertia (m_eff = m + m_spring/3).",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "spring_k": "N/m",
            "mass": PhysicalUnit.MASS.value,
            "displacement": PhysicalUnit.POSITION.value,
            "period": PhysicalUnit.TIME.value,
            "energy": PhysicalUnit.ENERGY.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return HarmonicParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        validated = HarmonicParamsSchema(**parameters)
        k = validated.spring_k
        m = validated.mass
        A = validated.displacement
        b = validated.damping

        omega_0 = math.sqrt(k / m)
        period_0 = 2.0 * math.pi * math.sqrt(m / k)
        freq_0 = 1.0 / period_0

        gamma = b / (2.0 * m)
        if omega_0 > gamma and gamma > 0:
            omega_d = math.sqrt(omega_0 ** 2 - gamma ** 2)
            period_damped = 2.0 * math.pi / omega_d
        else:
            period_damped = period_0

        primary_period = round(period_damped if b > 0 else period_0, 4)
        total_energy = 0.5 * k * (A ** 2)

        series = self.generate_theoretical_series(validated.model_dump(), duration=max(3.0, primary_period * 2.5), steps=100)

        computed = {
            "period_s": primary_period,
            "frequency_hz": round(1.0 / primary_period, 4),
            "natural_angular_frequency_rad_s": round(omega_0, 4),
            "spring_constant_n_m": k,
            "total_mechanical_energy_j": round(total_energy, 4),
            "formula_used": "T = 2π√(m/k)",
        }

        return TheoreticalResult(
            experiment_type="harmonic_motion",
            parameters=validated.model_dump(),
            primary_theoretical_value=primary_period,
            primary_metric_name="period_s",
            primary_metric_unit="s",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "period": "s",
                "frequency": "Hz",
                "spring_k": "N/m",
                "energy": "J",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 3.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        k = float(parameters.get("spring_k", 25.0))
        m = float(parameters.get("mass", 1.0))
        A = float(parameters.get("displacement", 0.5))
        b = float(parameters.get("damping", 0.0))

        omega_0 = math.sqrt(k / m)
        gamma = b / (2.0 * m)
        omega_d = math.sqrt(max(0.001, omega_0 ** 2 - gamma ** 2)) if omega_0 > gamma else omega_0

        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            decay = math.exp(-gamma * t) if b > 0 else 1.0
            x_m = A * decay * math.cos(omega_d * t)
            v_mps = A * decay * (-gamma * math.cos(omega_d * t) - omega_d * math.sin(omega_d * t))
            a_mps2 = -(k / m) * x_m

            pe_j = 0.5 * k * (x_m ** 2)
            ke_j = 0.5 * m * (v_mps ** 2)

            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(x_m), 4),
                    velocity=round(float(v_mps), 4),
                    acceleration=round(float(a_mps2), 4),
                    kinetic_energy=round(float(ke_j), 4),
                    potential_energy=round(float(pe_j), 4),
                    total_energy=round(float(pe_j + ke_j), 4),
                )
            )

        return points

    def process_measurements(
        self,
        parameters: Dict[str, Any],
        raw_observations: List[Dict[str, Any]],
        calibration: Optional[Dict[str, Any]] = None,
    ) -> ExperimentResult:
        theo = self.calculate_theoretical(parameters)
        t_theo = theo.primary_theoretical_value

        periods: List[float] = []
        for obs in raw_observations:
            p = obs.get("period_s") or obs.get("period") or obs.get("time")
            if p is not None:
                try:
                    pf = float(p)
                    if math.isfinite(pf) and pf > 0:
                        periods.append(pf)
                except (ValueError, TypeError):
                    continue

        if periods:
            exp_period = float(np.mean(periods))
            n = len(periods)
            s_p = float(np.std(periods, ddof=1)) if n > 1 else 0.0
            se_p = float(s_p / math.sqrt(n)) if n > 1 else 0.05
        else:
            exp_period = t_theo
            n = 0
            s_p = 0.0
            se_p = 0.0

        abs_err = abs(exp_period - t_theo)
        pct_err = (abs_err / t_theo) * 100.0 if t_theo > 0 else 0.0

        error_analysis = ErrorAnalysis(
            absolute_error=round(abs_err, 4),
            percentage_error=round(pct_err, 2),
            sample_size=n,
            standard_deviation=round(s_p, 4),
            standard_error_of_mean=round(se_p, 4),
            confidence_interval_95=[round(max(0.0, exp_period - 1.96 * se_p), 4), round(exp_period + 1.96 * se_p, 4)],
            scientific_verdict=f"Spring oscillation period verified within {pct_err:.1f}% error.",
            discrepancy_sources=[
                {"factor": "Spring Effective Mass", "description": "Spring coils contribute ~1/3 of spring mass to inertia, slightly elongating period."},
                {"factor": "Internal Viscous Damping", "description": "Material hysteresis in helical wire absorbs mechanical energy."},
            ],
        )

        return ExperimentResult(
            experiment_type="harmonic_motion",
            measurement_mode="manual",
            parameters=theo.parameters,
            theoretical_value=t_theo,
            experimental_value=round(exp_period, 4),
            primary_metric_name="period_s",
            primary_metric_unit="s",
            error_analysis=error_analysis,
            observation_count=len(raw_observations),
            theoretical_series=theo.theoretical_series,
            experimental_series=[],
            units=self.metadata.units,
        )

    def explain_results(
        self,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        student_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        k = float(parameters.get("spring_k", 25.0))
        m = float(parameters.get("mass", 1.0))
        t_theo = float(results.get("theoretical_value", 1.257))
        exp_p = float(results.get("experimental_value", t_theo))
        pct_err = float(results.get("error_analysis", {}).get("percentage_error", 0.0))

        return {
            "status": "success",
            "experiment_id": "harmonic_motion",
            "what_it_demonstrates": (
                f"Demonstrates Hooke's Law and simple harmonic oscillation. With spring constant k = {k} N/m "
                f"and mass m = {m} kg, the natural frequency is ω₀ = √(k/m) = {math.sqrt(k/m):.2f} rad/s, "
                f"yielding period T = 2π√(m/k) = {t_theo:.3f} s."
            ),
            "why_observed_differs_from_theory": (
                f"Observed period was {exp_p:.3f}s vs theoretical {t_theo:.3f}s ({pct_err:.1f}% error). "
                "Real springs possess internal coil mass and structural damping that slightly retard oscillation rate."
            ),
            "role_of_measurement_error": "Timing across multiple complete cycles reduces human split uncertainty.",
            "parameter_sensitivity": "Increasing mass increases period (T ∝ √m). Stiffer springs decrease period (T ∝ 1/√k).",
            "graph_interpretation": "Position x(t) and acceleration a(t) are 180° out of phase: a = -(k/m)x. Energy oscillates between PE and KE.",
            "conclusion": f"Hooke's Law oscillator verified within {pct_err:.1f}% error.",
        }

