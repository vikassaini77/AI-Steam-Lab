"""
Tutor Retrieval Service - Retrieval Layer
Problem 45: Service boundaries separation.
Encapsulates query normalization, embedding generation, and ranked memory retrieval.
Decoupled from LLM prompting, HTTP, and SSE serialization.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Protocol, runtime_checkable

from app.ai_agent.embedding_service import generate_embedding
from app.core_backend.repositories.memory_repository import MemoryRepositoryProtocol
from app.logger import logger


@runtime_checkable
class RetrievalProtocol(Protocol):
    """Protocol defining the retrieval layer contract for semantic search."""

    async def generate_query_embedding(self, text: str) -> List[float]:
        ...

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        top_k: int = 3,
        embedding_fn: Optional[Any] = None,
    ) -> List[Any]:
        ...


class TutorRetrievalService:
    """
    Production implementation of the Retrieval Layer for AI Tutor interactions.
    Coordinates embedding generation and hybrid ranked retrieval via MemoryRepository.
    """
    def __init__(
        self,
        repository: MemoryRepositoryProtocol,
        executor: Optional[ThreadPoolExecutor] = None,
    ):
        self._repository = repository
        self._executor = executor

    async def generate_query_embedding(self, text: str) -> List[float]:
        """Generates real 768-dimensional normalized semantic query embedding."""
        return await generate_embedding(text)

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        top_k: int = 3,
        embedding_fn: Optional[Any] = None,
    ) -> List[Any]:
        """
        Executes hybrid ranked retrieval (combining vector similarity and keyword search).
        Offloads synchronous database search to thread pool.
        Degrades gracefully without crashing if retrieval fails.
        """
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []

        try:
            emb_gen = embedding_fn or self.generate_query_embedding
            q_emb = await emb_gen(normalized_query)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor,
                lambda: self._repository.search_memories(
                    query_embedding=q_emb,
                    query_text=normalized_query,
                    user_id=user_id,
                    session_id=session_id,
                    top_k=top_k,
                ),
            )
        except Exception as err:
            logger.warning(
                f"TutorRetrievalService degraded mode ({type(err).__name__}): {err}. "
                "Proceeding without past context."
            )
            return []

