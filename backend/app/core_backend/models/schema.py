from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None

class ExperimentData(BaseModel):
    user_id: str
    type: str
    metrics: Dict[str, Any]

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
