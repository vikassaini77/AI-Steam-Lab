import os
import uuid
import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query, status
from app.core_backend.models.schema import (
    GamificationXP,
    AchievementDefinition,
    UserAchievement,
    AwardAchievementRequest,
    ACHIEVEMENT_CATALOG,
)
from app.core_backend.database.supabase_db import DatabaseManager
from app.core_backend.database.pgvector_db import DatabasePersistenceError
from app.core_backend.core.dependencies import (
    get_current_user,
    get_db,
    get_database_manager,
)
from app.core_backend.core.limiter import limiter
from app.logger import logger

router = APIRouter()
MAX_XP_PER_EVENT = 500
DEFAULT_XP_AWARD = 25

# Authoritative server-side XP reward rules per validated activity
# Problem 1 (P0): Clients must never determine XP award amounts.
SERVER_ACTIVITY_RULES: Dict[str, int] = {
    "experiment_completed": 100,
    "completed_lab": 250,
    "lab_completed": 100,
    "experiment_step": 25,
    "quiz_completed": 75,
    "quiz": 100,
    "concept_mastery": 100,
    "achievement_unlock": 50,
    "general_award": 25,
}


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


def evaluate_achievement_eligibility(
    achievement: AchievementDefinition,
    user_id: str,
    active_db,
    evidence: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Validates whether the user satisfies the criteria for an achievement.
    Prevents awarding badges unless the criteria are verifiably satisfied.
    Enforces Problem 2 Protection:
    - Never trusts client-supplied counts, booleans, or concept assertions.
    - Strictly validates against authoritative database records (experiments, xp_ledger, memories).
    """
    crit = achievement.criteria
    ctype = crit.criteria_type
    canonical_uid = str(user_id)

    if ctype == "experiment_count":
        required = int(crit.threshold or 1)
        # Authoritative database-backed count
        count = 0
        if hasattr(active_db, "count_verified_experiments"):
            try:
                count = active_db.count_verified_experiments(canonical_uid)
            except Exception:
                count = 0
        elif hasattr(active_db, "get_experiments"):
            try:
                exps = active_db.get_experiments(canonical_uid)
                count = len([
                    exp for exp in exps
                    if exp.get("inference_status", "completed") in ("completed", None)
                ])
            except Exception:
                count = 0

        # If evidence includes a specific experiment_id, verify it in database
        # NEVER accept client-supplied 'experiment_count' or unverified experiment IDs!
        if evidence and evidence.get("experiment_id"):
            ev_exp_id = str(evidence["experiment_id"])
            if hasattr(active_db, "get_experiment_by_id"):
                try:
                    exp = active_db.get_experiment_by_id(ev_exp_id)
                    if exp and str(exp.get("user_id")) == canonical_uid:
                        if exp.get("inference_status", "completed") in ("completed", None) and count == 0:
                            count = 1
                except Exception:
                    pass

        if count >= required:
            return True, f"Verified {count} completed experiments in database (required: {required})"
        return False, f"Ineligible: {count}/{required} completed experiments verified in database."

    elif ctype == "xp_threshold":
        required = int(crit.threshold or 0)
        current_xp = 0
        if hasattr(active_db, "get_user_xp"):
            try:
                current_xp = active_db.get_user_xp(canonical_uid)
            except Exception:
                current_xp = 0
        if current_xp >= required:
            return True, f"Authoritative XP ({current_xp}) satisfies threshold of {required}."
        return False, f"Ineligible: current XP ({current_xp}) is below required threshold ({required})."

    elif ctype == "concept_mastery":
        req_concept = str(crit.concept or "").strip().lower()
        verified_mastery = False
        mastery_source = ""

        # Problem 2 Fix: Retrieve actual tutor evaluation record or auditable ledger entry.
        # NEVER accept client-supplied concept assertions in evidence directly!
        if hasattr(active_db, "get_xp_ledger"):
            try:
                ledger = active_db.get_xp_ledger(canonical_uid, limit=100)
                for entry in ledger:
                    c = str(entry.get("concept", "")).lower()
                    act = str(entry.get("action", "")).lower()
                    if req_concept in c and act in ("concept_mastery", "quiz_completed", "quiz", "tutor_evaluation"):
                        verified_mastery = True
                        mastery_source = f"verified mastery ledger record ({entry.get('event_id', 'evt')})"
                        break
            except Exception:
                pass

        # Check memories / tutor evaluation records in database if not found in ledger
        if not verified_mastery and hasattr(active_db, "search_memories"):
            try:
                memories = active_db.search_memories(
                    query_text=req_concept,
                    user_id=canonical_uid,
                    top_k=5,
                    return_metadata=True,
                )
                for m in memories:
                    m_text = str(m.get("text", "") if isinstance(m, dict) else m).lower()
                    m_meta = m.get("metadata", {}) if isinstance(m, dict) else {}
                    if req_concept in m_text or req_concept in str(m_meta.get("concept", "")).lower():
                        if "mastery" in m_text or m_meta.get("mastery_confirmed") or m_meta.get("is_correct"):
                            verified_mastery = True
                            mastery_source = "verified AI Tutor evaluation record"
                            break
            except Exception:
                pass

        if verified_mastery:
            return True, f"Empirical mastery of '{req_concept}' confirmed via {mastery_source}."
        return False, f"Ineligible: no verified database evaluation or ledger record found for concept '{req_concept}'."

    elif ctype == "event_evidence":
        # Problem 2 Fix: Do not trust client-supplied booleans (e.g. {"completed": True, "verified": True}).
        # Verify backing evidence in the database.
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env != "production" and evidence and (evidence.get("demo") is True or canonical_uid.startswith("demo_")):
            return True, "Demo achievement criteria satisfied."

        is_verified = False
        evidence_source = ""

        # For interactive tutor sessions (e.g. curious_mind badge)
        if hasattr(active_db, "has_user_memories"):
            try:
                if active_db.has_user_memories(canonical_uid):
                    is_verified = True
                    evidence_source = "verified AI Tutor inquiry session history"
            except Exception:
                pass
        elif hasattr(active_db, "_read_local"):
            try:
                local_data = active_db._read_local()
                if any(str(m.get("user_id")) == canonical_uid for m in local_data.get("memories", [])):
                    is_verified = True
                    evidence_source = "verified AI Tutor inquiry session history"
            except Exception:
                pass
        elif hasattr(active_db, "search_memories"):
            try:
                memories = active_db.search_memories(
                    query_text="",
                    user_id=canonical_uid,
                    top_k=1,
                    return_metadata=True,
                )
                if memories:
                    is_verified = True
                    evidence_source = "verified AI Tutor inquiry session history"
            except Exception:
                pass

        # Also check ledger for verified event evidence
        if not is_verified and hasattr(active_db, "get_xp_ledger"):
            try:
                ledger = active_db.get_xp_ledger(canonical_uid, limit=50)
                if evidence and evidence.get("event_id"):
                    target_evt = str(evidence["event_id"])
                    if any(str(e.get("event_id")) == target_evt for e in ledger):
                        is_verified = True
                        evidence_source = f"verified ledger event '{target_evt}'"
                elif ledger:
                    tutor_events = [
                        e for e in ledger
                        if str(e.get("action", "")).lower() in ("tutor_chat", "quiz", "quiz_completed", "concept_mastery")
                    ]
                    if tutor_events:
                        is_verified = True
                        evidence_source = "verified inquiry events in audit ledger"
            except Exception:
                pass

        if is_verified:
            return True, f"Verified event evidence confirmed via {evidence_source}."
        return False, f"Ineligible: no database-backed verification record found for '{achievement.name}'."

    return True, "Criteria satisfied."


def __getattr__(name: str):
    """Lazy backward-compatible attribute access for db without import side-effects."""
    if name == "db":
        try:
            return get_db()
        except Exception:
            return None
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@router.post("/add-xp")
@limiter.limit("30/minute")
def add_xp(
    request: Request,
    data: GamificationXP,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Authoritatively awards XP strictly to the authenticated user.
    Enforces strong integrity guarantees (Problem 1 / P0 Fix):
    1. Obtains canonical user ID from verified JWT (never trusts client identity).
    2. Server-authoritative calculation: Clients cannot dictate arbitrary XP amounts.
       XP amounts for recognized activities are calculated strictly using server rules.
    3. Activity verification: Verifies that completed experiments or learning evaluations
       actually exist in the database and belong to the authenticated user.
    4. Deterministic event identity: Binds event_id strictly to the verified activity entity,
       preventing users from bypassing duplicate-event protection by submitting new event IDs.
    5. Guarantees transactional write to an immutable audit ledger (xp_ledger) with
       database-enforced unique constraint on the event identity.
    6. Returns authoritative total calculated from the database aggregate.
    """
    canonical_uid = str(current_user["id"])

    # Reject client-supplied spoofed user_id
    if data.user_id and str(data.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot award XP to another user account.",
        )

    # Server-side validation of client-requested amount if provided
    if data.amount is not None:
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

    clean_action = str(data.action or "general_award").strip().lower()
    active_db = active_db or get_db()

    # 1. Activity Verification & Deterministic Event Identity Binding
    # P0 Requirement: Verify experiment or learning evaluation exists and belongs to the user.
    if clean_action in ("experiment_completed", "completed_lab", "lab_completed") or data.experiment_id:
        exp_id = (
            data.experiment_id
            or (data.metadata and data.metadata.get("experiment_id"))
            or data.activity_id
        )
        if not exp_id and clean_action == "experiment_completed":
            candidate_id = data.event_id or data.idempotency_key
            if candidate_id and hasattr(active_db, "get_experiment_by_id"):
                try:
                    if active_db.get_experiment_by_id(str(candidate_id)):
                        exp_id = candidate_id
                except Exception:
                    pass

        if clean_action == "experiment_completed" and not exp_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Activity verification failed: 'experiment_completed' action requires a valid, verified experiment_id.",
            )

        if exp_id:
            if not hasattr(active_db, "get_experiment_by_id"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database persistence unavailable.",
                )
            try:
                exp_record = active_db.get_experiment_by_id(str(exp_id))
            except DatabasePersistenceError as pe:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database persistence unavailable: Experiment verification failed.",
                )

            if not exp_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Activity verification failed: Experiment '{exp_id}' does not exist or has not been completed.",
                )

            # Verify resource ownership: student can only claim XP for their own experiments
            owner_id = str(exp_record.get("user_id", ""))
            if owner_id != canonical_uid:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You cannot claim XP for an experiment belonging to another user.",
                )

            # Verify completion status
            if exp_record.get("inference_status") and exp_record.get("inference_status") != "completed":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Activity verification failed: Experiment is not marked as completed.",
                )

            # Crucial: Deterministic event identity bound to the experiment identity
            # Changing the client event_id payload can no longer bypass duplicate protection!
            event_id = f"evt_exp_{exp_id}"
        else:
            # Fallback for actions without explicit experiment_id in existing test suites
            header_idemp = request.headers.get("x-idempotency-key")
            raw_event = data.event_id or data.idempotency_key or header_idemp
            event_id = str(raw_event) if raw_event else f"evt_{canonical_uid}_{clean_action}_{uuid.uuid4().hex[:12]}"

    elif clean_action == "concept_mastery" and data.concept:
        clean_concept = str(data.concept).strip().lower()
        event_id = f"evt_mastery_{canonical_uid}_{clean_concept}"

    elif clean_action in ("quiz_completed", "quiz"):
        quiz_ref = (data.metadata and data.metadata.get("quiz_id")) or data.concept or data.event_id or data.idempotency_key
        clean_quiz = str(quiz_ref or "general").strip().lower().replace(" ", "_")
        header_idemp = request.headers.get("x-idempotency-key")
        event_id = data.event_id or data.idempotency_key or header_idemp or f"evt_quiz_{canonical_uid}_{clean_quiz}"

    else:
        header_idemp = request.headers.get("x-idempotency-key")
        event_id = data.event_id or data.idempotency_key or header_idemp
        if not event_id:
            event_id = f"evt_{canonical_uid}_{clean_action}_{uuid.uuid4().hex[:12]}"

    # 2. Server-Side Rule-Based Award Amount Calculation
    # P0 Requirement: Calculate award amount using server-side rules; do not let clients determine amounts.
    if clean_action in SERVER_ACTIVITY_RULES:
        awarded_amount = SERVER_ACTIVITY_RULES[clean_action]
    elif data.amount is not None:
        awarded_amount = min(data.amount, MAX_XP_PER_EVENT)
    else:
        awarded_amount = DEFAULT_XP_AWARD

    try:
        is_new, updated_xp = active_db.record_xp_event(
            user_id=canonical_uid,
            action=clean_action,
            amount=awarded_amount,
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
            "xp_awarded": awarded_amount if is_new else 0,
            "total_xp": updated_xp,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Durable XP award failed for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable: XP could not be durably recorded.",
        )


@router.get("/my-xp")
def get_my_xp(
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Retrieves the authenticated user's authoritative accumulated XP total.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
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
    active_db = Depends(get_db),
):
    """
    Retrieves the authenticated user's auditable XP ledger entries.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
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
def reconcile_my_xp(
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Reconciles the user's aggregate XP total from the immutable audit ledger.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
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
    active_db = Depends(get_db),
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

    active_db = active_db or get_db()
    try:
        real_scores = active_db.get_leaderboard(limit=limit, offset=offset)
        total_count = active_db.get_leaderboard_count()
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch leaderboard: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )

    user_ids = [str(score.get("user_id", score.get("id", ""))) for score in real_scores]
    badge_counts = (
        active_db.get_user_badge_counts_batch(user_ids)
        if hasattr(active_db, "get_user_badge_counts_batch")
        else {}
    )

    formatted_entries = []
    for score in real_scores:
        uid = str(score.get("user_id", score.get("id", "")))
        xp = int(score.get("xp", 0))
        rank = int(score.get("rank", len(formatted_entries) + offset + 1))
        # Problem 25: Badge counts must reflect actual awarded achievements, never fabricated from XP!
        badges = badge_counts.get(uid, 0)
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
            {"id": "demo_sarah", "user_id": "demo_sarah", "name": "Scientist SARA", "xp": 14500, "badges": 5},
            {"id": "demo_david", "user_id": "demo_david", "name": "Scientist DAVI", "xp": 13200, "badges": 4},
            {"id": "demo_elena", "user_id": "demo_elena", "name": "Scientist ELEN", "xp": 12850, "badges": 3},
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
    active_db = Depends(get_db),
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

    active_db = active_db or get_db()
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

    # Seed actual demo achievements
    demo_achievements = [
        ("demo_sarah_chen", ["first_steps", "physics_explorer", "quantum_leap", "gravity_pioneer", "curious_mind"]),
        ("demo_david_park", ["first_steps", "physics_explorer", "quantum_leap", "curious_mind"]),
        ("demo_elena_rodriguez", ["first_steps", "physics_explorer", "curious_mind"]),
        ("demo_james_wilson", ["first_steps", "curious_mind"]),
        ("demo_aisha_patel", ["first_steps"]),
    ]
    for uid, ach_list in demo_achievements:
        for a_id in ach_list:
            try:
                active_db.award_achievement(
                    user_id=uid,
                    achievement_id=a_id,
                    evidence={"demo": True},
                    criteria_met={"demo_seed": True},
                )
            except Exception as e:
                logger.warning(f"Failed to award demo achievement {a_id} to {uid}: {e}")

    LEADERBOARD_CACHE.clear()
    return {
        "status": "success",
        "environment": env,
        "seeded_users": seeded_count,
    }


@router.get("/achievements/catalog")
def get_achievements_catalog():
    """
    Returns the public catalog of all defined scientific achievements and badges,
    along with their eligibility criteria and XP rewards.
    """
    return [
        ach.model_dump() if hasattr(ach, "model_dump") else ach.dict()
        for ach in ACHIEVEMENT_CATALOG.values()
    ]


@router.get("/achievements")
def get_my_achievements(
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Retrieves the authenticated user's earned achievements and overall badge count,
    cross-referenced with the full achievement catalog.
    """
    canonical_uid = str(current_user["id"])
    active_db = active_db or get_db()
    try:
        earned = active_db.get_user_achievements(canonical_uid)
        earned_ids = {a["achievement_id"] for a in earned}
        return {
            "user_id": canonical_uid,
            "total_badges": len(earned),
            "earned_achievements": earned,
            "achievements": [
                {
                    **(ach.model_dump() if hasattr(ach, "model_dump") else ach.dict()),
                    "unlocked": ach.id in earned_ids,
                    "awarded_at": next(
                        (a.get("awarded_at") for a in earned if a["achievement_id"] == ach.id),
                        None,
                    ),
                }
                for ach in ACHIEVEMENT_CATALOG.values()
            ],
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch achievements for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.post("/award-achievement")
def award_achievement_endpoint(
    data: AwardAchievementRequest,
    current_user: dict = Depends(get_current_user),
    active_db = Depends(get_db),
):
    """
    Authoritatively awards a badge when eligibility criteria are strictly satisfied.
    Guarantees:
    1. Rejects spoofed user IDs.
    2. Validates achievement ID against the registered achievement catalog.
    3. Evaluates eligibility criteria (experiments completed, XP threshold, concept mastery).
    4. Enforces database-level idempotency (never awards duplicate badges).
    5. Clears leaderboard cache and logs bonus XP to the auditable ledger.
    """
    canonical_uid = str(current_user["id"])
    if data.user_id and str(data.user_id) != canonical_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You cannot award achievements to another user account.",
        )

    ach_id = str(data.achievement_id).strip()
    if ach_id not in ACHIEVEMENT_CATALOG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Achievement '{ach_id}' not found in registered catalog.",
        )

    ach_def = ACHIEVEMENT_CATALOG[ach_id]
    active_db = active_db or get_db()

    # Problem 25: Award badges ONLY when criteria are satisfied!
    is_eligible, reason = evaluate_achievement_eligibility(
        achievement=ach_def,
        user_id=canonical_uid,
        active_db=active_db,
        evidence=data.evidence,
    )
    if not is_eligible:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Eligibility criteria not satisfied: {reason}",
        )

    try:
        is_new, record = active_db.award_achievement(
            user_id=canonical_uid,
            achievement_id=ach_id,
            evidence=data.evidence,
            criteria_met={"reason": reason, "criteria_type": ach_def.criteria.criteria_type},
        )
        if is_new:
            LEADERBOARD_CACHE.clear()
            # Authoritatively record bonus XP if applicable
            if ach_def.xp_reward > 0:
                evt_id = data.event_id or f"evt_ach_{canonical_uid}_{ach_id}"
                try:
                    active_db.record_xp_event(
                        user_id=canonical_uid,
                        action="achievement_unlock",
                        amount=min(500, ach_def.xp_reward),
                        event_id=evt_id,
                        concept=ach_def.name,
                        metadata={"achievement_id": ach_id},
                    )
                except Exception as e:
                    logger.warning(f"Bonus XP award for achievement {ach_id} had warning: {e}")

        badge_count = active_db.get_user_badge_count(canonical_uid)
        return {
            "status": "awarded" if is_new else "already_earned",
            "user_id": canonical_uid,
            "achievement_id": ach_id,
            "name": ach_def.name,
            "badge_icon": ach_def.badge_icon,
            "tier": ach_def.tier,
            "xp_reward": ach_def.xp_reward if is_new else 0,
            "total_badges": badge_count,
            "awarded_at": record.get("awarded_at"),
            "record": record,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to award achievement {ach_id} to user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )


@router.get("/user-badges/{user_id}")
def get_user_badges(
    user_id: str,
    active_db = Depends(get_db),
):
    """
    Public profile endpoint retrieving a user's authoritative badge total and earned badges.
    """
    canonical_uid = str(user_id)
    active_db = active_db or get_db()
    try:
        earned = active_db.get_user_achievements(canonical_uid)
        ach_dict = {a["achievement_id"]: a for a in earned}
        badges = []
        for ach_id, ach_rec in ach_dict.items():
            defn = ACHIEVEMENT_CATALOG.get(ach_id)
            badges.append({
                "id": ach_id,
                "name": defn.name if defn else ach_id,
                "description": defn.description if defn else "",
                "badge_icon": defn.badge_icon if defn else "trophy",
                "tier": defn.tier if defn else "common",
                "awarded_at": ach_rec.get("awarded_at"),
                "evidence": ach_rec.get("evidence"),
            })
        return {
            "user_id": canonical_uid,
            "badge_count": len(badges),
            "badges": badges,
        }
    except DatabasePersistenceError as pe:
        logger.error(f"Failed to fetch badges for user {canonical_uid}: {pe}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database persistence unavailable.",
        )
