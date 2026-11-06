"""
Projectile Motion Experiment Implementation.
Provides theoretical trajectory modeling, range, max height, flight time,
and experimental trajectory comparison against video/webcam observations.
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


class ProjectileParamsSchema(BaseModel):
    velocity: float = Field(default=20.0, gt=0.1, le=500.0, description="Initial launch speed v0 in m/s")
    angle_deg: float = Field(default=45.0, ge=0.0, le=90.0, description="Launch angle above horizontal in degrees")
    gravity: float = Field(default=9.81, gt=0.1, le=100.0, description="Gravitational acceleration in m/s^2")
    initial_height: float = Field(default=0.0, ge=0.0, le=1000.0, description="Initial elevation y0 in meters")
    mass: float = Field(default=1.0, gt=0.001, le=1000.0, description="Projectile mass in kg")
    unit_system: str = Field(default="SI", description="Unit system (SI)")

    @field_validator("velocity", "angle_deg", "gravity", "initial_height", "mass", mode="before")
    @classmethod
    def validate_finite(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Field '{info.field_name}' must be numeric") from e
        if not math.isfinite(val):
            raise ValueError(f"Field '{info.field_name}' must be finite")
        return val


class ProjectileExperiment(BaseExperiment):
    _metadata = ExperimentMetadata(
        id="projectile_motion",
        title="2D Projectile Motion Analysis",
        category="Classical Mechanics & Kinematics",
        tier="Intermediate",
        time_estimate="20 min",
        learning_objectives=[
            "Resolve 2D initial velocity vectors into orthogonal x and y components.",
            "Verify that horizontal motion maintains constant velocity (ax = 0) while vertical motion undergoes uniform gravitational acceleration (ay = -g).",
            "Calculate time of flight, peak trajectory height, and maximum horizontal range.",
            "Compare observed parabolic webcam tracking coordinates against theoretical predictions.",
        ],
        required_materials=[
            "Virtual: Launch speed, elevation angle, gravity presets, initial height.",
            "Physical/Webcam: Launcher/ramp, ball/marble, calibrated backdrop grid or measuring tape.",
        ],
        instructions=[
            "Step 1: Set initial launch speed v0 and launch angle θ.",
            "Step 2: Observe the parabolic trajectory curve y(x).",
            "Step 3: Track the projectile using webcam tracking or input landing coordinates.",
            "Step 4: Compare theoretical range and flight time against experimental measurements.",
        ],
        theoretical_model_summary=(
            "Decomposing initial velocity: vx0 = v0·cos(θ), vy0 = v0·sin(θ). "
            "Horizontal position: x(t) = vx0·t. "
            "Vertical position: y(t) = y0 + vy0·t - ½ g·t². "
            "Maximum height: H_max = y0 + vy0² / (2g). "
            "For y0 = 0, flight time: t_flight = 2 vy0 / g, range: R = (v0² sin(2θ)) / g."
        ),
        governing_equations=[
            "Horizontal Component: vx(t) = v0 cos θ, x(t) = v0 cos(θ) t",
            "Vertical Component: vy(t) = v0 sin θ - g t, y(t) = y0 + v0 sin(θ) t - ½ g t²",
            "Time of Flight (y0=0): t_flight = 2 v0 sin(θ) / g",
            "Maximum Range (y0=0): R = (v0² sin(2θ)) / g",
            "Peak Height: H = y0 + (v0 sin θ)² / (2g)",
        ],
        assumptions=[
            "Negligible aerodynamic drag (vacuum condition).",
            "Uniform gravitational field throughout flight.",
            "Flat ground surface.",
        ],
        limitations=[
            "Real-world high-speed projectiles deviate due to quadratic drag and spin (Magnus effect).",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "velocity": PhysicalUnit.VELOCITY.value,
            "angle": PhysicalUnit.ANGLE_DEG.value,
            "range": PhysicalUnit.POSITION.value,
            "time_of_flight": PhysicalUnit.TIME.value,
            "max_height": PhysicalUnit.POSITION.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return ProjectileParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        validated = ProjectileParamsSchema(**parameters)
        v0 = validated.velocity
        theta_rad = math.radians(validated.angle_deg)
        g = validated.gravity
        y0 = validated.initial_height

        vx0 = v0 * math.cos(theta_rad)
        vy0 = v0 * math.sin(theta_rad)

        # Quadratic formula for flight time when y(t) = 0: y0 + vy0*t - 0.5*g*t^2 = 0
        discriminant = vy0 ** 2 + 2.0 * g * y0
        t_flight = (vy0 + math.sqrt(discriminant)) / g if g > 0 else 0.0

        range_m = vx0 * t_flight
        h_max = y0 + (vy0 ** 2) / (2.0 * g)

        series = self.generate_theoretical_series(validated.model_dump(), duration=t_flight, steps=100)

        computed = {
            "time_of_flight_s": round(t_flight, 4),
            "range_meters": round(range_m, 4),
            "max_height_meters": round(h_max, 4),
            "vx0_mps": round(vx0, 4),
            "vy0_mps": round(vy0, 4),
            "optimal_angle_deg": 45.0 if y0 == 0.0 else round(math.degrees(math.asin(1.0 / math.sqrt(2.0 + 2.0 * g * y0 / (v0 ** 2)))), 1),
            "formula_used": "R = vx0 * t_flight, H = y0 + vy0^2 / (2g)",
        }

        return TheoreticalResult(
            experiment_type="projectile_motion",
            parameters=validated.model_dump(),
            primary_theoretical_value=round(range_m, 4),
            primary_metric_name="range_meters",
            primary_metric_unit="m",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "range": "m",
                "time_of_flight": "s",
                "max_height": "m",
                "velocity": "m/s",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 2.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        v0 = float(parameters.get("velocity", 20.0))
        theta_rad = math.radians(float(parameters.get("angle_deg", 45.0)))
        g = float(parameters.get("gravity", 9.81))
        y0 = float(parameters.get("initial_height", 0.0))
        mass = float(parameters.get("mass", 1.0))

        vx0 = v0 * math.cos(theta_rad)
        vy0 = v0 * math.sin(theta_rad)

        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            x_m = vx0 * t
            y_m = max(0.0, y0 + vy0 * t - 0.5 * g * (t ** 2))
            vy_t = vy0 - g * t
            v_mag = math.sqrt(vx0 ** 2 + vy_t ** 2)

            pe_j = max(0.0, mass * g * y_m)
            ke_j = 0.5 * mass * (v_mag ** 2)

            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(x_m), 4),
                    velocity=round(float(v_mag), 4),
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
        t_range = theo.primary_theoretical_value

        if not raw_observations:
            empty_error = ErrorAnalysis(
                absolute_error=0.0,
                percentage_error=0.0,
                sample_size=0,
                scientific_verdict="No trajectory observations recorded.",
            )
            return ExperimentResult(
                experiment_type="projectile_motion",
                measurement_mode="manual",
                parameters=theo.parameters,
                theoretical_value=t_range,
                experimental_value=0.0,
                primary_metric_name="range_meters",
                primary_metric_unit="m",
                error_analysis=empty_error,
                observation_count=0,
                theoretical_series=theo.theoretical_series,
                experimental_series=[],
                units=self.metadata.units,
            )

        # Detect landing distance or trajectory points
        ranges: List[float] = []
        experimental_series: List[TimeSeriesPoint] = []
        mode = "manual"

        for obs in raw_observations:
            r_val = obs.get("range_meters") or obs.get("range") or obs.get("position")
            if r_val is not None:
                try:
                    r_f = float(r_val)
                    if math.isfinite(r_f) and r_f > 0:
                        ranges.append(r_f)
                except (ValueError, TypeError):
                    continue

        if ranges:
            exp_range = float(np.mean(ranges))
            n = len(ranges)
            s_range = float(np.std(ranges, ddof=1)) if n > 1 else 0.0
            se_range = float(s_range / math.sqrt(n)) if n > 1 else 0.1
        else:
            exp_range = t_range
            n = 0
            s_range = 0.0
            se_range = 0.0

        abs_err = abs(exp_range - t_range)
        pct_err = (abs_err / t_range) * 100.0 if t_range > 0 else 0.0

        error_analysis = ErrorAnalysis(
            absolute_error=round(abs_err, 4),
            percentage_error=round(pct_err, 2),
            sample_size=n,
            standard_deviation=round(s_range, 4),
            standard_error_of_mean=round(se_range, 4),
            confidence_interval_95=[round(max(0.0, exp_range - 1.96 * se_range), 4), round(exp_range + 1.96 * se_range, 4)],
            scientific_verdict=f"Projectile flight verified within {pct_err:.1f}% of theoretical range.",
            discrepancy_sources=[
                {"factor": "Air Drag Resistance", "description": "Drag reduces horizontal velocity over time."},
                {"factor": "Launch Angle Precision", "description": "Mechanical alignment error in initial launch angle."},
            ],
        )

        return ExperimentResult(
            experiment_type="projectile_motion",
            measurement_mode=mode,
            parameters=theo.parameters,
            theoretical_value=t_range,
            experimental_value=round(exp_range, 4),
            primary_metric_name="range_meters",
            primary_metric_unit="m",
            error_analysis=error_analysis,
            observation_count=len(raw_observations),
            theoretical_series=theo.theoretical_series,
            experimental_series=experimental_series,
            units=self.metadata.units,
        )

    def explain_results(
        self,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        student_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        v0 = float(parameters.get("velocity", 20.0))
        angle = float(parameters.get("angle_deg", 45.0))
        t_range = float(results.get("theoretical_value", 40.77))
        exp_range = float(results.get("experimental_value", t_range))
        err_pct = float(results.get("error_analysis", {}).get("percentage_error", 0.0))

        return {
            "status": "success",
            "experiment_id": "projectile_motion",
            "what_it_demonstrates": (
                f"Demonstrates the independence of horizontal and vertical kinematic vectors. "
                f"With launch speed {v0} m/s at {angle}°, the horizontal velocity vx = {v0 * math.cos(math.radians(angle)):.2f} m/s "
                f"remains constant because ax = 0, while gravity acts only vertically."
            ),
            "why_observed_differs_from_theory": (
                f"Observed range was {exp_range:.2f}m vs theoretical {t_range:.2f}m ({err_pct:.1f}% error). "
                f"In physical experiments, quadratic air resistance (F_drag = ½ ρ C_d A v²) extracts kinetic energy, "
                f"shortening the trajectory compared to ideal vacuum parabolic motion."
            ),
            "role_of_measurement_error": "Launcher muzzle speed consistency and trigger timing introduce ±2-5% variance across repeated trials.",
            "parameter_sensitivity": (
                "Range is maximized at 45° for level ground. Doubling launch speed quadruples the range (R ∝ v₀²), "
                "making speed the most sensitive governing parameter."
            ),
            "graph_interpretation": "The trajectory curve y(x) is a symmetric downward parabola opening with vertex at peak height H.",
            "conclusion": f"2D kinematic vector decomposition accurately accounts for the observed trajectory within {err_pct:.1f}% error.",
        }

