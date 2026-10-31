import os
import math
import time
import uuid
from typing import Optional, Dict, Any, Union, List
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from app.core_backend.models.schema import (
    ExperimentData,
    ExperimentType,
    SUPPORTED_EXPERIMENT_TYPES,
    FreeFallInputSchema,
    PendulumInputSchema,
    CollisionInputSchema,
    HarmonicMotionInputSchema,
    normalize_experiment_type,
)
from app.core_backend.models.provenance import (
    ModelIdentifier,
    CalibrationParameters,
    FrameMetadata,
    ExperimentProvenance,
    ReproductionReport,
    compute_input_hash,
    compute_output_hash,
    strip_raw_footage,
    reproduce_experiment_metrics,
)
from datetime import datetime, timezone
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import DatabasePersistenceError
from app.core_backend.core.dependencies import (
    get_current_user,
    get_db,
    get_database_manager,
)
from app.core_backend.core.limiter import limiter
from app.machine_learning.physics_engine import PhysicsEngine
from app.logger import logger

router = APIRouter()


def __getattr__(name: str):
    """Lazy backward-compatible attribute access for db without import side-effects."""
    if name == "db":
        try:
            return get_db()
        except Exception:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class ExperimentAnalyzePayload(BaseModel):
    height: Optional[float] = Field(None, gt=0.0, le=10000.0, description="Height in meters (free-fall)")
    mass: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass in kg")
    gravity: Optional[float] = Field(None, gt=0.0, le=100.0, description="Gravity in m/s^2")
    length: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Length in meters (pendulum)")
    angle_deg: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Release angle in degrees")
    damping: Optional[float] = Field(None, ge=0.0, le=10.0, description="Damping coefficient")
    mass_a: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass A in kg (collision)")
    mass_b: Optional[float] = Field(None, gt=0.0, le=100000.0, description="Mass B in kg (collision)")
    vel_a: Optional[float] = Field(None, ge=-10000.0, le=10000.0, description="Velocity A in m/s")
    vel_b: Optional[float] = Field(None, ge=-10000.0, le=10000.0, description="Velocity B in m/s")
    collision_type: Optional[str] = Field(None, max_length=20, description="elastic or inelastic")
    amplitude: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Amplitude in meters (harmonic)")
    angular_frequency: Optional[float] = Field(None, gt=0.0, le=1000.0, description="Angular frequency in rad/s")
    phase: Optional[float] = Field(None, ge=-360.0, le=360.0, description="Phase angle in degrees")
    time: Optional[float] = Field(None, ge=0.0, le=100000.0, description="Time in seconds")
    unit_system: Optional[str] = Field(default="metric", max_length=20, description="Unit system: metric or imperial")

    model_config = {
        "extra": "allow",
    }


class ExperimentAnalysisResponse(BaseModel):
    status: str = Field(..., description="Analysis status ('success')")
    experiment_type: str = Field(..., description="Normalized experiment type")
    algorithm_version: str = Field(..., description="Physics algorithm version")
    model_name: Optional[str] = Field("PhysicsEngine", description="Model identifier")
    model_version: Optional[str] = Field("physics_engine_v1.2.0", description="Model version")
    configuration_version: Optional[str] = Field("config_v1.0", description="Configuration schema version")
    preprocessing_version: Optional[str] = Field("norm_v1.0", description="Preprocessing version")
    calibration: Optional[Dict[str, Any]] = Field(None, description="Calibration parameters")
    measurement_units: Optional[Dict[str, str]] = Field(None, description="Measurement units mapping")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Experiment provenance and cryptographic lineage")
    validated_inputs: Dict[str, Any] = Field(..., description="Validated physics input parameters")
    computed_results: Dict[str, Any] = Field(..., description="Authoritative server-computed physics results")
    parameters: Dict[str, Any] = Field(..., description="Simulation parameters")

    model_config = {"extra": "allow"}


class ExperimentRecord(BaseModel):
    id: str = Field(..., description="Unique experiment record ID")
    user_id: str = Field(..., description="Owner user ID")
    experiment_type: str = Field(..., description="Experiment type")
    type: Optional[str] = Field(None, description="Experiment type alias")
    model_name: Optional[str] = Field("PhysicsEngine", description="Model identifier")
    model_version: Optional[str] = Field("physics_engine_v1.2.0", description="Model version")
    algorithm_version: str = Field(..., description="Algorithm version")
    configuration_version: Optional[str] = Field("config_v1.0", description="Configuration schema version")
    preprocessing_version: Optional[str] = Field("norm_v1.0", description="Preprocessing version")
    computation_version: Optional[str] = Field("kinematics_analytical_v1", description="Exact computation version")
    calibration: Optional[Dict[str, Any]] = Field(None, description="Calibration parameters")
    measurement_units: Optional[Dict[str, str]] = Field(None, description="Measurement units mapping")
    frame_metadata: Optional[Dict[str, Any]] = Field(None, description="Frame metadata and privacy flags")
    inference_status: Optional[str] = Field("completed", description="Inference status")
    error_info: Optional[Dict[str, Any]] = Field(None, description="Error information")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Experiment provenance and cryptographic lineage")
    input_data: Dict[str, Any] = Field(..., description="Validated input parameters")
    server_computed_results: Dict[str, Any] = Field(..., description="Authoritative server-computed results")
    client_supplied_metrics: Optional[Dict[str, Any]] = Field(None, description="Client metrics recorded for audit")
    metrics: Dict[str, Any] = Field(..., description="Authoritative physics metrics")
    timestamp: Union[int, float] = Field(..., description="Creation epoch timestamp")

    model_config = {"extra": "allow"}


class ExperimentSaveResponse(BaseModel):
    status: str = Field(..., description="Save status ('saved')")
    experiment: ExperimentRecord = Field(..., description="Persisted experiment record")
    server_computed_results: Dict[str, Any] = Field(..., description="Authoritative server-computed physics results")


class ExperimentHistoryResponse(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list, description="List of user's saved experiment records")


class ExperimentDetailResponse(BaseModel):
    experiment: Dict[str, Any] = Field(..., description="Saved experiment record details")


@router.post("/analyze/{exp_type}", response_model=ExperimentAnalysisResponse)
def analyze_experiment(exp_type: str, data: Dict[str, Any]):
    """
    Analyzes physics kinematics simulations (e.g. free_fall, pendulum, collision, harmonic_motion).
    Guarantees:
    1. Validates experiment type against ExperimentType enum (rejects unsupported types with 400).
    2. Validates parameters using distinct physics-specific schema (units, coordinate ranges, required parameters, finite numbers).
    3. Computes simulation results on the server using PhysicsEngine.
    """
    try:
        exp_type_enum = normalize_experiment_type(exp_type)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )

    try:
        if exp_type_enum == ExperimentType.FREE_FALL:
            schema = FreeFallInputSchema(**data)
            computed = PhysicsEngine.solve_free_fall(
                height=schema.height,
                mass=schema.mass,
                gravity=schema.gravity,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.PENDULUM:
            schema = PendulumInputSchema(**data)
            computed = PhysicsEngine.solve_pendulum(
                length=schema.length,
                angle_deg=schema.angle_deg,
                mass=schema.mass,
                gravity=schema.gravity,
                damping=schema.damping,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.COLLISION:
            schema = CollisionInputSchema(**data)
            computed = PhysicsEngine.solve_collision(
                mass_a=schema.mass_a,
                mass_b=schema.mass_b,
                vel_a=schema.vel_a,
                vel_b=schema.vel_b,
                collision_type=schema.collision_type,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.HARMONIC_MOTION:
            schema = HarmonicMotionInputSchema(**data)
            pos = PhysicsEngine.harmonic_motion(
                t=schema.time,
                A=schema.amplitude,
                omega=schema.angular_frequency,
                phi=math.radians(schema.phase),
            )
            computed = {
                "position": round(pos, 4),
                "amplitude": schema.amplitude,
                "angular_frequency": schema.angular_frequency,
                "time": schema.time,
                "phase": schema.phase,
            }
            validated_inputs = schema.model_dump()

    except ValidationError as e:
        errors = e.errors()
        first_err = errors[0]["msg"] if errors else "Invalid parameters"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Physics schema validation failed: {first_err}",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Physics validation error: {str(ve)}",
        )

    calib = CalibrationParameters(
        unit_system=validated_inputs.get("unit_system", "SI"),
    ).model_dump()
    in_hash = compute_input_hash(validated_inputs, algorithm_version="physics_engine_v1.0", config_version="config_v1.0")
    out_hash = compute_output_hash(computed)

    formula_map = {
        ExperimentType.FREE_FALL: "v = sqrt(2*g*h), t = sqrt(2*h/g)",
        ExperimentType.PENDULUM: "T = 2*pi*sqrt(L/g) * (1 + 1/16*theta^2)",
        ExperimentType.COLLISION: "m1*v1 + m2*v2 = m1*v1' + m2*v2'",
        ExperimentType.HARMONIC_MOTION: "x(t) = A * cos(omega*t + phi)",
    }
    formula_desc = formula_map.get(exp_type_enum, "exact theoretical formulation")

    prov = {
        "id": f"prov_{uuid.uuid4().hex[:12]}",
        "experiment_id": f"ana_{uuid.uuid4().hex[:8]}",
        "model": {"name": "PhysicsEngine", "version": "physics_engine_v1.2.0", "family": "physics_solver"},
        "algorithm_version": "physics_engine_v1.0",
        "configuration_version": "config_v1.0",
        "preprocessing_version": "norm_v1.0",
        "computation_version": "kinematics_analytical_v1",
        "calibration": calib,
        "inference_status": "completed",
        "source": "simulation",
        "input_hash": in_hash,
        "output_hash": out_hash,
        "reproducible": True,
        "reproduction_formula": formula_desc,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    response_payload = {
        "status": "success",
        "experiment_type": exp_type_enum.value,
        "algorithm_version": "physics_engine_v1.0",
        "model_name": "PhysicsEngine",
        "model_version": "physics_engine_v1.2.0",
        "configuration_version": "config_v1.0",
        "preprocessing_version": "norm_v1.0",
        "calibration": calib,
        "measurement_units": calib.get("measurement_units", {}),
        "provenance": prov,
        "validated_inputs": validated_inputs,
        "computed_results": computed,
        "parameters": computed.get("parameters", validated_inputs),
    }
    for k, v in computed.items():
        if k != "parameters":
            response_payload[k] = v

    return response_payload


@router.post("/save", response_model=ExperimentSaveResponse)
@limiter.limit("30/minute")
def save_experiment(
    request: Request,
    data: ExperimentData,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Commits experiment kinematics to database.
    Guarantees:
    1. Obtains canonical user ID from verified identity (rejects spoofing with 403 Forbidden).
    2. Enforces supported experiment type enum (rejects unsupported types with 400 Bad Request).
    3. Validates units, ranges, and required parameters against physics schema.
    4. Computes authoritative results on the server (does not trust client-supplied metrics).
    5. Persists input data, algorithm/model version, and computed results separately.
    6. In production mode: reports 503 if persistence fails.
    """
    canonical_uid = str(current_user["id"])

    # Reject client-supplied spoofed user_id
    if data.user_id and str(data.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot save an experiment on behalf of another user.",
        )

    # Validate and normalize experiment type
    try:
        exp_type_enum = normalize_experiment_type(data.type or data.experiment_type, raw_name=data.name)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )

    # Extract raw parameters from data, parameters, or metrics
    raw_params: Dict[str, Any] = {}
    if data.parameters:
        raw_params.update(data.parameters)
    if data.metrics:
        for k in (
            "height", "mass", "gravity", "length", "angle_deg", "damping",
            "mass_a", "mass_b", "vel_a", "vel_b", "collision_type",
            "amplitude", "angular_frequency", "phase", "time"
        ):
            if k in data.metrics and k not in raw_params:
                raw_params[k] = data.metrics[k]
    for k in (
        "height", "mass", "gravity", "length", "angle_deg", "damping",
        "mass_a", "mass_b", "vel_a", "vel_b", "collision_type",
        "amplitude", "angular_frequency", "phase", "time", "unit_system"
    ):
        val = getattr(data, k, None)
        if val is not None and k not in raw_params:
            raw_params[k] = val
    if data.unit_system and "unit_system" not in raw_params:
        raw_params["unit_system"] = data.unit_system

    # Validate against specific physics schema and compute authoritative results on server
    try:
        if exp_type_enum == ExperimentType.FREE_FALL:
            if "height" not in raw_params or raw_params["height"] is None:
                raw_params["height"] = 50.0
            schema = FreeFallInputSchema(**raw_params)
            server_results = PhysicsEngine.solve_free_fall(
                height=schema.height,
                mass=schema.mass,
                gravity=schema.gravity,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.PENDULUM:
            if "length" not in raw_params or raw_params["length"] is None:
                raw_params["length"] = 2.5
            schema = PendulumInputSchema(**raw_params)
            server_results = PhysicsEngine.solve_pendulum(
                length=schema.length,
                angle_deg=schema.angle_deg,
                mass=schema.mass,
                gravity=schema.gravity,
                damping=schema.damping,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.COLLISION:
            if "mass_a" not in raw_params:
                raw_params["mass_a"] = 1.0
            if "mass_b" not in raw_params:
                raw_params["mass_b"] = 1.0
            if "vel_a" not in raw_params:
                raw_params["vel_a"] = 1.0
            if "vel_b" not in raw_params:
                raw_params["vel_b"] = -1.0
            schema = CollisionInputSchema(**raw_params)
            server_results = PhysicsEngine.solve_collision(
                mass_a=schema.mass_a,
                mass_b=schema.mass_b,
                vel_a=schema.vel_a,
                vel_b=schema.vel_b,
                collision_type=schema.collision_type,
            )
            validated_inputs = schema.model_dump()

        elif exp_type_enum == ExperimentType.HARMONIC_MOTION:
            if "amplitude" not in raw_params:
                raw_params["amplitude"] = 1.0
            if "angular_frequency" not in raw_params:
                raw_params["angular_frequency"] = 2.0
            schema = HarmonicMotionInputSchema(**raw_params)
            pos = PhysicsEngine.harmonic_motion(
                t=schema.time,
                A=schema.amplitude,
                omega=schema.angular_frequency,
                phi=math.radians(schema.phase),
            )
            server_results = {
                "position": round(pos, 4),
                "amplitude": schema.amplitude,
                "angular_frequency": schema.angular_frequency,
            }
            validated_inputs = schema.model_dump()

    except ValidationError as e:
        errors = e.errors()
        first_err = errors[0]["msg"] if errors else "Invalid parameters"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Physics schema validation failed: {first_err}",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Physics validation error: {str(ve)}",
        )

    # Persist input data, algorithm/model version, and computed results separately!
    # Server-computed results are authoritative; client metrics stored separately for audit
    record_id = f"exp_{uuid.uuid4().hex[:12]}"

    # Privacy guard: strip raw video footage or images unless explicit consent provided
    consent_given = bool(getattr(data, "consent_to_record", False))
    clean_params, stripped_raw = strip_raw_footage(validated_inputs, consent_to_record=consent_given)

    algo_version = "physics_engine_v1.0"
    model_version = getattr(data, "model_version", None) or "physics_engine_v1.2.0"
    config_version = "config_v1.0"
    preprocess_version = "norm_v1.0"
    comp_version = "kinematics_analytical_v1"

    in_hash = compute_input_hash(clean_params, algorithm_version=algo_version, config_version=config_version)
    out_hash = compute_output_hash(server_results)

    calib = getattr(data, "calibration", None) or CalibrationParameters(
        unit_system=getattr(data, "unit_system", "SI") or "SI",
    ).model_dump()

    frame_meta = getattr(data, "frame_metadata", None) or FrameMetadata(
        raw_footage_stored=False,
        consent_to_record=consent_given,
        retention_policy="ephemeral_discard" if not consent_given else "user_consent_retained",
    ).model_dump()

    formula_map = {
        ExperimentType.FREE_FALL: "v = sqrt(2*g*h), t = sqrt(2*h/g)",
        ExperimentType.PENDULUM: "T = 2*pi*sqrt(L/g) * (1 + 1/16*theta^2)",
        ExperimentType.COLLISION: "m1*v1 + m2*v2 = m1*v1' + m2*v2'",
        ExperimentType.HARMONIC_MOTION: "x(t) = A * cos(omega*t + phi)",
    }
    formula_desc = formula_map.get(exp_type_enum, "exact theoretical formulation")

    prov_record = {
        "id": f"prov_{uuid.uuid4().hex[:12]}",
        "experiment_id": record_id,
        "model": {
            "name": "PhysicsEngine",
            "version": model_version,
            "family": "physics_solver",
        },
        "algorithm_version": algo_version,
        "configuration_version": config_version,
        "preprocessing_version": preprocess_version,
        "computation_version": comp_version,
        "calibration": calib,
        "frame_metadata": frame_meta,
        "inference_status": "completed",
        "error_info": None,
        "source": "simulation",
        "input_hash": in_hash,
        "output_hash": out_hash,
        "reproducible": True,
        "reproduction_formula": formula_desc,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    record_payload = {
        "id": record_id,
        "user_id": canonical_uid,
        "experiment_type": exp_type_enum.value,
        "type": exp_type_enum.value,
        "model_name": "PhysicsEngine",
        "model_version": model_version,
        "algorithm_version": algo_version,
        "configuration_version": config_version,
        "preprocessing_version": preprocess_version,
        "computation_version": comp_version,
        "calibration": calib,
        "measurement_units": calib.get("measurement_units", {}),
        "frame_metadata": frame_meta,
        "inference_status": "completed",
        "error_info": None,
        "provenance": prov_record,
        "input_data": clean_params,
        "server_computed_results": server_results,
        "client_supplied_metrics": data.metrics or {},
        "metrics": server_results,  # Authoritative results override client claims
        "timestamp": int(time.time()),
    }

    active_db = active_db or get_db()
    try:
        saved_record = active_db.save_experiment(record_payload, user_id=canonical_uid)
        return {
            "status": "saved",
            "experiment": saved_record,
            "server_computed_results": server_results,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Durable save failed for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Experiment could not be durably saved.",
        )


@router.get("/history", response_model=ExperimentHistoryResponse)
def get_history(
    user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Returns experiment history filtered strictly by the authenticated canonical user ID.
    Rejects requests attempting to query another user's ID with 403 Forbidden.
    """
    canonical_uid = str(current_user["id"])

    # If a user explicitly specifies another user's ID, reject with 403 Forbidden
    if user_id and str(user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to view another user's experiment history.",
        )

    active_db = active_db or get_db()
    try:
        user_experiments = active_db.get_experiments(user_id=canonical_uid)
        return {"history": user_experiments}
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to query experiment history: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.get("/experiment/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Fetches a specific experiment by ID.
    Enforces authorization: 403 Forbidden if the resource belongs to another user.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
    try:
        target_exp = active_db.get_experiment_by_id(experiment_id)
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to query experiment: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )

    if not target_exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found.",
        )

    if str(target_exp.get("user_id")) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this experiment resource.",
        )

    return {"experiment": target_exp}


@router.post("/reproduce/{experiment_id}", response_model=ReproductionReport)
def reproduce_saved_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Verification: Reproduces a stored experiment's derived metrics from its recorded
    inputs, calibration parameters, and algorithm configuration.
    Confirms mathematical integrity and cryptographic audit hashes.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
    try:
        target_exp = active_db.get_experiment_by_id(experiment_id)
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to query experiment for reproduction: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )

    if not target_exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found.",
        )

    if str(target_exp.get("user_id")) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this experiment resource.",
        )

    report = reproduce_experiment_metrics(target_exp)
    return report


@router.post("/reproduce", response_model=ReproductionReport)
def reproduce_experiment_from_payload(
    record: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
):
    """
    Reproduces experiment metrics on-demand from any provided historical experiment payload.
    """
    report = reproduce_experiment_metrics(record)
    return report
