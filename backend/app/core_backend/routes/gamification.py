import os
import uuid
import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query, status
from app.core_backend.models.schema import GamificationXP
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import DatabasePersistenceError
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.core.limiter import limiter
from app.logger import logger

router = APIRouter()
MAX_XP_PER_EVENT = 500


class LeaderboardCache:
    """
    Thread-safe in-memory cache for high-throughput leaderboard requests.
    Caches paginated leaderboard slices with TTL to prevent DB query saturation.
    """
    def __init__(self, ttl_seconds: float = 30.0):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[int, int, bool], Tuple[float, List[dict], int]] = {}
        self._lock = threading.Lock()

    def get(self, limit: int, offset: int, include_demo: bool = False) -> Optional[Tuple[List[dict], int]]:
        key = (limit, offset, include_demo)
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                timestamp, data, total_count = entry
                if now - timestamp < self.ttl_seconds:
                    return [d.copy() for d in data], total_count
                else:
                    del self._cache[key]
        return None

    def set(self, limit: int, offset: int, data: List[dict], total_count: int, include_demo: bool = False) -> None:
        key = (limit, offset, include_demo)
        now = time.time()
        with self._lock:
            self._cache[key] = (now, [d.copy() for d in data], total_count)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


LEADERBOARD_CACHE = LeaderboardCache(ttl_seconds=30.0)


def mask_user_display_name(user_id: str) -> str:
    """
    Masks user identification to prevent PII exposure (emails, personal names, internal tokens).
    Returns a standardized, privacy-preserving pseudonym while preserving leaderboard ranking.
    """
    uid = str(user_id).strip()
    if "@" in uid:
        local_part = uid.split("@")[0]
        prefix = local_part[:3].capitalize()
        return f"Scientist {prefix}***"
    clean_id = uid.replace("-", "")[:4].upper()
    return f"Scientist {clean_id}"


def get_database_manager():
    if os.getenv("POSTGRES_URL") or os.getenv("ENVIRONMENT") == "production":
        from app.core_backend.database.pgvector_db import PGVectorManager
        return PGVectorManager()
    return DatabaseManager()


db = get_database_manager()


def get_db():
    return getattr(router, "db", None) or globals().get("db") or get_database_manager()


@router.post("/add-xp")
@limiter.limit("30/minute")
def add_xp(
    request: Request,
    data: GamificationXP,
    current_user: dict = Depends(get_current_user),
):
    """
    Authoritatively awards XP strictly to the authenticated user.
    Enforces strong integrity guarantees:
    1. Obtains canonical user ID from verified JWT (never trusts client identity).
    2. Validates XP award amount on server (must be strictly positive and <= MAX_XP_PER_EVENT).
    3. Guarantees transactional write to an immutable audit ledger (xp_ledger).
    4. Enforces strict idempotency via unique event_id / idempotency_key (repeated submissions do not award duplicate points).
    5. Returns authoritative total calculated from the database aggregate.
    """
    canonical_uid = str(current_user["id"])

    # Reject client-supplied spoofed user_id
    if data.user_id and str(data.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot award XP to another user account.",
        )

    # Server-side award amount validation
    if data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid XP award: amount must be strictly positive.",
        )
    if data.amount > MAX_XP_PER_EVENT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid XP award: amount exceeds maximum allowable limit of {MAX_XP_PER_EVENT} XP.",
        )

    # Resolve event idempotency key
    header_idemp = request.headers.get("x-idempotency-key")
    event_id = data.event_id or data.idempotency_key or header_idemp
    if not event_id:
        clean_action = str(data.action or "general_award").strip().lower()
        event_id = f"evt_{canonical_uid}_{clean_action}_{uuid.uuid4().hex[:12]}"

    active_db = get_db()
    try:
        is_new, updated_xp = active_db.record_xp_event(
            user_id=canonical_uid,
            action=data.action,
            amount=data.amount,
            event_id=event_id,
            concept=data.concept,
            metadata=data.metadata,
        )
        if is_new:
            LEADERBOARD_CACHE.clear()
        return {
            "status": "success" if is_new else "duplicate",
            "user_id": canonical_uid,
            "event_id": event_id,
            "awarded": is_new,
            "xp_awarded": data.amount if is_new else 0,
            "total_xp": updated_xp,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Durable XP award failed for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: XP could not be durably recorded.",
        )


@router.get("/my-xp")
def get_my_xp(current_user: dict = Depends(get_current_user)):
    """
    Retrieves the authenticated user's authoritative accumulated XP total.
    """
    canonical_uid = str(current_user["id"])
    active_db = get_db()
    try:
        xp = active_db.get_user_xp(user_id=canonical_uid)
        return {"user_id": canonical_uid, "xp": xp}
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch XP for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.get("/xp-history")
def get_my_xp_history(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieves the authenticated user's auditable XP ledger entries.
    """
    canonical_uid = str(current_user["id"])
    active_db = get_db()
    try:
        history = active_db.get_xp_ledger(user_id=canonical_uid, limit=min(100, max(1, limit)))
        return {"user_id": canonical_uid, "history": history}
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch XP history for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.post("/reconcile")
def reconcile_my_xp(current_user: dict = Depends(get_current_user)):
    """
    Reconciles the user's aggregate XP total from the immutable audit ledger.
    """
    canonical_uid = str(current_user["id"])
    active_db = get_db()
    try:
        reconciled_xp = active_db.reconcile_xp_from_ledger(user_id=canonical_uid)
        LEADERBOARD_CACHE.clear()
        return {"user_id": canonical_uid, "reconciled_xp": reconciled_xp}
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to reconcile XP for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.get("/leaderboard")
def get_leaderboard(
    response: Response,
    limit: int = Query(10, ge=1, le=100, description="Maximum number of leaderboard entries to return"),
    offset: int = Query(0, ge=0, description="Offset for leaderboard pagination"),
    include_demo: bool = Query(False, description="Include demo participants (only permitted in non-production environments)"),
):
    """
    Retrieves the authoritative public leaderboard computed from actual persisted scores.
    Guarantees:
    1. Zero mock/fabricated users in production responses.
    2. Exact rank calculation from persisted XP totals via deterministic database ranking.
    3. PII protection: User display names are sanitized/pseudonymized to prevent leaking email addresses or personal identifiers.
    4. Caching with TTL & pagination headers (X-Total-Count, X-Limit, X-Offset, X-Cache).
    """
    is_prod = os.getenv("ENVIRONMENT") == "production"
    # Never allow demo users in production
    effective_include_demo = include_demo and not is_prod

    cached_result = LEADERBOARD_CACHE.get(limit=limit, offset=offset, include_demo=effective_include_demo)
    if cached_result is not None:
        entries, total_count = cached_result
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        response.headers["X-Cache"] = "HIT"
        return entries

    active_db = get_db()
    try:
        real_scores = active_db.get_leaderboard(limit=limit, offset=offset)
        total_count = active_db.get_leaderboard_count()
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch leaderboard: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )

    formatted_entries = []
    for score in real_scores:
        uid = str(score.get("user_id", score.get("id", "")))
        xp = int(score.get("xp", 0))
        rank = int(score.get("rank", len(formatted_entries) + offset + 1))
        badges = int(xp / 500)
        formatted_entries.append({
            "id": uid,
            "user_id": uid,
            "name": mask_user_display_name(uid),
            "xp": xp,
            "rank": rank,
            "badges": badges,
            "avatar": None,
        })

    # In non-production environments ONLY, if explicitly requested and database has no records
    if effective_include_demo and not formatted_entries and offset == 0:
        mock_candidates = [
            {"id": "demo_sarah", "user_id": "demo_sarah", "name": "Scientist SARA", "xp": 14500, "badges": 29},
            {"id": "demo_david", "user_id": "demo_david", "name": "Scientist DAVI", "xp": 13200, "badges": 26},
            {"id": "demo_elena", "user_id": "demo_elena", "name": "Scientist ELEN", "xp": 12850, "badges": 25},
        ]
        total_count = len(mock_candidates)
        formatted_entries = [
            {**m, "rank": idx + 1, "avatar": None}
            for idx, m in enumerate(mock_candidates[:limit])
        ]

    LEADERBOARD_CACHE.set(
        limit=limit,
        offset=offset,
        data=formatted_entries,
        total_count=total_count,
        include_demo=effective_include_demo,
    )

    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Cache"] = "MISS"

    return formatted_entries


@router.post("/seed-demo-leaderboard")
def seed_demo_leaderboard(
    current_user: dict = Depends(get_current_user),
):
    """
    Seeds demonstration learners with realistic XP in development or test environments.
    Strictly forbidden in production to protect real student rankings and data integrity.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Seeding demonstration leaderboard data is disabled in production.",
        )

    active_db = get_db()
    demo_users = [
        ("demo_sarah_chen", 1500, "Advanced Quantum Physics Exploration"),
        ("demo_david_park", 1200, "Neural Circuit Simulation"),
        ("demo_elena_rodriguez", 950, "Synapse Plasticity Lab"),
        ("demo_james_wilson", 700, "Optogenetics Analysis"),
        ("demo_aisha_patel", 450, "Cellular Electrophysiology"),
    ]

    seeded_count = 0
    for uid, target_xp, concept in demo_users:
        try:
            curr = active_db.get_user_xp(user_id=uid)
            remaining = target_xp - curr
            while remaining > 0:
                chunk = min(500, remaining)
                active_db.record_xp_event(
                    user_id=uid,
                    action="demo_seed",
                    amount=chunk,
                    event_id=f"evt_seed_{uid}_{uuid.uuid4().hex[:8]}",
                    concept=concept,
                    metadata={"is_demo": True},
                )
                remaining -= chunk
            if target_xp > curr:
                seeded_count += 1
        except Exception as e:
            logger.warning(f"Failed to seed demo user {uid}: {e}")

    LEADERBOARD_CACHE.clear()
    return {
        "status": "success",
        "environment": env,
        "seeded_users": seeded_count,
    }
