"""
Free Fall Experiment Implementation.
Solves uniform gravitational acceleration, time of flight, final impact velocity,
and mechanical energy conservation (PE -> KE).
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


class FreeFallParamsSchema(BaseModel):
    height: float = Field(default=10.0, gt=0.01, le=1000.0, description="Drop height in meters (m)")
    gravity: float = Field(default=9.81, gt=0.1, le=100.0, description="Gravitational acceleration in m/s^2")
    mass: float = Field(default=1.0, gt=0.001, le=1000.0, description="Object mass in kilograms (kg)")
    unit_system: str = Field(default="SI", description="Unit system (SI)")

    @field_validator("height", "gravity", "mass", mode="before")
    @classmethod
    def validate_finite(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Field '{info.field_name}' must be numeric") from e
        if not math.isfinite(val):
            raise ValueError(f"Field '{info.field_name}' must be finite")
        return val


class FreeFallExperiment(BaseExperiment):
    _metadata = ExperimentMetadata(
        id="free_fall",
        title="Gravitational Free Fall Kinematics",
        category="Classical Mechanics & Kinematics",
        tier="Beginner",
        time_estimate="10 min",
        learning_objectives=[
            "Verify Galileo's law: in a vacuum, all bodies fall with identical gravitational acceleration g regardless of mass.",
            "Calculate drop duration t = √(2h/g) and terminal impact speed v = √(2gh).",
            "Demonstrate total mechanical energy conservation: potential energy transforms into kinetic energy.",
            "Compare observed drop times against theoretical values.",
        ],
        required_materials=[
            "Virtual: Height slider, gravity presets (Earth, Moon, Mars, Jupiter), object mass.",
            "Physical/Webcam: Drop apparatus, ball/mass, ruler or height marker, photogate or webcam.",
        ],
        instructions=[
            "Step 1: Set the drop height h (e.g. 5.0 m) and local gravity g.",
            "Step 2: Drop the object and record the time to impact using a timer or webcam tracking.",
            "Step 3: Compare experimental time of flight and impact velocity against theoretical predictions.",
        ],
        theoretical_model_summary=(
            "Under uniform gravity without drag, vertical acceleration is constant: a(t) = -g. "
            "Position: y(t) = h - ½ g t². "
            "Velocity: v(t) = -g t. "
            "Time to impact: t_impact = √(2h / g). "
            "Impact velocity: v_impact = √(2g h). "
            "Energy: PE = m g y, KE = ½ m v², E = PE + KE = m g h (constant)."
        ),
        governing_equations=[
            "Position: y(t) = h - ½ g t²",
            "Velocity: v(t) = g t",
            "Time to Impact: t = √(2h / g)",
            "Impact Speed: v = √(2gh)",
            "Conservation of Energy: m g h = ½ m v²",
        ],
        assumptions=[
            "Negligible aerodynamic drag (vacuum condition).",
            "Initial velocity v0 = 0 m/s.",
            "Uniform local gravitational acceleration.",
        ],
        limitations=[
            "Real air drops reach terminal velocity if drag force balances weight (F_drag = mg).",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "height": PhysicalUnit.POSITION.value,
            "gravity": PhysicalUnit.ACCELERATION.value,
            "time_of_flight": PhysicalUnit.TIME.value,
            "velocity": PhysicalUnit.VELOCITY.value,
            "energy": PhysicalUnit.ENERGY.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return FreeFallParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        validated = FreeFallParamsSchema(**parameters)
        h = validated.height
        g = validated.gravity
        mass = validated.mass

        t_flight = math.sqrt(2.0 * h / g) if g > 0 else 0.0
        v_impact = math.sqrt(2.0 * g * h) if g > 0 else 0.0
        initial_pe = mass * g * h

        series = self.generate_theoretical_series(validated.model_dump(), duration=t_flight, steps=100)

        computed = {
            "time_of_flight_s": round(t_flight, 4),
            "final_velocity_mps": round(v_impact, 4),
            "initial_potential_energy_j": round(initial_pe, 4),
            "final_kinetic_energy_j": round(initial_pe, 4),
            "formula_used": "t = √(2h/g), v = √(2gh)",
        }

        return TheoreticalResult(
            experiment_type="free_fall",
            parameters=validated.model_dump(),
            primary_theoretical_value=round(t_flight, 4),
            primary_metric_name="time_of_flight_s",
            primary_metric_unit="s",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "time_of_flight": "s",
                "velocity": "m/s",
                "height": "m",
                "energy": "J",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 2.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        h = float(parameters.get("height", 10.0))
        g = float(parameters.get("gravity", 9.81))
        mass = float(parameters.get("mass", 1.0))

        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            y_m = max(0.0, h - 0.5 * g * (t ** 2))
            v_mps = g * t
            pe_j = max(0.0, mass * g * y_m)
            ke_j = max(0.0, 0.5 * mass * (v_mps ** 2))

            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(y_m), 4),
                    velocity=round(float(v_mps), 4),
                    acceleration=round(float(g), 4),
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

        times: List[float] = []
        for obs in raw_observations:
            t_val = obs.get("time_of_flight_s") or obs.get("time") or obs.get("period_s")
            if t_val is not None:
                try:
                    t_f = float(t_val)
                    if math.isfinite(t_f) and t_f > 0:
                        times.append(t_f)
                except (ValueError, TypeError):
                    continue

        if times:
            exp_time = float(np.mean(times))
            n = len(times)
            s_time = float(np.std(times, ddof=1)) if n > 1 else 0.0
            se_time = float(s_time / math.sqrt(n)) if n > 1 else 0.05
        else:
            exp_time = t_theo
            n = 0
            s_time = 0.0
            se_time = 0.0

        abs_err = abs(exp_time - t_theo)
        pct_err = (abs_err / t_theo) * 100.0 if t_theo > 0 else 0.0

        error_analysis = ErrorAnalysis(
            absolute_error=round(abs_err, 4),
            percentage_error=round(pct_err, 2),
            sample_size=n,
            standard_deviation=round(s_time, 4),
            standard_error_of_mean=round(se_time, 4),
            confidence_interval_95=[round(max(0.0, exp_time - 1.96 * se_time), 4), round(exp_time + 1.96 * se_time, 4)],
            scientific_verdict=f"Free fall drop time verified within {pct_err:.1f}% error.",
            discrepancy_sources=[
                {"factor": "Air Drag Resistance", "description": "Drag opposes gravity, slightly prolonging fall duration."},
                {"factor": "Release Timing Latency", "description": "Trigger/stopwatch reaction latency on drop initiation."},
            ],
        )

        return ExperimentResult(
            experiment_type="free_fall",
            measurement_mode="manual",
            parameters=theo.parameters,
            theoretical_value=t_theo,
            experimental_value=round(exp_time, 4),
            primary_metric_name="time_of_flight_s",
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
        h = float(parameters.get("height", 10.0))
        g = float(parameters.get("gravity", 9.81))
        t_theo = float(results.get("theoretical_value", 1.428))
        exp_time = float(results.get("experimental_value", t_theo))
        pct_err = float(results.get("error_analysis", {}).get("percentage_error", 0.0))

        return {
            "status": "success",
            "experiment_id": "free_fall",
            "what_it_demonstrates": (
                f"Demonstrates uniform gravitational acceleration. Dropped from {h}m, "
                f"the theoretical time of flight is √(2·{h}/{g}) = {t_theo:.3f}s with impact velocity {math.sqrt(2*g*h):.2f} m/s."
            ),
            "why_observed_differs_from_theory": (
                f"Experimental drop time was {exp_time:.3f}s ({pct_err:.1f}% error). "
                "Air resistance provides an upward drag force proportional to v², reducing net downward acceleration."
            ),
            "role_of_measurement_error": "Human stopwatch release reaction time (~0.1-0.2s) is the dominant experimental error in manual free-fall tests.",
            "parameter_sensitivity": "Drop time scales with √h. Quadrupling the height doubles the time of flight.",
            "graph_interpretation": "Position vs Time is a downward parabola y = h - ½gt². Velocity vs Time is a linear line v = gt.",
            "conclusion": f"Free-fall mechanics confirm Newtonian gravitational acceleration within {pct_err:.1f}% error.",
        }

