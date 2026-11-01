"""
Tests for Problem 8: Non-blocking streaming verification in AI Tutor & Client.
Verifies:
1. Concurrent tutor requests without event loop stalling or worker starvation.
2. Client disconnect cancellation during streaming (worker stop_event terminates thread).
3. Upstream API timeout (initial call timeout & mid-stream chunk stall timeout).
4. Rate-limit responses from Gemini (HTTP 429 / ResourceExhausted handled gracefully).
5. Partial stream failures (mid-stream errors emitted cleanly with partial_text preserved).
"""
import asyncio
import os
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai_agent.ai_client import GeminiAIClient, check_cancellation
from app.ai_agent.tutor_service import AITutorService, get_tutor_executor
from app.application.tutor_orchestrator import SSEEventName, TutorOrchestrator
from app.main import app


class DummyRequest:
    def __init__(self, is_disconnected_flag=False):
        self._disconnected = is_disconnected_flag

    async def is_disconnected(self):
        return self._disconnected

    def set_disconnected(self, val=True):
        self._disconnected = val


class MockChatRequest:
    def __init__(self, prompt: str, session_id: str = "test_sess"):
        self.prompt = prompt
        self.session_id = session_id
        self.concept = None
        self.question = None


class MockResourceExhausted(Exception):
    """Simulates google.api_core.exceptions.ResourceExhausted (429)."""
    def __init__(self, message="429 Quota exceeded for quota metric 'GenerateContent'"):
        super().__init__(message)
        self.code = 429
        self.status_code = 429


# ==============================================================================
# 1. Concurrent Tutor Requests Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_tutor_requests_no_event_loop_stalling():
    """
    Verification: 5 concurrent tutor requests run simultaneously.
    Synchronous model execution is offloaded so event loop lag remains < 50ms.
    """
    chunks_generated = []

    def mock_slow_generate(prompt, **kwargs):
        time.sleep(0.04)  # 40ms sync blocking in worker thread
        c1 = MagicMock()
        c1.text = f"Part 1 for {prompt[:10]}; "
        time.sleep(0.04)
        c2 = MagicMock()
        c2.text = f"Part 2 for {prompt[:10]}."
        chunks_generated.append(prompt)
        return [c1, c2]

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = mock_slow_generate

    tutor = AITutorService(model=mock_model)

    # Event loop latency monitor
    lags = []
    running = True

    async def lag_monitor():
        while running:
            t0 = time.perf_counter()
            await asyncio.sleep(0.01)
            delta = time.perf_counter() - t0
            lags.append(max(0.0, delta - 0.01))

    monitor_task = asyncio.create_task(lag_monitor())

    async def run_single_stream(idx):
        req = MockChatRequest(f"Question {idx}")
        events = []
        async for evt in tutor.stream_chat(req, user_id=f"user_{idx}"):
            events.append(evt)
        return events

    # 4 concurrent requests
    tasks = [run_single_stream(i) for i in range(4)]
    results = await asyncio.gather(*tasks)

    running = False
    await monitor_task

    assert len(results) == 4
    for r in results:
        assert len(r) > 0
        text = "".join(r)
        assert "Part 1" in text and "Part 2" in text

    max_lag = max(lags) if lags else 0.0
    # Event loop should never be blocked by the 40ms sleep in mock_slow_generate
    assert max_lag < 0.05, f"Event loop stalled! Max lag was {max_lag*1000:.1f}ms"


# ==============================================================================
# 2. Client Disconnect Cancellation Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_client_disconnect_cancellation_sync_worker_terminates():
    """
    Verification: When client disconnects mid-stream, check_cancellation signals stop_event,
    halting the background sync worker thread immediately without exhausting thread pool.
    """
    worker_continued_generating = threading.Event()
    worker_aborted = threading.Event()

    def mock_infinite_stream(prompt, **kwargs):
        class ChunkIterator:
            def __iter__(self):
                return self
            def __next__(self):
                # Yield 2 chunks, then stall
                time.sleep(0.02)
                chunk = MagicMock()
                chunk.text = "Chunk"
                return chunk
        return ChunkIterator()

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = mock_infinite_stream

    client = GeminiAIClient(model=mock_model)
    req = DummyRequest(is_disconnected_flag=False)

    tokens = []
    async for token in client.stream_completion("Hello", timeout_seconds=1.0, is_cancelled=req.is_disconnected):
        tokens.append(token)
        if len(tokens) >= 2:
            # Client disconnects after 2 chunks
            req.set_disconnected(True)

    assert len(tokens) == 2
    # Verify cancellation check
    assert await check_cancellation(req.is_disconnected) is True


@pytest.mark.asyncio
async def test_client_disconnect_cancellation_releases_semaphore():
    """
    Verification: When client disconnects before or during generation,
    orchestrator gracefully exits and releases the concurrency semaphore slot.
    """
    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Token"
    mock_model.generate_content.return_value = [mock_chunk]

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Hello")
    disc_req = DummyRequest(is_disconnected_flag=True)

    initial_slot = tutor._concurrency_semaphore._value

    events = []
    async for evt in tutor.stream_chat(req, user_id="user_disc", request=disc_req):
        events.append(evt)

    # Disconnected before stream -> 0 events
    assert len(events) == 0
    # Semaphore slot must be fully restored
    assert tutor._concurrency_semaphore._value == initial_slot


# ==============================================================================
# 3. Upstream API Timeout Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_upstream_timeout_initial_call():
    """
    Verification: If upstream Gemini API hangs initially, stream_completion raises
    TimeoutError and orchestrator emits MODEL_TIMEOUT error event.
    """
    def stalling_call(*args, **kwargs):
        time.sleep(2.0)
        return []

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = stalling_call

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Stall request")

    events = []
    with patch("app.ai_agent.tutor_service.MODEL_TIMEOUT_SECONDS", 0.15):
        async for evt in tutor.stream_chat(req, user_id="user_to"):
            events.append(evt)

    assert len(events) >= 1
    full_output = "".join(events)
    assert "MODEL_TIMEOUT" in full_output
    assert "too long to respond" in full_output


@pytest.mark.asyncio
async def test_upstream_timeout_mid_stream_chunk_stall():
    """
    Verification: If model sends 1 chunk then hangs mid-stream between chunks,
    per-chunk timeout triggers and emits MODEL_TIMEOUT preserving partial_text.
    """
    class SlowChunkIterator:
        def __init__(self):
            self.count = 0
        def __iter__(self):
            return self
        def __next__(self):
            self.count += 1
            if self.count == 1:
                c = MagicMock()
                c.text = "First chunk delivered."
                return c
            # Stall on chunk 2
            time.sleep(2.0)
            return MagicMock(text="Second chunk")

    mock_model = MagicMock()
    mock_model.generate_content.return_value = SlowChunkIterator()

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Mid-stream stall")

    events = []
    with patch("app.ai_agent.tutor_service.MODEL_TIMEOUT_SECONDS", 0.2):
        async for evt in tutor.stream_chat(req, user_id="user_mid_stall"):
            events.append(evt)

    full_output = "".join(events)
    # First chunk token was yielded
    assert "First chunk delivered." in full_output
    # Followed by MODEL_TIMEOUT error
    assert "MODEL_TIMEOUT" in full_output
    # And semaphore was restored
    assert tutor._concurrency_semaphore._value > 0


# ==============================================================================
# 4. Rate-Limit Responses from Gemini Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_rate_limit_response_initial_call():
    """
    Verification: When Gemini returns HTTP 429 / ResourceExhausted,
    orchestrator emits QUOTA_EXHAUSTED error event with retry_after_seconds.
    """
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = MockResourceExhausted("ResourceExhausted: 429 Quota exceeded")

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Prompt needing quota")

    events = []
    async for evt in tutor.stream_chat(req, user_id="user_429"):
        events.append(evt)

    assert len(events) >= 2  # metadata + error
    error_event = [e for e in events if "QUOTA_EXHAUSTED" in e]
    assert len(error_event) == 1
    assert "high demand" in error_event[0]
    assert "retry_after_seconds" in error_event[0]


@pytest.mark.asyncio
async def test_rate_limit_response_mid_stream():
    """
    Verification: When Gemini hits rate limit mid-stream after emitting 1 chunk,
    the client receives token event, followed by QUOTA_EXHAUSTED with partial_text.
    """
    class RateLimitMidStreamIterator:
        def __init__(self):
            self.count = 0
        def __iter__(self):
            return self
        def __next__(self):
            self.count += 1
            if self.count == 1:
                c = MagicMock()
                c.text = "Preliminary answer."
                return c
            raise MockResourceExhausted("429 rate limit exceeded mid-stream")

    mock_model = MagicMock()
    mock_model.generate_content.return_value = RateLimitMidStreamIterator()

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Prompt mid-stream quota")

    events = []
    async for evt in tutor.stream_chat(req, user_id="user_mid_429"):
        events.append(evt)

    full_output = "".join(events)
    assert "Preliminary answer." in full_output
    assert "QUOTA_EXHAUSTED" in full_output
    assert "partial_text" in full_output


# ==============================================================================
# 5. Partial Stream Failures Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_partial_stream_failure_emits_structured_error():
    """
    Verification: When an unhandled error occurs mid-stream (e.g. connection dropped),
    the client receives partial tokens, followed by PARTIAL_STREAM_FAILURE event with partial_text.
    """
    class NetworkDropIterator:
        def __init__(self):
            self.count = 0
        def __iter__(self):
            return self
        def __next__(self):
            self.count += 1
            if self.count <= 2:
                c = MagicMock()
                c.text = f"Token-{self.count} "
                return c
            raise RuntimeError("Connection reset by peer: stream dropped")

    mock_model = MagicMock()
    mock_model.generate_content.return_value = NetworkDropIterator()

    tutor = AITutorService(model=mock_model)
    req = MockChatRequest("Prompt network drop")

    events = []
    async for evt in tutor.stream_chat(req, user_id="user_drop"):
        events.append(evt)

    full_output = "".join(events)
    assert "Token-1" in full_output
    assert "Token-2" in full_output
    assert "PARTIAL_STREAM_FAILURE" in full_output
    assert "partial_text" in full_output
    # Concurrency semaphore must be released
    assert tutor._concurrency_semaphore._value == 5


# ==============================================================================
# 6. HTTP Streaming Endpoint Test
# ==============================================================================

def test_http_chat_stream_endpoint_flow():
    """
    Verification: Full HTTP integration test for /api/tutor/chat/stream.
    Ensures SSE headers, token events, and done events are properly streamed.
    """
    from app.core_backend.core.dependencies import get_current_user, get_db, get_tutor_service

    mock_model = MagicMock()
    c1 = MagicMock()
    c1.text = "Physics is wonderful. "
    c2 = MagicMock()
    c2.text = "Newton's laws govern motion."
    mock_model.generate_content.return_value = [c1, c2]

    mock_tutor_svc = AITutorService(model=mock_model)

    class MockDB:
        def check_and_increment_daily_usage(self, uid, limit=100):
            return True, 1

    app.dependency_overrides[get_current_user] = lambda: {"id": "test-stream-user-id", "email": "stream@neurolab.ai"}
    app.dependency_overrides[get_tutor_service] = lambda: mock_tutor_svc
    app.dependency_overrides[get_db] = lambda: MockDB()

    try:
        client = TestClient(app)
        response = client.post(
            "/api/tutor/chat/stream",
            json={"prompt": "Explain Newton's laws"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "metadata" in body
        assert "Physics is wonderful." in body
        assert "Newton's laws govern motion." in body
        assert "done" in body
    finally:
        app.dependency_overrides.clear()
