import os
import json
import uuid
import time
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple, Union
import numpy as np
from app.core_backend.database.hybrid_retrieval import (
    execute_in_memory_hybrid_search,
    normalize_query_text,
)

db_lock = threading.Lock()


class DatabaseManager:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.local_db_path = os.path.join(os.path.dirname(__file__), "local_stem_db.json")
        self.last_retrieval_metadata: List[Dict[str, Any]] = []
        self._init_local_db()

    def _init_local_db(self):
        if not os.path.exists(self.local_db_path):
            with open(self.local_db_path, "w") as f:
                json.dump({"experiments": [], "memories": [], "xp": {}}, f, indent=2)

    def _read_local(self) -> dict:
        try:
            with open(self.local_db_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"experiments": [], "memories": [], "xp": {}}

    def _write_local(self, data: dict):
        with open(self.local_db_path, "w") as f:
            json.dump(data, f, indent=2)

    def save_experiment(
        self,
        data: Optional[dict] = None,
        user_id: Optional[str] = None,
        experiment_type: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """
        Saves an experiment record stamped with the canonical user_id.
        Guarantees record ownership.
        Supports both (data, user_id) and (user_id=..., experiment_type=..., data=...) signatures.
        """
        payload = dict(data or kwargs.get("data") or {})
        uid = str(user_id or kwargs.get("user_id") or payload.get("user_id", ""))
        payload["user_id"] = uid
        exp_type = experiment_type or kwargs.get("experiment_type") or payload.get("experiment_type")
        if exp_type:
            payload["experiment_type"] = exp_type
        if "id" not in payload or not payload["id"]:
            payload["id"] = f"exp_{uuid.uuid4().hex[:12]}"
        if "timestamp" not in payload:
            payload["timestamp"] = int(time.time())

        with db_lock:
            db = self._read_local()
            # If experiment already exists, update it, else append
            existing_idx = next(
                (i for i, exp in enumerate(db["experiments"]) if exp.get("id") == payload["id"]),
                None,
            )
            if existing_idx is not None:
                db["experiments"][existing_idx] = payload
            else:
                db["experiments"].append(payload)
            self._write_local(db)

        return payload

    def get_experiments(self, user_id: str) -> List[dict]:
        """
        Retrieves experiments filtered strictly by user_id.
        User isolation: never returns records belonging to other users.
        """
        if not user_id:
            return []

        canonical_uid = str(user_id)
        with db_lock:
            db = self._read_local()
            return [
                exp for exp in db.get("experiments", [])
                if str(exp.get("user_id")) == canonical_uid
            ]

    def get_experiment_by_id(self, experiment_id: str) -> Optional[dict]:
        """
        Fetches an experiment record by ID without exposing it directly.
        Caller must enforce ownership check.
        """
        with db_lock:
            db = self._read_local()
            return next(
                (exp for exp in db.get("experiments", []) if str(exp.get("id")) == str(experiment_id)),
                None,
            )

    def record_xp_event(
        self,
        user_id: str,
        action: str,
        amount: int,
        event_id: Optional[str] = None,
        concept: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, int]:
        """
        Records an auditable XP award in the ledger and updates user_xp aggregate.
        Enforces idempotency and server-side amount validation.
        """
        canonical_uid = str(user_id)
        if amount <= 0:
            raise ValueError(f"XP amount must be positive, got {amount}")
        if amount > 1000:
            raise ValueError(f"XP amount exceeds maximum server limit (1000), got {amount}")

        clean_action = str(action or "general_award").strip().lower()
        evt_key = str(event_id) if event_id else f"evt_{canonical_uid}_{clean_action}_{uuid.uuid4().hex[:12]}"

        with db_lock:
            db = self._read_local()
            if "xp_ledger" not in db:
                db["xp_ledger"] = {}
            if "xp" not in db:
                db["xp"] = {}

            if evt_key in db["xp_ledger"]:
                return False, db["xp"].get(canonical_uid, 0)

            db["xp_ledger"][evt_key] = {
                "event_id": evt_key,
                "user_id": canonical_uid,
                "action": clean_action,
                "amount": amount,
                "concept": concept,
                "created_at": time.time(),
                "metadata": metadata or {},
            }
            if concept:
                if "mastery_records" not in db:
                    db["mastery_records"] = {}
                db["mastery_records"][evt_key] = {
                    "user_id": canonical_uid,
                    "concept": concept,
                    "amount": amount,
                    "timestamp": int(time.time()),
                }
            new_xp = db["xp"].get(canonical_uid, 0) + amount
            db["xp"][canonical_uid] = new_xp
            self._write_local(db)
            return True, new_xp

    def add_xp(
        self,
        user_id: str,
        amount: int,
        action: str = "general_award",
        event_id: Optional[str] = None,
        concept: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Increments XP for the specified user_id via an auditable transaction.
        Returns the updated authoritative total XP.
        """
        _, total_xp = self.record_xp_event(
            user_id=user_id,
            action=action,
            amount=amount,
            event_id=event_id,
            concept=concept,
            metadata=metadata,
        )
        return total_xp

    def award_mastery_xp(
        self,
        user_id: str,
        concept: str,
        amount: int = 100,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """
        Idempotently awards XP for verified concept mastery.
        Guarantees that retries or repeated triggers cannot award points twice.
        Returns (is_newly_awarded, total_xp).
        """
        canonical_uid = str(user_id)
        dedup_key = idempotency_key or f"{canonical_uid}:{concept.strip().lower()}"
        return self.record_xp_event(
            user_id=canonical_uid,
            action="concept_mastery",
            amount=amount,
            event_id=dedup_key,
            concept=concept,
        )

    def get_xp_ledger(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves the immutable audit trail of XP awards for a specific user.
        """
        canonical_uid = str(user_id)
        with db_lock:
            db = self._read_local()
            ledger = db.get("xp_ledger", {})
            user_entries = [
                entry for entry in ledger.values()
                if entry.get("user_id") == canonical_uid
            ]
            user_entries.sort(key=lambda x: x.get("created_at", 0), reverse=True)
            return user_entries[:limit]

    def reconcile_xp_from_ledger(self, user_id: str) -> int:
        """
        Calculates authoritative total XP from the immutable xp_ledger
        and reconciles user_xp aggregate.
        """
        canonical_uid = str(user_id)
        with db_lock:
            db = self._read_local()
            ledger = db.get("xp_ledger", {})
            total = sum(
                entry.get("amount", 0) for entry in ledger.values()
                if entry.get("user_id") == canonical_uid
            )
            if "xp" not in db:
                db["xp"] = {}
            db["xp"][canonical_uid] = total
            self._write_local(db)
            return total

    def get_user_xp(self, user_id: str) -> int:
        """
        Returns the total accumulated XP for the given user_id.
        """
        canonical_uid = str(user_id)
        with db_lock:
            db = self._read_local()
            return db.get("xp", {}).get(canonical_uid, 0)

    def get_leaderboard(self, limit: int = 10, offset: int = 0) -> List[dict]:
        """
        Returns ranked public leaderboard scores computed from persisted data.
        """
        with db_lock:
            db = self._read_local()
        xp_data = db.get("xp", {})
        positive_users = [(uid, xp) for uid, xp in xp_data.items() if xp > 0]
        sorted_users = sorted(positive_users, key=lambda item: (-item[1], str(item[0])))
        paged = sorted_users[offset : offset + limit]

        leaderboard = []
        for i, (uid, xp) in enumerate(paged):
            leaderboard.append({
                "id": uid,
                "user_id": uid,
                "rank": offset + i + 1,
                "xp": xp,
            })
        return leaderboard

    def get_leaderboard_count(self) -> int:
        with db_lock:
            db = self._read_local()
        xp_data = db.get("xp", {})
        return sum(1 for xp in xp_data.values() if xp > 0)

    def award_achievement(
        self,
        user_id: str,
        achievement_id: str,
        evidence: Optional[dict] = None,
        criteria_met: Optional[dict] = None,
    ) -> Tuple[bool, dict]:
        """
        Awards an achievement to user if not already earned.
        Enforces strict uniqueness per (user_id, achievement_id).
        Returns (is_new, record).
        """
        canonical_uid = str(user_id)
        ach_id = str(achievement_id)
        with db_lock:
            db = self._read_local()
            if "user_achievements" not in db:
                db["user_achievements"] = []

            for rec in db["user_achievements"]:
                if str(rec.get("user_id")) == canonical_uid and str(rec.get("achievement_id")) == ach_id:
                    return False, rec

            record = {
                "id": f"ach_{canonical_uid}_{ach_id}_{uuid.uuid4().hex[:8]}",
                "user_id": canonical_uid,
                "achievement_id": ach_id,
                "awarded_at": datetime.now(timezone.utc).isoformat(),
                "criteria_met": criteria_met or {},
                "evidence": evidence or {},
            }
            db["user_achievements"].append(record)
            self._write_local(db)
            return True, record

    def get_user_achievements(self, user_id: str) -> List[dict]:
        """
        Retrieves all achievements awarded to the user, ordered chronologically.
        """
        canonical_uid = str(user_id)
        with db_lock:
            db = self._read_local()
        achievements = db.get("user_achievements", [])
        user_achs = [a for a in achievements if str(a.get("user_id")) == canonical_uid]
        return sorted(user_achs, key=lambda x: str(x.get("awarded_at", "")))

    def get_user_badge_count(self, user_id: str) -> int:
        """
        Returns authoritative count of actual achievements earned by the user.
        """
        return len(self.get_user_achievements(user_id))

    def get_user_badge_counts_batch(self, user_ids: List[str]) -> Dict[str, int]:
        """
        Batch returns authoritative badge counts for a list of users.
        """
        with db_lock:
            db = self._read_local()
        achievements = db.get("user_achievements", [])
        counts: Dict[str, int] = {str(uid): 0 for uid in user_ids}
        for ach in achievements:
            uid = str(ach.get("user_id"))
            if uid in counts:
                counts[uid] += 1
        return counts

    def save_memory(self, session_id: str, text: str, embedding: list, user_id: Optional[str] = None) -> int:
        """
        Saves a conversational vector memory tagged with user_id for strict tenant isolation.
        Returns document ID.
        """
        canonical_uid = str(user_id) if user_id else None
        with db_lock:
            db = self._read_local()
            if "memories" not in db:
                db["memories"] = []
            doc_id = len(db["memories"]) + 1
            db["memories"].append({
                "id": doc_id,
                "user_id": canonical_uid,
                "session_id": session_id,
                "text": text,
                "embedding": embedding,
            })
            self._write_local(db)
            return doc_id

    def search_memories(
        self,
        query_embedding: Optional[list] = None,
        query_text: str = "",
        user_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = False,
        search_mode: str = "hybrid",
        include_expired: bool = False,
        embedding_model_version: Optional[str] = None,
    ) -> Union[List[str], List[Dict[str, Any]]]:
        """
        Hybrid search using RRF (Reciprocal Rank Fusion) combining semantic vector
        search with keyword/technical term matching and tenant ownership filtering.
        Supports search_mode: 'hybrid' | 'semantic' | 'keyword'.
        """
        with db_lock:
            db = self._read_local()
            memories = list(db.get("memories", []))

        results, metadata = execute_in_memory_hybrid_search(
            memories=memories,
            query_embedding=query_embedding,
            query_text=query_text,
            user_id=user_id,
            top_k=top_k,
            return_metadata=return_metadata,
            search_mode=search_mode,
            include_expired=include_expired,
            embedding_model_version=embedding_model_version,
        )
        self.last_retrieval_metadata = metadata
        return results

    def check_and_increment_daily_usage(self, user_id: str, limit: int = 100) -> tuple[bool, int]:
        """
        Tracks daily request counts per user.
        Enforces daily AI model request budgets.
        Returns (is_allowed, current_count).
        """
        today_key = time.strftime("%Y-%m-%d", time.gmtime())
        canonical_uid = str(user_id)

        with db_lock:
            db = self._read_local()
            if "daily_usage" not in db:
                db["daily_usage"] = {}
            user_usage = db["daily_usage"].setdefault(canonical_uid, {})
            current_count = user_usage.get(today_key, 0)

            if current_count >= limit:
                return False, current_count

            current_count += 1
            user_usage[today_key] = current_count
            self._write_local(db)
            return True, current_count
