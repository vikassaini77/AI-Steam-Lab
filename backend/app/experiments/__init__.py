"""
Authoritative Scientific Experiment Engine for NeuroLab AI.
Provides reusable base classes, registry, parameter validation,
theoretical modeling, observation processing, error analysis, and AI explanation.
"""

from app.experiments.base import (
    BaseExperiment,
    ExperimentMetadata,
    TheoreticalResult,
    ExperimentResult,
    Observation,
    TimeSeriesPoint,
)
from app.experiments.registry import experiment_registry
from app.experiments.pendulum import PendulumExperiment
from app.experiments.projectile import ProjectileExperiment
from app.experiments.free_fall import FreeFallExperiment
from app.experiments.circular import CircularMotionExperiment
from app.experiments.harmonic import HarmonicMotionExperiment
from app.experiments.collision import CollisionExperiment

__all__ = [
    "BaseExperiment",
    "ExperimentMetadata",
    "TheoreticalResult",
    "ExperimentResult",
    "Observation",
    "TimeSeriesPoint",
    "experiment_registry",
    "PendulumExperiment",
    "ProjectileExperiment",
    "FreeFallExperiment",
    "CircularMotionExperiment",
    "HarmonicMotionExperiment",
    "CollisionExperiment",
]

