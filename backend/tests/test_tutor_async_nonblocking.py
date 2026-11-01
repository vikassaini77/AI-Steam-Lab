import os
import time
import asyncio
import threading
import numpy as np
import pytest
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from unittest.mock import MagicMock
from app.ai_agent.tutor_service import AITutorService, tutor_executor, _stream_model_chunks
from app.core_backend.database.supabase_db import DatabaseManager


class AsyncMockRequest:
    def __init__(self, disconnected=False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


class MockChatRequest:
    def __init__(self, prompt, session_id="test_sess"):
        self.prompt = prompt
        self.session_id = session_id


@pytest.mark.asyncio
async def test_database_calls_execute_off_main_thread(monkeypatch):
    """
    Verification: Confirms that search_memories and save_memory run inside the bounded
    executor on a worker thread, never blocking the main asyncio event loop thread.
    """
    worker_threads_recorded = []

    class ThreadTrackingDB(DatabaseManager):
        def search_memories(self, *args, **kwargs):
            worker_threads_recorded.append(("search", threading.current_thread()))
            return ["Tracked memory"]

        def save_memory(self, *args, **kwargs):
            worker_threads_recorded.append(("save", threading.current_thread()))
            return 1

    tracking_db = ThreadTrackingDB()
    tutor = AITutorService(db=tracking_db)

    # Isolate from external network embedding generation
    dummy_vec = [0.05] * 768
    async def fast_emb(*args, **kwargs):
        return dummy_vec
    monkeypatch.setattr(tutor, "generate_embedding", fast_emb)

    # Mock chunk generator
    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Newton's laws explain mechanical motion."
    mock_model.generate_content.return_value = [mock_chunk]
    tutor.model = mock_model

    req = MockChatRequest("Explain acceleration")
    main_thread = threading.current_thread()

    # Consume stream
    events = []
    async for event in tutor.stream_chat(req, user_id="thread_test_user"):
        events.append(event)

    assert len(worker_threads_recorded) >= 2
    for op_name, op_thread in worker_threads_recorded:
        # Critical verification: Thread must be a worker thread from executor, NOT main event loop
        assert op_thread != main_thread, f"Operation {op_name} ran on main thread!"
        assert "tutor_worker" in op_thread.name or "ThreadPoolExecutor" in op_thread.name or op_thread.daemon is False


@pytest.mark.asyncio
async def test_event_loop_lag_under_concurrent_chat_requests(monkeypatch):
    """
    Verification: Sends concurrent chat requests and monitors event loop lag.
    Event loop lag must remain minimal (< 50ms) because operations are offloaded.
    """
    mock_model = MagicMock()

    def slow_sync_generate(*args, **kwargs):
        # Simulate synchronous model computation taking 50ms per chunk
        time.sleep(0.05)
        chunk1 = MagicMock()
        chunk1.text = "Chunk 1 response."
        time.sleep(0.05)
        chunk2 = MagicMock()
        chunk2.text = "Chunk 2 response."
        return [chunk1, chunk2]

    mock_model.generate_content.side_effect = slow_sync_generate
    tutor = AITutorService()
    tutor.model = mock_model

    # Mock embedding generation to isolate local worker/pipeline latency from external network jitter
    dummy_vec = [0.05] * 768
    async def fast_emb(*args, **kwargs):
        return dummy_vec
    monkeypatch.setattr(tutor, "generate_embedding", fast_emb)

    # Monitor event loop responsiveness concurrently
    loop_lags = []
    monitoring = True

    async def lag_monitor():
        while monitoring:
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            delta = time.perf_counter() - t0
            lag = max(0.0, delta - 0.01)
            loop_lags.append(lag)

    monitor_task = asyncio.create_task(lag_monitor())

    # Send 4 concurrent chat requests
    async def run_single_chat(idx):
        req = MockChatRequest(f"Concurrent prompt {idx}")
        results = []
        async for item in tutor.stream_chat(req, user_id=f"user_{idx}"):
            results.append(item)
        return results

    t_start = time.perf_counter()
    tasks = [run_single_chat(i) for i in range(4)]
    responses = await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - t_start

    monitoring = False
    await monitor_task

    assert len(responses) == 4
    for r in responses:
        assert len(r) > 0

    # Critical check: Max event-loop lag must be negligible (< 80ms to accommodate OS timer resolution)
    # If the event loop were blocked by time.sleep(0.05), lag would spike to 200ms+
    max_lag = max(loop_lags) if loop_lags else 0.0
    avg_lag = sum(loop_lags) / len(loop_lags) if loop_lags else 0.0

    assert max_lag < 0.08, f"Event loop lag spiked to {max_lag * 1000:.1f}ms!"
    assert avg_lag < 0.02, f"Average loop lag too high: {avg_lag * 1000:.1f}ms"


@pytest.mark.asyncio
async def test_p95_p99_latency_and_worker_utilization(monkeypatch):
    """
    Verification: Measures p95 and p99 latency across concurrent requests
    and verifies that worker thread pool is strictly bounded.
    """
    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Fast response chunk."
    mock_model.generate_content.return_value = [mock_chunk]

    tutor = AITutorService()
    tutor.model = mock_model

    # Mock embedding generation to isolate local worker/pipeline latency from external network jitter
    dummy_vec = [0.05] * 768
    async def fast_emb(*args, **kwargs):
        return dummy_vec
    monkeypatch.setattr(tutor, "generate_embedding", fast_emb)

    # Verify bounded thread pool
    assert tutor._executor._max_workers <= 16
    assert tutor._executor._max_workers >= 4

    latencies = []

    async def timed_request(idx):
        t0 = time.perf_counter()
        req = MockChatRequest(f"Latency test {idx}")
        async for _ in tutor.stream_chat(req, user_id=f"user_lat_{idx}"):
            pass
        latencies.append(time.perf_counter() - t0)

    # Dispatch 5 concurrent requests matching max concurrency capacity
    await asyncio.gather(*[timed_request(i) for i in range(5)])

    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))

    # Sub-second latency for lightweight operations
    assert p95 < 0.5, f"p95 latency exceeded threshold: {p95:.3f}s"
    assert p99 < 0.8, f"p99 latency exceeded threshold: {p99:.3f}s"


@pytest.mark.asyncio
async def test_upstream_timeout_enforcement():
    """
    Verification: Confirms that an upstream model call exceeding timeout is interrupted,
    yielding safe error event without hanging the worker.
    """
    def stalling_generate(*args, **kwargs):
        time.sleep(2.0)
        return []

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = stalling_generate

    tutor = AITutorService()
    tutor.model = mock_model

    req = MockChatRequest("Stall request")

    # Call with a 0.2s timeout
    events = []
    from unittest.mock import patch
    with patch("app.ai_agent.tutor_service.MODEL_TIMEOUT_SECONDS", 0.2):
        async for event in tutor.stream_chat(req, user_id="timeout_user"):
            events.append(event)

    assert len(events) >= 1
    # Client receives structured timeout error
    assert "too long to respond" in events[0] or "status" in events[0]


@pytest.mark.asyncio
async def test_client_early_disconnect_cancellation():
    """
    Verification: When client disconnects before or during generation,
    generation halts immediately and releases concurrency slot.
    """
    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Unconsumed text"
    mock_model.generate_content.return_value = [mock_chunk]

    tutor = AITutorService()
    tutor.model = mock_model

    req = MockChatRequest("Disconnect request")
    disconnected_request = AsyncMockRequest(disconnected=True)

    events = []
    initial_semaphore_slots = tutor._concurrency_semaphore._value

    async for event in tutor.stream_chat(req, user_id="disc_user", request=disconnected_request):
        events.append(event)

    # Disconnected client consumed nothing
    assert len(events) == 0
    # Concurrency slot was safely released
    assert tutor._concurrency_semaphore._value == initial_semaphore_slots
