"""
Memory Repository - Persistence Layer
Problem 45 & Problem 9: Service boundaries separation and strict tenant isolation.
Encapsulates conversation memory storage, hybrid vector retrieval queries,
tenant isolation enforcement, session history, and gamification mastery awards.
Decoupled from AI prompting and HTTP routing.
"""
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable

from app.logger import logger
from app.core_backend.database.pgvector_db import TenantIsolationError


@runtime_checkable
class MemoryRepositoryProtocol(Protocol):
    """Protocol defining the persistence layer contract for conversational memories."""

    def search_memories(
        self,
        query_embedding: Optional[List[float]],
        query_text: str,
        user_id: str,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = False,
    ) -> List[Any]:
        ...

    def save_memory(
        self,
        session_id: str,
        text: str,
        embedding: Optional[List[float]],
        user_id: str,
        experiment_id: Optional[str] = None,
        embedding_model_version: str = "text-embedding-004",
        retention_days: Optional[int] = None,
    ) -> Any:
        ...

    def list_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        ...

    def delete_memory(
        self,
        memory_id: int,
        user_id: str,
    ) -> bool:
        ...

    def delete_user_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        hard_delete: bool = True,
    ) -> int:
        ...

    def get_session_history(
        self,
        session_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        ...

    def validate_session_ownership(
        self,
        session_id: str,
        user_id: str,
    ) -> bool:
        ...

    def award_mastery_xp(
        self,
        user_id: str,
        concept: str,
        amount: int = 100,
    ) -> Tuple[bool, int]:
        ...


class MemoryRepository:
    """
    Production Memory Repository implementation backed by DatabaseManager / PGVectorManager.
    Strictly enforces tenant isolation across all memory interactions.
    """
    def __init__(self, db_manager: Any):
        self._db = db_manager

    @property
    def underlying_db(self) -> Any:
        return self._db

    def search_memories(
        self,
        query_embedding: Optional[List[float]],
        query_text: str,
        user_id: str,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = False,
        search_mode: str = "hybrid",
        include_expired: bool = False,
        embedding_model_version: Optional[str] = None,
    ) -> List[Any]:
        """Queries database for past conversational memories using vector and text search with strict tenant isolation."""
        kwargs = {
            "query_embedding": query_embedding,
            "query_text": query_text,
            "user_id": user_id,
            "top_k": top_k,
            "return_metadata": return_metadata,
        }
        if session_id is not None:
            kwargs["session_id"] = session_id
        if experiment_id is not None:
            kwargs["experiment_id"] = experiment_id
        if search_mode is not None:
            kwargs["search_mode"] = search_mode
        if include_expired:
            kwargs["include_expired"] = include_expired
        if embedding_model_version is not None:
            kwargs["embedding_model_version"] = embedding_model_version

        try:
            return self._db.search_memories(**kwargs)
        except TenantIsolationError:
            raise
        except TypeError:
            kwargs.pop("session_id", None)
            kwargs.pop("experiment_id", None)
            kwargs.pop("search_mode", None)
            kwargs.pop("include_expired", None)
            kwargs.pop("embedding_model_version", None)
            try:
                return self._db.search_memories(**kwargs)
            except TenantIsolationError:
                raise
            except Exception as e:
                logger.warning(f"MemoryRepository search_memories fallback failed ({type(e).__name__}): {e}")
                return []
        except Exception as e:
            logger.warning(f"MemoryRepository search_memories failed ({type(e).__name__}): {e}")
            return []

    def save_memory(
        self,
        session_id: str,
        text: str,
        embedding: Optional[List[float]],
        user_id: str,
        experiment_id: Optional[str] = None,
        embedding_model_version: str = "text-embedding-004",
        retention_days: Optional[int] = None,
    ) -> Any:
        """Persists conversational memory interaction with tenant ownership and session ownership validation."""
        kwargs = {
            "session_id": session_id,
            "text": text,
            "embedding": embedding,
            "user_id": user_id,
        }
        if experiment_id is not None:
            kwargs["experiment_id"] = experiment_id
        if embedding_model_version is not None:
            kwargs["embedding_model_version"] = embedding_model_version
        if retention_days is not None:
            kwargs["retention_days"] = retention_days

        try:
            return self._db.save_memory(**kwargs)
        except TypeError:
            kwargs.pop("experiment_id", None)
            kwargs.pop("embedding_model_version", None)
            kwargs.pop("retention_days", None)
            return self._db.save_memory(**kwargs)
        except Exception as e:
            logger.exception(f"MemoryRepository save_memory failed ({type(e).__name__}): {e}")
            raise

    def list_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Lists memories for authenticated user with optional session scoping and pagination."""
        if hasattr(self._db, "list_memories"):
            return self._db.list_memories(
                user_id=user_id,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
        return []

    def delete_memory(
        self,
        memory_id: int,
        user_id: str,
    ) -> bool:
        """Deletes a specific memory with ownership enforcement."""
        if hasattr(self._db, "delete_memory_by_id"):
            return self._db.delete_memory_by_id(memory_id=memory_id, user_id=user_id)
        return False

    def delete_user_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        hard_delete: bool = True,
    ) -> int:
        """Deletes all memories for user, optionally scoped to session_id."""
        if hasattr(self._db, "delete_user_memories"):
            return self._db.delete_user_memories(
                user_id=user_id,
                session_id=session_id,
                hard_delete=hard_delete,
            )
        return 0

    def get_session_history(
        self,
        session_id: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieves chronological turns for session_id belonging to user_id."""
        if hasattr(self._db, "get_session_history"):
            return self._db.get_session_history(
                session_id=session_id,
                user_id=user_id,
            )
        return []

    def validate_session_ownership(
        self,
        session_id: str,
        user_id: str,
    ) -> bool:
        """Validates that session_id belongs to user_id."""
        if hasattr(self._db, "validate_session_ownership"):
            return self._db.validate_session_ownership(
                session_id=session_id,
                user_id=user_id,
            )
        return True

    def award_mastery_xp(
        self,
        user_id: str,
        concept: str,
        amount: int = 100,
    ) -> Tuple[bool, int]:
        """Awards authoritative mastery XP to user."""
        try:
            return self._db.award_mastery_xp(
                user_id=user_id,
                concept=concept,
                amount=amount,
            )
        except Exception as e:
            logger.warning(f"MemoryRepository award_mastery_xp failed ({type(e).__name__}): {e}")
            return False, 0
