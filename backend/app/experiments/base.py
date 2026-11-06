"""
Reusable Base Classes and Abstractions for Scientific Experiments.
Enforces:
1. Complete metadata, learning objectives, materials, and instructions.
2. Parameter validation with strict range and finiteness checks.
3. Separation between theoretical predictions and experimental observations.
4. Error analysis, measurement uncertainty, and physical units.
5. Consistent graphing time-series data structures.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Union
import math
from pydantic import BaseModel, Field


class ExperimentMetadata(BaseModel):
    """Authoritative metadata and educational curriculum information."""
    id: str = Field(..., description="Unique experiment slug (e.g. pendulum, projectile_motion)")
    title: str = Field(..., description="Human-readable title")
    category: str = Field(..., description="Subject category (e.g. Classical Mechanics, Oscillations & Waves)")
    tier: str = Field("Beginner", description="Difficulty tier: Beginner, Intermediate, Advanced")
    time_estimate: str = Field("15 min", description="Estimated completion time")
    learning_objectives: List[str] = Field(default_factory=list, description="Explicit pedagogical goals")
    required_materials: List[str] = Field(default_factory=list, description="Apparatus, instruments, and materials needed")
    instructions: List[str] = Field(default_factory=list, description="Step-by-step experiment procedure")
    theoretical_model_summary: str = Field(..., description="Summary of underlying mathematical and physical laws")
    governing_equations: List[str] = Field(default_factory=list, description="Mathematical formulas with variables")
    small_angle_approximation_note: Optional[str] = Field(
        None, description="Explanation of small-angle or perturbation assumptions where applicable"
    )
    assumptions: List[str] = Field(default_factory=list, description="Physical assumptions (e.g. point mass, negligible drag)")
    limitations: List[str] = Field(default_factory=list, description="Scope and edge limitations")
    measurement_modes: List[str] = Field(
        default_factory=lambda: ["manual", "cv_derived"],
        description="Supported measurement sources"
    )
    units: Dict[str, str] = Field(default_factory=dict, description="Physical units for all parameters and outputs")


class Observation(BaseModel):
    """A timestamped experimental observation (manual stopwatch or CV tracking frame)."""
    timestamp: float = Field(..., description="Timestamp in seconds relative to experiment start")
    position: Optional[float] = Field(None, description="Primary scalar position or displacement in meters")
    position_x: Optional[float] = Field(None, description="X coordinate in meters")
    position_y: Optional[float] = Field(None, description="Y coordinate in meters")
    velocity: Optional[float] = Field(None, description="Instantaneous velocity in m/s")
    velocity_x: Optional[float] = Field(None, description="X velocity in m/s")
    velocity_y: Optional[float] = Field(None, description="Y velocity in m/s")
    acceleration: Optional[float] = Field(None, description="Instantaneous acceleration in m/s^2")
    angle_deg: Optional[float] = Field(None, description="Displacement angle in degrees")
    period_s: Optional[float] = Field(None, description="Manually recorded period time in seconds")
    uncertainty: Optional[float] = Field(None, description="Estimated measurement uncertainty (± value)")
    raw_metadata: Optional[Dict[str, Any]] = Field(None, description="Hardware or detector metadata")

    model_config = {"extra": "allow"}


class TimeSeriesPoint(BaseModel):
    """Uniform data structure for charting and graph visualization."""
    time: float = Field(..., description="Time coordinate in seconds")
    position: Optional[float] = Field(None, description="Position/displacement in meters")
    velocity: Optional[float] = Field(None, description="Velocity in m/s")
    acceleration: Optional[float] = Field(None, description="Acceleration in m/s^2")
    angle_deg: Optional[float] = Field(None, description="Angle in degrees (where applicable)")
    kinetic_energy: Optional[float] = Field(None, description="Kinetic energy in Joules")
    potential_energy: Optional[float] = Field(None, description="Potential energy in Joules")
    total_energy: Optional[float] = Field(None, description="Total mechanical energy in Joules")

    model_config = {"extra": "allow"}


class TheoreticalResult(BaseModel):
    """Pure analytical theoretical physics prediction."""
    experiment_type: str = Field(..., description="Experiment type identifier")
    nature: str = Field("theoretical_physics_prediction", description="Result provenance")
    parameters: Dict[str, Any] = Field(..., description="Validated simulation parameters")
    primary_theoretical_value: float = Field(..., description="Main theoretical metric (e.g. period in s, range in m)")
    primary_metric_name: str = Field("theoretical_period", description="Name of the primary metric")
    primary_metric_unit: str = Field("s", description="SI unit of the primary metric")
    computed_metrics: Dict[str, Any] = Field(..., description="All computed analytical outputs")
    governing_formula: str = Field(..., description="Exact formula used")
    assumptions_applied: List[str] = Field(default_factory=list, description="Assumptions active in this model")
    theoretical_series: List[TimeSeriesPoint] = Field(default_factory=list, description="Discrete points for graphing")
    units: Dict[str, str] = Field(default_factory=dict, description="Units dictionary")


class ErrorAnalysis(BaseModel):
    """Rigorous scientific error analysis and uncertainty breakdown."""
    absolute_error: float = Field(..., description="|Experimental - Theoretical|")
    percentage_error: float = Field(..., description="Absolute error / Theoretical * 100%")
    sample_size: int = Field(..., description="Number of independent physical observations or cycles")
    standard_deviation: Optional[float] = Field(None, description="Sample standard deviation s")
    standard_error_of_mean: Optional[float] = Field(None, description="Standard error SE = s / sqrt(N)")
    confidence_interval_95: Optional[List[float]] = Field(None, description="95% confidence interval [lower, upper]")
    rmse: Optional[float] = Field(None, description="Root-mean-square error for trajectory curves")
    mae: Optional[float] = Field(None, description="Mean absolute error for trajectory curves")
    r_squared: Optional[float] = Field(None, description="Coefficient of determination R^2")
    discrepancy_sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed physical and instrumentation error breakdown"
    )
    scientific_verdict: str = Field(..., description="Conclusion on whether observation agrees with theory within uncertainty")


class ExperimentResult(BaseModel):
    """Complete experimental result combining theoretical modeling, observations, and error analysis."""
    experiment_type: str = Field(..., description="Experiment identifier")
    measurement_mode: str = Field("manual", description="'manual' or 'cv_derived'")
    parameters: Dict[str, Any] = Field(..., description="Input parameters used")
    theoretical_value: float = Field(..., description="Theoretical baseline value")
    experimental_value: float = Field(..., description="Measured experimental value")
    primary_metric_name: str = Field(..., description="Metric name (e.g. period_seconds)")
    primary_metric_unit: str = Field(..., description="Unit (e.g. s)")
    error_analysis: ErrorAnalysis = Field(..., description="Comprehensive error breakdown")
    observation_count: int = Field(..., description="Count of observations processed")
    theoretical_series: List[TimeSeriesPoint] = Field(default_factory=list, description="Theoretical curve points")
    experimental_series: List[TimeSeriesPoint] = Field(default_factory=list, description="Experimental observation points")
    units: Dict[str, str] = Field(default_factory=dict, description="Units mapping")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional experiment metadata")


class BaseExperiment(ABC):
    """
    Abstract Base Class for all scientifically validated experiments.
    Every experiment implements:
    1. metadata: Structured curriculum metadata.
    2. input_schema: Pydantic schema for parameters.
    3. calculate_theoretical: Analytical calculations and time-series generation.
    4. process_measurements: Processing raw observations (manual/CV), extracting cycles, computing error & uncertainty.
    5. explain_results: Structured pedagogical explanation grounded in actual results.
    """

    @property
    @abstractmethod
    def metadata(self) -> ExperimentMetadata:
        """Curriculum and metadata definition."""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Type[BaseModel]:
        """Pydantic schema defining valid parameter inputs."""
        pass

    @abstractmethod
    def calculate_theoretical(self, parameters: Dict[str, Any]) -> TheoreticalResult:
        """Computes authoritative theoretical physics results and benchmark curves."""
        pass

    @abstractmethod
    def generate_theoretical_series(
        self, parameters: Dict[str, Any], duration: float = 4.0, steps: int = 100
    ) -> List[TimeSeriesPoint]:
        """Generates uniformly-spaced theoretical points for graph overlay."""
        pass

    @abstractmethod
    def process_measurements(
        self,
        parameters: Dict[str, Any],
        raw_observations: List[Dict[str, Any]],
        calibration: Optional[Dict[str, Any]] = None,
    ) -> ExperimentResult:
        """
        Processes physical measurements (manual stopwatch entries or CV-derived frame coordinates),
        extracts physical quantities across cycles, and computes scientific error analysis.
        """
        pass

    @abstractmethod
    def explain_results(
        self,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        student_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates contextual AI tutor explanations analyzing discrepancies,
        parameter sensitivity, and physical conclusions without fabricated numbers.
        """
        pass

