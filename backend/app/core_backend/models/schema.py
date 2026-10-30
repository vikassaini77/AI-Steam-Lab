import math
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union


class ExperimentType(str, Enum):
    FREE_FALL = "free_fall"
    PENDULUM = "pendulum"
    COLLISION = "collision"
    HARMONIC_MOTION = "harmonic_motion"


SUPPORTED_EXPERIMENT_TYPES = {e.value for e in ExperimentType}
VALID_UNIT_SYSTEMS = {"si", "mks", "metric"}


def validate_finite(v: Any, field_name: str) -> float:
    if v is None:
        return v
    if not isinstance(v, (int, float)):
        try:
            v = float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{field_name}' must be a numeric value, got '{v}'")
    if not math.isfinite(v):
        raise ValueError(f"Field '{field_name}' must be a finite real number, got '{v}'")
    return float(v)


def validate_unit_system(unit_system: Optional[str]) -> str:
    if unit_system is None:
        return "SI"
    cleaned = str(unit_system).strip().lower()
    if cleaned not in VALID_UNIT_SYSTEMS:
        allowed = ", ".join(sorted(VALID_UNIT_SYSTEMS)).upper()
        raise ValueError(f"Unsupported unit system: '{unit_system}'. Allowed unit systems are: {allowed}.")
    return unit_system.upper()


def normalize_experiment_type(raw_type: Optional[str], raw_name: Optional[str] = None) -> ExperimentType:
    """
    Normalizes and validates experiment types against the ExperimentType enum.
    Raises ValueError if the experiment type is unsupported.
    """
    candidate = str(raw_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not candidate and raw_name:
        name_clean = str(raw_name).strip().lower()
        if "pendulum" in name_clean:
            candidate = "pendulum"
        elif "free_fall" in name_clean or "freefall" in name_clean or "free fall" in name_clean:
            candidate = "free_fall"
        elif "collision" in name_clean:
            candidate = "collision"
        elif "harmonic" in name_clean:
            candidate = "harmonic_motion"

    alias_map = {
        "free_fall": ExperimentType.FREE_FALL,
        "freefall": ExperimentType.FREE_FALL,
        "pendulum": ExperimentType.PENDULUM,
        "collision": ExperimentType.COLLISION,
        "harmonic_motion": ExperimentType.HARMONIC_MOTION,
        "harmonicmotion": ExperimentType.HARMONIC_MOTION,
    }

    if candidate in alias_map:
        return alias_map[candidate]

    supported = ", ".join(sorted(SUPPORTED_EXPERIMENT_TYPES))
    raise ValueError(f"Unsupported experiment type: '{raw_type}'. Supported types are: {supported}.")


class FreeFallInputSchema(BaseModel):
    height: float = Field(..., gt=0.0, le=10000.0, description="Initial drop height in meters (m)")
    mass: float = Field(default=1.0, gt=0.0, le=50000.0, description="Object mass in kilograms (kg)")
    gravity: float = Field(default=9.81, gt=0.0, le=100.0, description="Gravitational acceleration in m/s^2")
    unit_system: str = Field(default="SI", description="Unit system (default: SI)")

    @field_validator("height", "mass", "gravity", mode="before")
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite(v, info.field_name)

    @field_validator("unit_system")
    @classmethod
    def check_units(cls, v):
        return validate_unit_system(v)


class PendulumInputSchema(BaseModel):
    length: float = Field(..., gt=0.0, le=1000.0, description="Pendulum string/rod length in meters (m)")
    angle_deg: float = Field(default=45.0, ge=-180.0, le=180.0, description="Initial displacement angle in degrees (°)")
    mass: float = Field(default=1.0, gt=0.0, le=50000.0, description="Bob mass in kilograms (kg)")
    gravity: float = Field(default=9.81, gt=0.0, le=100.0, description="Gravitational acceleration in m/s^2")
    damping: float = Field(default=0.0, ge=0.0, le=10.0, description="Damping coefficient (non-negative)")
    unit_system: str = Field(default="SI", description="Unit system (default: SI)")

    @field_validator("length", "angle_deg", "mass", "gravity", "damping", mode="before")
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite(v, info.field_name)

    @field_validator("unit_system")
    @classmethod
    def check_units(cls, v):
        return validate_unit_system(v)


class CollisionInputSchema(BaseModel):
    mass_a: float = Field(..., gt=0.0, le=100000.0, description="Mass of body A in kg")
    mass_b: float = Field(..., gt=0.0, le=100000.0, description="Mass of body B in kg")
    vel_a: float = Field(..., ge=-10000.0, le=10000.0, description="Initial velocity of body A in m/s")
    vel_b: float = Field(..., ge=-10000.0, le=10000.0, description="Initial velocity of body B in m/s")
    collision_type: str = Field(default="Elastic", description="Collision type: 'Elastic' or 'Inelastic'")
    unit_system: str = Field(default="SI", description="Unit system (default: SI)")

    @field_validator("mass_a", "mass_b", "vel_a", "vel_b", mode="before")
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite(v, info.field_name)

    @field_validator("collision_type")
    @classmethod
    def check_collision_type(cls, v):
        clean = str(v).strip().lower()
        if clean not in ("elastic", "inelastic"):
            raise ValueError(f"Invalid collision_type: '{v}'. Must be 'Elastic' or 'Inelastic'.")
        return "Elastic" if clean == "elastic" else "Inelastic"

    @field_validator("unit_system")
    @classmethod
    def check_units(cls, v):
        return validate_unit_system(v)


class HarmonicMotionInputSchema(BaseModel):
    amplitude: float = Field(..., gt=0.0, le=1000.0, description="Oscillation amplitude in meters (m)")
    angular_frequency: float = Field(..., gt=0.0, le=1000.0, description="Angular frequency omega in rad/s")
    phase: float = Field(default=0.0, ge=-360.0, le=360.0, description="Initial phase phi in degrees or radians")
    time: float = Field(default=1.0, ge=0.0, le=3600.0, description="Evaluation time in seconds")
    unit_system: str = Field(default="SI", description="Unit system (default: SI)")

    @field_validator("amplitude", "angular_frequency", "phase", "time", mode="before")
    @classmethod
    def check_finite(cls, v, info):
        return validate_finite(v, info.field_name)

    @field_validator("unit_system")
    @classmethod
    def check_units(cls, v):
        return validate_unit_system(v)


class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None


class ExperimentData(BaseModel):
    user_id: Optional[str] = Field(None, max_length=128, description="Canonical user ID")
    type: Optional[str] = Field(None, max_length=50, description="Experiment type (free_fall, pendulum, collision, harmonic_motion)")
    experiment_type: Optional[str] = Field(None, max_length=50, description="Alias for experiment type")
    name: Optional[str] = Field(None, max_length=128, description="Experiment title or name")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Simulation parameters dictionary")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Simulation metrics dictionary")
    unit_system: Optional[str] = Field("SI", max_length=20, description="Unit system: SI or Imperial")
    height: Optional[float] = Field(None, gt=0.0, le=10000.0, description="Height in meters")
    mass: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass in kg")
    gravity: Optional[float] = Field(None, gt=0.0, le=100.0, description="Gravity in m/s^2")
    length: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Length in meters")
    angle_deg: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Angle in degrees")
    damping: Optional[float] = Field(None, ge=0.0, le=10.0, description="Damping factor")
    mass_a: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass A in kg")
    mass_b: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass B in kg")
    vel_a: Optional[float] = Field(None, ge=-10000.0, le=10000.0, description="Velocity A in m/s")
    vel_b: Optional[float] = Field(None, ge=-10000.0, le=10000.0, description="Velocity B in m/s")
    collision_type: Optional[str] = Field(None, max_length=20, description="elastic or inelastic")
    amplitude: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Amplitude in meters")
    angular_frequency: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Angular frequency in rad/s")
    phase: Optional[float] = Field(None, ge=-360.0, le=360.0, description="Phase angle in degrees")
    time: Optional[float] = Field(None, ge=0.0, le=100000.0, description="Time in seconds")

    model_config = {
        "extra": "forbid",
    }

class GamificationXP(BaseModel):
    user_id: Optional[str] = None
    action: str = Field(default="general_award", max_length=100)
    amount: int = Field(..., gt=0, le=500, description="XP award amount, strictly positive and capped at 500")
    event_id: Optional[str] = Field(None, max_length=128, description="Unique client or event idempotency key")
    idempotency_key: Optional[str] = Field(None, max_length=128, description="Alias for event_id")
    concept: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None


class EligibilityCriteria(BaseModel):
    criteria_type: str = Field(..., description="Type of criteria: experiment_count, xp_threshold, concept_mastery, event_evidence")
    threshold: Optional[float] = Field(None, description="Numeric threshold if applicable (e.g. 5 experiments, 1000 XP)")
    concept: Optional[str] = Field(None, description="Required concept name for concept_mastery criteria")
    description: Optional[str] = Field(None, description="Human readable description of eligibility condition")


class AchievementDefinition(BaseModel):
    id: str = Field(..., max_length=64, description="Unique achievement ID")
    name: str = Field(..., max_length=128, description="Display name of achievement")
    description: str = Field(..., max_length=512, description="Achievement description")
    badge_icon: str = Field(default="trophy", max_length=64, description="Badge icon identifier")
    tier: str = Field(default="common", max_length=32, description="Tier: common, uncommon, rare, epic, legendary")
    xp_reward: int = Field(default=0, ge=0, le=1000, description="Bonus XP awarded on completion")
    criteria: EligibilityCriteria


class UserAchievement(BaseModel):
    id: str = Field(..., description="Unique record identifier")
    achievement_id: str = Field(..., description="Achievement ID foreign key")
    user_id: str = Field(..., description="Associated user ID")
    awarded_at: str = Field(..., description="ISO 8601 timestamp of award")
    criteria_met: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Criteria verified at time of award")
    evidence: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional evidence or event reference")


class AwardAchievementRequest(BaseModel):
    achievement_id: str = Field(..., max_length=64, description="Achievement to award")
    user_id: Optional[str] = Field(None, max_length=64, description="Optional user ID (must match auth user unless admin)")
    evidence: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Event or experiment evidence verifying eligibility")
    event_id: Optional[str] = Field(None, max_length=128, description="Optional idempotency/event reference key")


ACHIEVEMENT_CATALOG: Dict[str, AchievementDefinition] = {
    "first_steps": AchievementDefinition(
        id="first_steps",
        name="First Steps",
        description="Complete your first scientific experiment",
        badge_icon="target",
        tier="common",
        xp_reward=50,
        criteria=EligibilityCriteria(
            criteria_type="experiment_count",
            threshold=1,
            description="Complete at least 1 experiment in NeuroLab",
        ),
    ),
    "curious_mind": AchievementDefinition(
        id="curious_mind",
        name="Curious Mind",
        description="Engage actively with the AI Tutor on scientific concepts",
        badge_icon="brain",
        tier="common",
        xp_reward=75,
        criteria=EligibilityCriteria(
            criteria_type="event_evidence",
            description="Complete interactive inquiry sessions with AI Tutor",
        ),
    ),
    "physics_explorer": AchievementDefinition(
        id="physics_explorer",
        name="Physics Explorer",
        description="Conduct 5 physics experiments in the lab",
        badge_icon="atom",
        tier="uncommon",
        xp_reward=150,
        criteria=EligibilityCriteria(
            criteria_type="experiment_count",
            threshold=5,
            description="Complete at least 5 scientific experiments",
        ),
    ),
    "gravity_pioneer": AchievementDefinition(
        id="gravity_pioneer",
        name="Gravity Pioneer",
        description="Accurately determine gravitational acceleration within tolerance",
        badge_icon="award",
        tier="rare",
        xp_reward=350,
        criteria=EligibilityCriteria(
            criteria_type="concept_mastery",
            concept="gravity",
            description="Master the gravitational acceleration experiment with empirical verification",
        ),
    ),
    "quantum_leap": AchievementDefinition(
        id="quantum_leap",
        name="Quantum Leap",
        description="Accumulate 1000 authoritative XP across scientific disciplines",
        badge_icon="sparkles",
        tier="epic",
        xp_reward=500,
        criteria=EligibilityCriteria(
            criteria_type="xp_threshold",
            threshold=1000,
            description="Reach 1000 cumulative XP through authenticated learning",
        ),
    ),
    "streak_warrior": AchievementDefinition(
        id="streak_warrior",
        name="Week Warrior",
        description="Maintain a 7-day consistent learning streak",
        badge_icon="flame",
        tier="uncommon",
        xp_reward=200,
        criteria=EligibilityCriteria(
            criteria_type="event_evidence",
            description="Maintain consistent activity across 7 days",
        ),
    ),
}
