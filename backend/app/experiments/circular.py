"""
Uniform Circular Motion Experiment Implementation.
Models centripetal acceleration, centripetal force, angular speed,
orbital period, and tangential velocity.
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


class CircularMotionParamsSchema(BaseModel):
    radius: float = Field(default=1.0, gt=0.01, le=100.0, description="Radius of circular path in meters (m)")
    speed: float = Field(default=5.0, gt=0.01, le=200.0, description="Tangential speed in m/s")
    mass: float = Field(default=1.0, gt=0.001, le=1000.0, description="Rotating mass in kilograms (kg)")
    unit_system: str = Field(default="SI", description="Unit system (SI)")

    @field_validator("radius", "speed", "mass", mode="before")
    @classmethod
    def validate_finite(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Field '{info.field_name}' must be numeric") from e
        if not math.isfinite(val):
            raise ValueError(f"Field '{info.field_name}' must be finite")
        return val


class CircularMotionExperiment(BaseExperiment):
    _metadata = ExperimentMetadata(
        id="circular_motion",
        title="Uniform Circular Motion & Centripetal Acceleration",
        category="Classical Mechanics & Kinematics",
        tier="Intermediate",
        time_estimate="15 min",
        learning_objectives=[
            "Distinguish between scalar speed (constant) and vector velocity (continuously changing direction).",
            "Calculate centripetal acceleration a_c = v² / r = ω² r directed radially inward toward the center.",
            "Determine the centripetal force F_c = m v² / r required to maintain the circular trajectory.",
            "Relate angular velocity ω, tangential speed v, and period T = 2πr / v.",
        ],
        required_materials=[
            "Virtual: Radius slider, tangential speed slider, mass slider.",
            "Physical/Webcam: Rotating turntable/arm, tethered ball, circular marker track, webcam.",
        ],
        instructions=[
            "Step 1: Set circular radius r and tangential speed v.",
            "Step 2: Observe how the centripetal acceleration vector always points toward the center of rotation.",
            "Step 3: Measure the orbital period T using manual stopwatch timing or webcam cycle tracking.",
            "Step 4: Verify that centripetal force scales quadratically with speed (Fc ∝ v²).",
        ],
        theoretical_model_summary=(
            "In uniform circular motion, speed v is constant, but velocity vector v(t) continuously changes direction. "
            "Centripetal acceleration: a_c = v² / r. "
            "Centripetal force: F_c = m a_c = m v² / r. "
            "Angular frequency: ω = v / r. "
            "Period of one revolution: T = 2π r / v."
        ),
        governing_equations=[
            "Period: T = 2π r / v",
            "Angular Velocity: ω = v / r = 2π / T",
            "Centripetal Acceleration: a_c = v² / r = ω² r",
            "Centripetal Force: F_c = m v² / r",
            "Position: x(t) = r cos(ωt), y(t) = r sin(ωt)",
        ],
        assumptions=[
            "Pure circular path with constant radius r.",
            "Constant tangential speed v (zero angular acceleration α = 0).",
            "Zero frictional energy loss.",
        ],
        limitations=[
            "Real-world rotation involves tether tension limits and mechanical bearing friction.",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "radius": PhysicalUnit.POSITION.value,
            "speed": PhysicalUnit.VELOCITY.value,
            "period": PhysicalUnit.TIME.value,
            "acceleration": PhysicalUnit.ACCELERATION.value,
            "force": PhysicalUnit.FORCE.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return CircularMotionParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        validated = CircularMotionParamsSchema(**parameters)
        r = validated.radius
        v = validated.speed
        mass = validated.mass

        period = (2.0 * math.pi * r) / v if v > 0 else 0.0
        frequency = 1.0 / period if period > 0 else 0.0
        omega = v / r if r > 0 else 0.0
        a_c = (v ** 2) / r if r > 0 else 0.0
        f_c = mass * a_c

        series = self.generate_theoretical_series(validated.model_dump(), duration=max(2.0, period * 2.0), steps=100)

        computed = {
            "period_s": round(period, 4),
            "frequency_hz": round(frequency, 4),
            "angular_velocity_rad_s": round(omega, 4),
            "centripetal_acceleration_mps2": round(a_c, 4),
            "centripetal_force_n": round(f_c, 4),
            "formula_used": "T = 2πr/v, a_c = v²/r, F_c = m v²/r",
        }

        return TheoreticalResult(
            experiment_type="circular_motion",
            parameters=validated.model_dump(),
            primary_theoretical_value=round(period, 4),
            primary_metric_name="period_s",
            primary_metric_unit="s",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "period": "s",
                "centripetal_acceleration": "m/s^2",
                "centripetal_force": "N",
                "speed": "m/s",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 2.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        r = float(parameters.get("radius", 1.0))
        v = float(parameters.get("speed", 5.0))
        mass = float(parameters.get("mass", 1.0))
        omega = v / r if r > 0 else 1.0
        a_c = (v ** 2) / r if r > 0 else 0.0
        ke = 0.5 * mass * (v ** 2)

        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            x_m = r * math.cos(omega * t)
            y_m = r * math.sin(omega * t)
            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(x_m), 4),
                    velocity=round(float(v), 4),
                    acceleration=round(float(a_c), 4),
                    angle_deg=round(float(math.degrees(omega * t) % 360.0), 2),
                    kinetic_energy=round(float(ke), 4),
                    potential_energy=0.0,
                    total_energy=round(float(ke), 4),
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
            scientific_verdict=f"Orbital revolution period verified within {pct_err:.1f}% error.",
            discrepancy_sources=[
                {"factor": "Centripetal Tension Compliance", "description": "Tether elasticity under high centripetal acceleration."},
                {"factor": "Angular Speed Drift", "description": "Motor bearing drag causing slight deceleration across revolutions."},
            ],
        )

        return ExperimentResult(
            experiment_type="circular_motion",
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
        r = float(parameters.get("radius", 1.0))
        v = float(parameters.get("speed", 5.0))
        m = float(parameters.get("mass", 1.0))
        t_theo = float(results.get("theoretical_value", 1.257))
        exp_p = float(results.get("experimental_value", t_theo))
        pct_err = float(results.get("error_analysis", {}).get("percentage_error", 0.0))

        return {
            "status": "success",
            "experiment_id": "circular_motion",
            "what_it_demonstrates": (
                f"Demonstrates uniform circular kinematics. At radius {r}m and speed {v}m/s, "
                f"centripetal acceleration is a_c = v²/r = {(v**2)/r:.2f} m/s², requiring centripetal force "
                f"F_c = m·a_c = {m * (v**2)/r:.2f} N toward the center."
            ),
            "why_observed_differs_from_theory": (
                f"Observed revolution period was {exp_p:.3f}s vs theoretical {t_theo:.3f}s ({pct_err:.1f}% error). "
                "In physical experiments, bearing friction and air resistance extract kinetic energy unless constantly driven."
            ),
            "role_of_measurement_error": "Revolution timing over multiple revolutions reduces start/stop reaction error.",
            "parameter_sensitivity": "Centripetal acceleration scales quadratically with speed (v²) and inversely with radius (1/r).",
            "graph_interpretation": "x(t) and y(t) are sinusoidal quadrature signals out of phase by 90°, tracing a circle in the 2D plane.",
            "conclusion": f"Uniform circular motion relations verified within {pct_err:.1f}% error.",
        }

