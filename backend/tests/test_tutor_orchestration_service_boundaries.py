"""
Test Suite for Problem 45: Clear Service Boundaries & Offline Orchestration Testing.
Validates:
1. Complete separation of API layer, Application layer, AI layer, Retrieval layer, and Persistence layer.
2. Verification: Unit-tests TutorOrchestrator completely offline without connecting to
   live Gemini API or production database.
3. Protocol conformance across AIClientProtocol, RetrievalProtocol, and MemoryRepositoryProtocol.
4. Correct SSE event sequence (METADATA -> TOKEN -> DONE).
5. Asynchronous persistence of interaction memory.
6. Evaluation and mastery XP award decoupling.
7. Graceful handling of AI model timeout and quota exhaustion.
8. Resilience when retrieval layer degrades.
"""
import json
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
import pytest

from app.ai_agent.ai_client import AIClientProtocol, GeminiAIClient
from app.ai_agent.retrieval_service import RetrievalProtocol, TutorRetrievalService
from app.core_backend.repositories.memory_repository import MemoryRepositoryProtocol, MemoryRepository
from app.application.tutor_orchestrator import (
    TutorOrchestrator,
    SSEEventName,
    make_sse_event,
)


# ==============================================================================
# In-Memory Offline Mock Implementations (Zero External Dependencies)
# ==============================================================================

class MockAIClient:
    """Mock AI Layer: yields predefined tokens without calling external Gemini API."""
    def __init__(self, token_chunks: Optional[List[str]] = None, fail_with: Optional[Exception] = None):
        self._chunks = token_chunks if token_chunks is not None else ["Force ", "equals ", "mass ", "times ", "acceleration."]
        self._fail_with = fail_with
        self.recorded_prompts: List[str] = []

    @property
    def model_name(self) -> str:
        return "mock-offline-physics-model"

    def is_configured(self) -> bool:
        return True

    async def stream_completion(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_seconds: float = 30.0,
        is_cancelled: Optional[Any] = None,
    ) -> AsyncGenerator[str, None]:
        self.recorded_prompts.append(prompt)
        if self._fail_with:
            raise self._fail_with
        for chunk in self._chunks:
            if is_cancelled and await is_cancelled():
                break
            await asyncio.sleep(0.001)
            yield chunk


class MockRetrievalService:
    """Mock Retrieval Layer: returns in-memory context without vector database."""
    def __init__(self, context: Optional[List[str]] = None, fail_with: Optional[Exception] = None):
        self._context = context if context is not None else ["Past discussion: Newton's first law of inertia."]
        self._fail_with = fail_with
        self.recorded_queries: List[str] = []

    async def generate_query_embedding(self, text: str) -> List[float]:
        # Return deterministic mock 768-dim vector without calling embedding models
        return [0.01 * (i % 10) for i in range(768)]

    async def retrieve_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        top_k: int = 3,
        **kwargs,
    ) -> List[Any]:
        self.recorded_queries.append(query)
        if self._fail_with:
            raise self._fail_with
        return self._context


class MockMemoryRepository:
    """Mock Persistence Layer: stores memories in a Python list without PostgreSQL."""
    def __init__(self):
        self.saved_memories: List[Dict[str, Any]] = []
        self.awarded_xp: List[Dict[str, Any]] = []

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
        return [m["text"] for m in self.saved_memories if m.get("user_id") == user_id][:top_k]

    def save_memory(
        self,
        session_id: str,
        text: str,
        embedding: Optional[List[float]],
        user_id: str,
    ) -> Any:
        record = {
            "session_id": session_id,
            "text": text,
            "embedding": embedding,
            "user_id": user_id,
        }
        self.saved_memories.append(record)
        return record

    def award_mastery_xp(
        self,
        user_id: str,
        concept: str,
        amount: int = 100,
    ):
        self.awarded_xp.append({"user_id": user_id, "concept": concept, "amount": amount})
        return True, amount


# ==============================================================================
# Helper to Parse SSE Event Stream
# ==============================================================================

def parse_sse_events(raw_chunks: List[str]) -> List[Dict[str, Any]]:
    """Parses raw SSE string frames into structured event dictionaries."""
    events = []
    full_text = "".join(raw_chunks)
    for block in full_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):].strip()
            elif line.startswith("data: "):
                data_str = line[len("data: "):].strip()
                data = json.loads(data_str)
        if data:
            if event_type:
                data["_event_type"] = event_type
            events.append(data)
    return events


# ==============================================================================
# 1. Verification: Offline Orchestration Testing
# ==============================================================================

@pytest.mark.asyncio
async def test_orchestration_executes_offline_without_live_gemini_or_database():
    """
    Verification: Unit-tests the entire orchestration workflow completely offline.
    Zero connection to live Gemini API or production PostgreSQL database.
    """
    mock_ai = MockAIClient(token_chunks=["Kinetic ", "energy ", "is ", "0.5 * m * v^2."])
    mock_retrieval = MockRetrievalService(context=["Prior topic: work and energy theorem."])
    mock_repo = MockMemoryRepository()

    orchestrator = TutorOrchestrator(
        ai_client=mock_ai,
        retrieval_service=mock_retrieval,
        memory_repository=mock_repo,
    )

    chunks = []
    async for chunk in orchestrator.execute_tutor_stream(
        prompt="Explain kinetic energy",
        user_id="student_offline_test",
        session_id="sess_offline_001",
    ):
        chunks.append(chunk)

    events = parse_sse_events(chunks)
    assert len(events) >= 3  # METADATA, TOKENs, DONE

    # 1. Metadata frame
    meta_event = events[0]
    assert meta_event["_event_type"] == SSEEventName.METADATA
    assert meta_event["model"] == "mock-offline-physics-model"
    assert meta_event["session_id"] == "sess_offline_001"

    # 2. Token frames
    token_events = [e for e in events if e.get("_event_type") == SSEEventName.TOKEN]
    assert len(token_events) == 4
    full_response = "".join(e["text"] for e in token_events)
    assert full_response == "Kinetic energy is 0.5 * m * v^2."

    # 3. Done terminal frame with usage metrics
    done_event = events[-1]
    assert done_event["_event_type"] == SSEEventName.DONE
    assert done_event["done"] is True
    assert done_event["status"] == "completed"
    assert done_event["usage"]["chunks_emitted"] == 4

    # 4. Verify Persistence Layer was called asynchronously
    assert len(mock_repo.saved_memories) == 1
    saved = mock_repo.saved_memories[0]
    assert saved["session_id"] == "sess_offline_001"
    assert saved["user_id"] == "student_offline_test"
    assert "Kinetic energy is 0.5 * m * v^2." in saved["text"]
    assert len(saved["embedding"]) == 768

    # 5. Verify Retrieval Layer received query
    assert len(mock_retrieval.recorded_queries) == 1
    assert "kinetic energy" in mock_retrieval.recorded_queries[0].lower()


# ==============================================================================
# 2. Concept Evaluation & Mastery Award Decoupling
# ==============================================================================

@pytest.mark.asyncio
async def test_orchestration_evaluates_concept_and_awards_mastery():
    """Confirms evaluation use case correctly decouples assessment from model generation."""
    mock_ai = MockAIClient(token_chunks=["Excellent work on Newton's laws."])
    mock_retrieval = MockRetrievalService()
    mock_repo = MockMemoryRepository()

    orchestrator = TutorOrchestrator(
        ai_client=mock_ai,
        retrieval_service=mock_retrieval,
        memory_repository=mock_repo,
    )

    chunks = []
    async for chunk in orchestrator.execute_tutor_stream(
        prompt="When the rocket pushes exhaust gas downward, an equal and opposite reaction force propels it upward.",
        user_id="student_newton_mastery",
        concept="Newton's 3rd Law",
        question="What occurs when two objects interact according to Newton?",
    ):
        chunks.append(chunk)

    events = parse_sse_events(chunks)

    # Confirm evaluation event emitted
    eval_events = [e for e in events if e.get("_event_type") == SSEEventName.EVALUATION]
    assert len(eval_events) == 1
    assert "evaluation" in eval_events[0]
    eval_data = eval_events[0]["evaluation"]
    assert eval_data["is_correct"] is True

    # Confirm mastery event emitted
    mastery_events = [e for e in events if e.get("_event_type") == SSEEventName.MASTERY]
    assert len(mastery_events) == 1
    assert "Newton's 3rd Law Mastered" in mastery_events[0]["kg_update"]
    assert mastery_events[0]["xp_awarded"] == 100

    # Confirm repository recorded the XP award
    assert len(mock_repo.awarded_xp) == 1
    assert mock_repo.awarded_xp[0]["concept"] == "Newton's 3rd Law"


# ==============================================================================
# 3. AI Layer Failure Isolation & Error Handlers
# ==============================================================================

@pytest.mark.asyncio
async def test_ai_layer_timeout_emits_structured_error_event():
    """Confirms model timeouts are trapped and translated into SSE error events without crashing."""
    failing_ai = MockAIClient(fail_with=TimeoutError("Model took longer than 30s"))
    mock_retrieval = MockRetrievalService()
    mock_repo = MockMemoryRepository()

    orchestrator = TutorOrchestrator(
        ai_client=failing_ai,
        retrieval_service=mock_retrieval,
        memory_repository=mock_repo,
    )

    chunks = []
    async for chunk in orchestrator.execute_tutor_stream(
        prompt="Tell me about gravity",
        user_id="student_timeout_test",
    ):
        chunks.append(chunk)

    events = parse_sse_events(chunks)
    error_events = [e for e in events if e.get("_event_type") == SSEEventName.ERROR]
    assert len(error_events) == 1
    assert error_events[0]["error_code"] == "MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_ai_layer_quota_exhaustion_emits_quota_error():
    """Confirms upstream 429 quota exhaustion emits specific QUOTA_EXHAUSTED event."""
    failing_ai = MockAIClient(fail_with=RuntimeError("ResourceExhausted: 429 Quota exceeded"))
    mock_retrieval = MockRetrievalService()
    mock_repo = MockMemoryRepository()

    orchestrator = TutorOrchestrator(
        ai_client=failing_ai,
        retrieval_service=mock_retrieval,
        memory_repository=mock_repo,
    )

    chunks = []
    async for chunk in orchestrator.execute_tutor_stream(
        prompt="Explain relativity",
        user_id="student_quota_test",
    ):
        chunks.append(chunk)

    events = parse_sse_events(chunks)
    error_events = [e for e in events if e.get("_event_type") == SSEEventName.ERROR]
    assert len(error_events) == 1
    assert error_events[0]["error_code"] == "QUOTA_EXHAUSTED"


# ==============================================================================
# 4. Retrieval Layer Degradation Resilience
# ==============================================================================

@pytest.mark.asyncio
async def test_retrieval_layer_failure_degrades_gracefully():
    """Confirms orchestration completes generation even when retrieval layer fails."""
    mock_ai = MockAIClient(token_chunks=["Gravity ", "pulls ", "masses ", "together."])
    failing_retrieval = MockRetrievalService(fail_with=RuntimeError("Vector index unavailable"))
    mock_repo = MockMemoryRepository()

    orchestrator = TutorOrchestrator(
        ai_client=mock_ai,
        retrieval_service=failing_retrieval,
        memory_repository=mock_repo,
    )

    chunks = []
    async for chunk in orchestrator.execute_tutor_stream(
        prompt="What is gravity?",
        user_id="student_degraded_test",
    ):
        chunks.append(chunk)

    events = parse_sse_events(chunks)
    done_events = [e for e in events if e.get("_event_type") == SSEEventName.DONE]
    assert len(done_events) == 1
    assert done_events[0]["status"] == "completed"


# ==============================================================================
# 5. Protocol Conformance Across Layers
# ==============================================================================

def test_layer_protocol_conformance():
    """Verifies that production implementations satisfy layer Protocols."""
    from app.core_backend.database.supabase_db import DatabaseManager

    db = DatabaseManager()
    repo = MemoryRepository(db)
    assert isinstance(repo, MemoryRepositoryProtocol)

    retrieval = TutorRetrievalService(repository=repo)
    assert isinstance(retrieval, RetrievalProtocol)

    client = GeminiAIClient()
    assert isinstance(client, AIClientProtocol)
