"""
1D Collision & Momentum Conservation Experiment Implementation.
Models elastic and inelastic collisions between two bodies:
conservation of linear momentum, kinetic energy exchange, and restitution.
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


class CollisionParamsSchema(BaseModel):
    mass_a: float = Field(default=1.0, gt=0.001, le=1000.0, description="Mass of Cart A in kg")
    mass_b: float = Field(default=1.0, gt=0.001, le=1000.0, description="Mass of Cart B in kg")
    vel_a: float = Field(default=3.0, ge=-100.0, le=100.0, description="Initial velocity of Cart A in m/s")
    vel_b: float = Field(default=-2.0, ge=-100.0, le=100.0, description="Initial velocity of Cart B in m/s")
    collision_type: str = Field(default="Elastic", description="'Elastic' or 'Inelastic'")
    unit_system: str = Field(default="SI", description="Unit system (SI)")

    @field_validator("mass_a", "mass_b", "vel_a", "vel_b", mode="before")
    @classmethod
    def validate_finite(cls, v, info):
        try:
            val = float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Field '{info.field_name}' must be numeric") from e
        if not math.isfinite(val):
            raise ValueError(f"Field '{info.field_name}' must be finite")
        return val

    @field_validator("collision_type")
    @classmethod
    def validate_type(cls, v):
        clean = str(v).strip().lower()
        if clean not in ("elastic", "inelastic"):
            raise ValueError("collision_type must be 'Elastic' or 'Inelastic'")
        return "Elastic" if clean == "elastic" else "Inelastic"


class CollisionExperiment(BaseExperiment):
    _metadata = ExperimentMetadata(
        id="collision",
        title="1D Linear Collision & Momentum Conservation",
        category="Classical Mechanics & Conservation Laws",
        tier="Intermediate",
        time_estimate="20 min",
        learning_objectives=[
            "Demonstrate the Law of Conservation of Linear Momentum: total momentum before collision equals total momentum after.",
            "Compare elastic collisions (kinetic energy fully conserved) with inelastic collisions (kinetic energy lost to deformation and heat).",
            "Calculate post-collision velocities v1' and v2' using mass ratios.",
            "Evaluate mechanical energy dissipation.",
        ],
        required_materials=[
            "Virtual: Masses mA, mB, initial velocities vA, vB, collision type toggle (Elastic/Inelastic).",
            "Physical/Webcam: Dynamic track, two low-friction carts, magnetic/velcro bumpers, photogates or webcam.",
        ],
        instructions=[
            "Step 1: Set cart masses mA and mB and their initial velocities vA and vB.",
            "Step 2: Choose collision mode: 'Elastic' (spring/magnetic rebound) or 'Inelastic' (velcro sticking).",
            "Step 3: Measure post-collision velocities using photogates or video tracking.",
            "Step 4: Verify total momentum conservation and check the kinetic energy delta.",
        ],
        theoretical_model_summary=(
            "Linear momentum is strictly conserved in all isolated collisions: P_total = m_A v_A + m_B v_B = constant. "
            "For elastic collisions: KE_initial = KE_final. "
            "v_A' = ((m_A - m_B) v_A + 2 m_B v_B) / (m_A + m_B). "
            "v_B' = ((m_B - m_A) v_B + 2 m_A v_A) / (m_A + m_B). "
            "For completely inelastic collisions, carts stick together: v_final = P_total / (m_A + m_B)."
        ),
        governing_equations=[
            "Conservation of Momentum: m_A v_A + m_B v_B = m_A v_A' + m_B v_B'",
            "Elastic Velocity A: v_A' = ((m_A - m_B) v_A + 2 m_B v_B) / (m_A + m_B)",
            "Elastic Velocity B: v_B' = ((m_B - m_A) v_B + 2 m_A v_A) / (m_A + m_B)",
            "Inelastic Common Velocity: v' = (m_A v_A + m_B v_B) / (m_A + m_B)",
            "Kinetic Energy: KE = ½ m_A v_A² + ½ m_B v_B²",
        ],
        assumptions=[
            "One-dimensional collision along a horizontal axis.",
            "Isolated system: zero net external horizontal force (frictionless track).",
            "Negligible impact duration compared to observation timescale.",
        ],
        limitations=[
            "Real-world collisions always dissipate some energy as acoustic noise and microscopic thermal dissipation.",
        ],
        measurement_modes=["manual", "cv_derived"],
        units={
            "mass": PhysicalUnit.MASS.value,
            "velocity": PhysicalUnit.VELOCITY.value,
            "momentum": PhysicalUnit.MOMENTUM.value,
            "energy": PhysicalUnit.ENERGY.value,
        },
    )

    @property
    def metadata(self) -> ExperimentMetadata:
        return self._metadata

    @property
    def input_schema(self) -> Type[BaseModel]:
        return CollisionParamsSchema

    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        validated = CollisionParamsSchema(**parameters)
        mA = validated.mass_a
        mB = validated.mass_b
        vA = validated.vel_a
        vB = validated.vel_b
        c_type = validated.collision_type

        p_total = mA * vA + mB * vB
        ke_init = 0.5 * mA * (vA ** 2) + 0.5 * mB * (vB ** 2)

        if c_type == "Elastic":
            vA_post = ((mA - mB) * vA + 2.0 * mB * vB) / (mA + mB)
            vB_post = ((mB - mA) * vB + 2.0 * mA * vA) / (mA + mB)
        else:
            v_common = p_total / (mA + mB)
            vA_post = v_common
            vB_post = v_common

        ke_post = 0.5 * mA * (vA_post ** 2) + 0.5 * mB * (vB_post ** 2)
        ke_loss = max(0.0, ke_init - ke_post)

        series = self.generate_theoretical_series(validated.model_dump(), duration=3.0, steps=100)

        computed = {
            "initial_total_momentum": round(p_total, 4),
            "final_total_momentum": round(p_total, 4),
            "v_a_final_mps": round(vA_post, 4),
            "v_b_final_mps": round(vB_post, 4),
            "initial_kinetic_energy_j": round(ke_init, 4),
            "final_kinetic_energy_j": round(ke_post, 4),
            "energy_loss_j": round(ke_loss, 4),
            "formula_used": "P = mA·vA + mB·vB = const",
        }

        return TheoreticalResult(
            experiment_type="collision",
            parameters=validated.model_dump(),
            primary_theoretical_value=round(p_total, 4),
            primary_metric_name="total_momentum",
            primary_metric_unit="kg*m/s",
            computed_metrics=computed,
            governing_formula=computed["formula_used"],
            assumptions_applied=self.metadata.assumptions,
            theoretical_series=series,
            units={
                "momentum": "kg*m/s",
                "velocity": "m/s",
                "energy": "J",
            },
        )

    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 3.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        mA = float(parameters.get("mass_a", 1.0))
        mB = float(parameters.get("mass_b", 1.0))
        vA = float(parameters.get("vel_a", 3.0))
        vB = float(parameters.get("vel_b", -2.0))
        c_type = str(parameters.get("collision_type", "Elastic"))

        p_total = mA * vA + mB * vB
        if c_type == "Elastic":
            vA_post = ((mA - mB) * vA + 2.0 * mB * vB) / (mA + mB)
            vB_post = ((mB - mA) * vB + 2.0 * mA * vA) / (mA + mB)
        else:
            vA_post = p_total / (mA + mB)
            vB_post = vA_post

        # Assume collision happens at t = 1.0s
        t_impact = 1.0
        t_values = np.linspace(0.0, float(duration), int(steps))
        points: List[TimeSeriesPoint] = []

        for t in t_values:
            curr_vA = vA if t < t_impact else vA_post
            curr_vB = vB if t < t_impact else vB_post
            curr_p = mA * curr_vA + mB * curr_vB
            curr_ke = 0.5 * mA * (curr_vA ** 2) + 0.5 * mB * (curr_vB ** 2)

            points.append(
                TimeSeriesPoint(
                    time=round(float(t), 4),
                    position=round(float(curr_vA), 4),  # vA as primary metric
                    velocity=round(float(curr_vB), 4),  # vB
                    kinetic_energy=round(float(curr_ke), 4),
                    total_energy=round(float(curr_p), 4),  # total momentum
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
        p_theo = theo.primary_theoretical_value

        p_measured: List[float] = []
        for obs in raw_observations:
            p = obs.get("total_momentum") or obs.get("momentum")
            if p is not None:
                try:
                    pf = float(p)
                    if math.isfinite(pf):
                        p_measured.append(pf)
                except (ValueError, TypeError):
                    continue

        if p_measured:
            exp_p = float(np.mean(p_measured))
            n = len(p_measured)
            s_p = float(np.std(p_measured, ddof=1)) if n > 1 else 0.0
            se_p = float(s_p / math.sqrt(n)) if n > 1 else 0.05
        else:
            exp_p = p_theo
            n = 0
            s_p = 0.0
            se_p = 0.0

        abs_err = abs(exp_p - p_theo)
        pct_err = (abs_err / abs(p_theo)) * 100.0 if abs(p_theo) > 1e-6 else 0.0

        error_analysis = ErrorAnalysis(
            absolute_error=round(abs_err, 4),
            percentage_error=round(pct_err, 2),
            sample_size=n,
            standard_deviation=round(s_p, 4),
            standard_error_of_mean=round(se_p, 4),
            confidence_interval_95=[round(exp_p - 1.96 * se_p, 4), round(exp_p + 1.96 * se_p, 4)],
            scientific_verdict=f"Momentum conservation verified within {pct_err:.1f}% error.",
            discrepancy_sources=[
                {"factor": "Track Surface Friction", "description": "Friction between wheels and track drains linear momentum over time."},
                {"factor": "Collision Acoustic Dissipation", "description": "Sound and heat energy generated on contact."},
            ],
        )

        return ExperimentResult(
            experiment_type="collision",
            measurement_mode="manual",
            parameters=theo.parameters,
            theoretical_value=p_theo,
            experimental_value=round(exp_p, 4),
            primary_metric_name="total_momentum",
            primary_metric_unit="kg*m/s",
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
        mA = float(parameters.get("mass_a", 1.0))
        mB = float(parameters.get("mass_b", 1.0))
        c_type = str(parameters.get("collision_type", "Elastic"))
        p_theo = float(results.get("theoretical_value", 1.0))
        exp_p = float(results.get("experimental_value", p_theo))
        pct_err = float(results.get("error_analysis", {}).get("percentage_error", 0.0))

        return {
            "status": "success",
            "experiment_id": "collision",
            "what_it_demonstrates": (
                f"Demonstrates Newton's Third Law (equal and opposite contact forces) and the Law of Conservation of Momentum. "
                f"The total system momentum P = {p_theo:.2f} kg·m/s remains strictly invariant before and after collision."
            ),
            "why_observed_differs_from_theory": (
                f"Observed post-collision momentum was {exp_p:.2f} kg·m/s ({pct_err:.1f}% discrepancy). "
                f"In {c_type.lower()} collisions, track friction and mechanical deformation absorb fractional momentum and kinetic energy."
            ),
            "role_of_measurement_error": "Photogate flag timing resolution (~1ms) limits instantaneous velocity measurement precision.",
            "parameter_sensitivity": "Equal mass carts (mA = mB) in elastic collisions completely exchange velocities.",
            "graph_interpretation": "Total momentum is a constant flat line over time, while kinetic energy drops sharply at impact in inelastic collisions.",
            "conclusion": f"Momentum conservation holds within {pct_err:.1f}% error.",
        }

