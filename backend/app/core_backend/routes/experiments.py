import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from app.core_backend.models.schema import ExperimentData
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import DatabasePersistenceError
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import limiter
from app.machine_learning.physics_engine import PhysicsEngine
from app.logger import logger

router = APIRouter()


def get_database_manager():
    """
    Returns the configured database manager:
    - If POSTGRES_URL is configured or in production: PGVectorManager
    - Otherwise: DatabaseManager (Supabase / local dev)
    """
    if os.getenv("POSTGRES_URL") or os.getenv("ENVIRONMENT") == "production":
        from app.core_backend.database.pgvector_db import PGVectorManager
        return PGVectorManager()
    return DatabaseManager()


db = get_database_manager()


def get_db():
    return getattr(router, "db", None) or globals().get("db") or get_database_manager()


class ExperimentAnalysisRequest(BaseModel):
    user_id: Optional[str] = None
    type: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    height: Optional[float] = None
    mass: Optional[float] = None
    gravity: Optional[float] = 9.81
    length: Optional[float] = None
    angle_deg: Optional[float] = None
    damping: Optional[float] = 0.0
    mass_a: Optional[float] = None
    mass_b: Optional[float] = None
    vel_a: Optional[float] = None
    vel_b: Optional[float] = None
    collision_type: Optional[str] = "Elastic"


@router.post("/analyze/{exp_type}")
def analyze_experiment(exp_type: str, data: ExperimentAnalysisRequest):
    """
    Analyzes physics kinematics simulations (e.g. free-fall, pendulum, collision).
    Returns calculated trajectory and series data.
    """
    norm_type = exp_type.lower()
    if norm_type in ["free-fall", "freefall"]:
        height = data.height if data.height is not None else 50.0
        mass = data.mass if data.mass is not None else 1.0
        gravity = data.gravity if data.gravity is not None else 9.81
        return PhysicsEngine.solve_free_fall(height=height, mass=mass, gravity=gravity)
    elif norm_type == "pendulum":
        length = data.length if data.length is not None else 2.5
        angle = data.angle_deg if data.angle_deg is not None else 45.0
        mass = data.mass if data.mass is not None else 1.0
        gravity = data.gravity if data.gravity is not None else 9.81
        damping = data.damping if data.damping is not None else 0.0
        return PhysicsEngine.solve_pendulum(
            length=length, angle_deg=angle, mass=mass, gravity=gravity, damping=damping
        )
    elif norm_type == "collision":
        mass_a = data.mass_a if data.mass_a is not None else 1.0
        mass_b = data.mass_b if data.mass_b is not None else 1.0
        vel_a = data.vel_a if data.vel_a is not None else 1.0
        vel_b = data.vel_b if data.vel_b is not None else -1.0
        col_type = data.collision_type or "Elastic"
        return PhysicsEngine.solve_collision(
            mass_a=mass_a, mass_b=mass_b, vel_a=vel_a, vel_b=vel_b, collision_type=col_type
        )

    return {"status": "analyzed", "type": exp_type, "parameters": data.model_dump()}


@router.post("/save")
@limiter.limit("30/minute")
def save_experiment(
    request: Request,
    data: ExperimentData,
    current_user: dict = Depends(get_current_user),
):
    """
    Commits experiment kinematics to database.
    Obtains the canonical user ID from the verified identity.
    Never trusts client-supplied user_id: rejects mismatches with 403 Forbidden.
    In production mode: reports a controlled 503 failure if persistence fails,
    never claiming that the record was saved when it was not durably committed.
    """
    canonical_uid = str(current_user["id"])

    # Reject client-supplied spoofed user_id
    if data.user_id and str(data.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot save an experiment on behalf of another user.",
        )

    active_db = get_db()
    try:
        saved_record = active_db.save_experiment(data.model_dump(), user_id=canonical_uid)
        return {"status": "saved", "experiment": saved_record}
    except DatabasePersistenceError as pe:
        logger.error(f"Durable save failed for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: Experiment could not be durably saved.",
        )


@router.get("/history")
def get_history(
    user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
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

    active_db = get_db()
    try:
        user_experiments = active_db.get_experiments(user_id=canonical_uid)
        return {"history": user_experiments}
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to query experiment history: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.get("/experiment/{experiment_id}")
def get_experiment(
    experiment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Fetches a specific experiment by ID.
    Enforces authorization: 403 Forbidden if the resource belongs to another user.
    """
    canonical_uid = str(current_user["id"])
    active_db = get_db()
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
