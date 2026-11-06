"""
Central Experiment Registry for NeuroLab AI.
Provides single-source lookup for all supported experiment implementations,
metadata listing, and dynamic execution.
"""
from typing import Dict, Any, List, Optional
from app.experiments.base import BaseExperiment


class ExperimentRegistry:
    """Thread-safe catalog of authoritative scientific experiments."""

    def __init__(self):
        self._experiments: Dict[str, BaseExperiment] = {}

    def register(self, experiment: BaseExperiment) -> None:
        """Registers an experiment instance under its metadata ID."""
        exp_id = experiment.metadata.id.lower().strip()
        self._experiments[exp_id] = experiment

    def get(self, experiment_id: str) -> Optional[BaseExperiment]:
        """Retrieves experiment by ID or normalized alias."""
        clean_id = (experiment_id or "").lower().strip().replace("-", "_").replace(" ", "_")
        # Handle common aliases
        alias_map = {
            "pendulum": "pendulum",
            "simple_pendulum": "pendulum",
            "projectile": "projectile_motion",
            "projectile_motion": "projectile_motion",
            "free_fall": "free_fall",
            "freefall": "free_fall",
            "circular_motion": "circular_motion",
            "circular": "circular_motion",
            "uniform_circular_motion": "circular_motion",
            "harmonic_motion": "harmonic_motion",
            "harmonic": "harmonic_motion",
            "shm": "harmonic_motion",
            "collision": "collision",
            "momentum": "collision",
            "collision_and_momentum": "collision",
        }
        target_key = alias_map.get(clean_id, clean_id)
        return self._experiments.get(target_key)

    def list_all(self) -> List[Dict[str, Any]]:
        """Returns metadata summaries for all registered experiments."""
        return [
            exp.metadata.model_dump()
            for exp in self._experiments.values()
        ]

    def supported_ids(self) -> List[str]:
        """Returns list of registered experiment IDs."""
        return list(self._experiments.keys())


experiment_registry = ExperimentRegistry()

# Register all authoritative experiment implementations
from app.experiments.pendulum import PendulumExperiment
from app.experiments.projectile import ProjectileExperiment
from app.experiments.free_fall import FreeFallExperiment
from app.experiments.circular import CircularMotionExperiment
from app.experiments.harmonic import HarmonicMotionExperiment
from app.experiments.collision import CollisionExperiment

experiment_registry.register(PendulumExperiment())
experiment_registry.register(ProjectileExperiment())
experiment_registry.register(FreeFallExperiment())
experiment_registry.register(CircularMotionExperiment())
experiment_registry.register(HarmonicMotionExperiment())
experiment_registry.register(CollisionExperiment())

