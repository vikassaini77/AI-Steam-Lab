"""
Memory Repository - Persistence Layer
Problem 45: Service boundaries separation.
Encapsulates conversation memory storage, hybrid vector retrieval queries,
and gamification mastery awards. Decoupled from AI prompting and HTTP routing.
"""
from typing import Any, List, Optional, Protocol, Tuple, runtime_checkable

from app.logger import logger


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
    ) -> Any:
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
    ) -> List[Any]:
        """Queries database for past conversational memories using vector and text search."""
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

        try:
            return self._db.search_memories(**kwargs)
        except TypeError:
            kwargs.pop("session_id", None)
            kwargs.pop("experiment_id", None)
            try:
                return self._db.search_memories(**kwargs)
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
    ) -> Any:
        """Persists conversational memory interaction."""
        try:
            return self._db.save_memory(
                session_id=session_id,
                text=text,
                embedding=embedding,
                user_id=user_id,
            )
        except Exception as e:
            logger.exception(f"MemoryRepository save_memory failed ({type(e).__name__}): {e}")
            raise

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

