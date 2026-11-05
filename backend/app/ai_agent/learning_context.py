"""
Student Learning Context and Structured Profile Management - Educational AI Layer
Provides lightweight, structured student learning memory prior to or alongside vector search:
- Topics studied & topics completed
- Weak concepts & recurring misconceptions
- Learning progress & mastery scores
- Relevant experiment history
"""
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.logger import logger


class StudentLearningProfile(BaseModel):
    user_id: str = Field(..., description="Canonical student user ID")
    topics_studied: List[str] = Field(default_factory=list, description="Unique list of concepts/topics studied")
    topics_completed: List[str] = Field(default_factory=list, description="List of topics where mastery is confirmed")
    weak_concepts: List[str] = Field(default_factory=list, description="List of topics needing reinforcement")
    previous_mistakes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological log of misconceptions or failed evaluation attempts",
    )
    learning_progress: Dict[str, float] = Field(
        default_factory=dict,
        description="Progress mapping per topic (0.0 to 1.0)",
    )
    relevant_experiment_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent experiment observations and telemetry associated with learning",
    )
    last_active_at: float = Field(default_factory=time.time, description="Epoch timestamp of last interaction")


class LearningContextManager:
    """
    Coordinates structured learning profiles with the persistent database.
    Ensures strict tenant isolation across all student profile operations.
    """
    def __init__(self, db_manager: Any):
        self._db = db_manager

    def get_profile(self, user_id: str) -> StudentLearningProfile:
        """Retrieves or initializes a structured student learning profile."""
        if hasattr(self._db, "get_student_profile"):
            raw_profile = self._db.get_student_profile(user_id)
            if raw_profile:
                return StudentLearningProfile(**raw_profile)

        # Fallback default profile
        return StudentLearningProfile(user_id=user_id)

    def record_mistake(self, user_id: str, concept: str, mistake_summary: str) -> StudentLearningProfile:
        """Records a conceptual mistake or low-confidence attempt."""
        if hasattr(self._db, "record_learning_mistake"):
            raw_profile = self._db.record_learning_mistake(
                user_id=user_id,
                concept=concept,
                mistake_summary=mistake_summary,
            )
            if raw_profile:
                return StudentLearningProfile(**raw_profile)

        profile = self.get_profile(user_id)
        if concept not in profile.weak_concepts:
            profile.weak_concepts.append(concept)
        if concept not in profile.topics_studied:
            profile.topics_studied.append(concept)

        profile.previous_mistakes.append({
            "concept": concept,
            "summary": mistake_summary,
            "timestamp": time.time(),
        })
        profile.last_active_at = time.time()

        if hasattr(self._db, "update_student_profile"):
            self._db.update_student_profile(user_id, profile.model_dump())

        return profile

    def record_mastery(self, user_id: str, concept: str) -> StudentLearningProfile:
        """Records confirmed concept mastery, updating topics_completed and weak_concepts."""
        if hasattr(self._db, "record_topic_progress"):
            raw_profile = self._db.record_topic_progress(user_id=user_id, topic=concept, completed=True)
            if raw_profile:
                return StudentLearningProfile(**raw_profile)

        profile = self.get_profile(user_id)
        if concept not in profile.topics_studied:
            profile.topics_studied.append(concept)
        if concept not in profile.topics_completed:
            profile.topics_completed.append(concept)
        if concept in profile.weak_concepts:
            profile.weak_concepts.remove(concept)

        profile.learning_progress[concept] = 1.0
        profile.last_active_at = time.time()

        if hasattr(self._db, "update_student_profile"):
            self._db.update_student_profile(user_id, profile.model_dump())

        return profile

    def record_experiment_activity(
        self,
        user_id: str,
        experiment_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> StudentLearningProfile:
        """Associates active experiment activity with the student profile."""
        profile = self.get_profile(user_id)
        if experiment_type not in profile.topics_studied:
            profile.topics_studied.append(experiment_type)

        profile.relevant_experiment_history.append({
            "experiment_type": experiment_type,
            "parameters": parameters or {},
            "metrics": metrics or {},
            "timestamp": time.time(),
        })
        # Keep last 10 experiment records
        if len(profile.relevant_experiment_history) > 10:
            profile.relevant_experiment_history = profile.relevant_experiment_history[-10:]

        profile.last_active_at = time.time()
        if hasattr(self._db, "update_student_profile"):
            self._db.update_student_profile(user_id, profile.model_dump())

        return profile
