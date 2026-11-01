import os
import json
import asyncio
import pytest
from unittest.mock import MagicMock
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app
from app.ai_agent.tutor_service import AITutorService, SSEEventName, make_sse_event
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.supabase_db import DatabaseManager

client = TestClient(app)

AUTH_USER = {"id": "streaming_student_test", "email": "streaming@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_streaming"}


@pytest.fixture(autouse=True)
def setup_auth_override():
    async def override_user(authorization=None):
        return AUTH_USER

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


class AsyncMockRequest:
    def __init__(self, disconnected=False):
        self._disconnected = disconnected

    async def is_disconnected(self):
        return self._disconnected


class MockChatRequest:
    def __init__(self, prompt="Explain gravity", session_id="test_stream_session"):
        self.prompt = prompt
        self.session_id = session_id


class MockDB(DatabaseManager):
    def search_memories(self, *args, **kwargs):
        return ["Gravity causes objects to fall."]

    def save_memory(self, *args, **kwargs):
        return 1

    def award_mastery_xp(self, *args, **kwargs):
        return True, 100


def parse_sse_frames(raw_text: str):
    """
    Parses SSE raw text chunks into a list of structured frames:
    [{"event": "metadata", "id": 1, "data": {...}}, ...]
    """
    frames = []
    blocks = raw_text.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        frame = {}
        for line in block.strip().split("\n"):
            if line.startswith("event: "):
                frame["event"] = line[7:].strip()
            elif line.startswith("id: "):
                frame["id"] = int(line[4:].strip())
            elif line.startswith("data: "):
                frame["data"] = json.loads(line[6:].strip())
        if "data" in frame:
            frames.append(frame)
    return frames


# ==============================================================================
# Problem 15 Verifications: Robust Streaming Semantics
# ==============================================================================

@pytest.mark.asyncio
async def test_normal_completion_sse_protocol():
    """
    Verification:
    1. metadata: safe request and model metadata emitted first.
    2. token: incremental answer content emitted for each chunk.
    3. done: final completion status, finish reason, and usage statistics.
    4. Incremental id fields present on all frames.
    """
    mock_db = MockDB()
    tutor = AITutorService(db=mock_db)

    # Mock model yielding multiple chunks
    mock_model = MagicMock()
    chunk1 = MagicMock(text="Gravity is an ")
    chunk2 = MagicMock(text="attractive force between ")
    chunk3 = MagicMock(text="masses.")
    mock_model.generate_content.return_value = [chunk1, chunk2, chunk3]
    tutor.model = mock_model

    req = MockChatRequest(prompt="What is gravity?", session_id="gravity_sess_1")

    raw_output = ""
    async for event_str in tutor.stream_chat(req, user_id="student_123"):
        raw_output += event_str

    frames = parse_sse_frames(raw_output)
    assert len(frames) >= 5, f"Expected metadata + 3 tokens + done, got {len(frames)}"

    # 1. Metadata frame
    metadata_frame = frames[0]
    assert metadata_frame["event"] == SSEEventName.METADATA
    assert metadata_frame["id"] == 1
    assert metadata_frame["data"]["request_id"].startswith("req_")
    assert metadata_frame["data"]["status"] == "started"
    assert metadata_frame["data"]["session_id"] == "gravity_sess_1"

    # 2. Token frames
    token_frames = frames[1:4]
    reconstructed_text = ""
    for idx, tf in enumerate(token_frames, start=1):
        assert tf["event"] == SSEEventName.TOKEN
        assert tf["id"] == idx + 1
        assert "token" in tf["data"]
        assert "delta" in tf["data"]
        assert tf["data"]["index"] == idx
        reconstructed_text += tf["data"]["delta"]

    assert reconstructed_text == "Gravity is an attractive force between masses."

    # 3. Terminal Done frame
    done_frame = frames[-1]
    assert done_frame["event"] == SSEEventName.DONE
    assert done_frame["data"]["done"] is True
    assert done_frame["data"]["status"] == "completed"
    assert done_frame["data"]["finish_reason"] == "stop"
    usage = done_frame["data"]["usage"]
    assert usage["chunks_emitted"] == 3
    assert usage["prompt_tokens_est"] >= 1
    assert usage["completion_tokens_est"] >= 1
    assert usage["total_tokens_est"] >= usage["prompt_tokens_est"]
    assert usage["duration_seconds"] >= 0.0


@pytest.mark.asyncio
async def test_model_failure_mid_stream():
    """
    Verification:
    Simulates a model generator that emits initial tokens and then raises an exception.
    Confirms client receives initial tokens, followed by a sanitized error event
    with error_code='MODEL_STREAM_ERROR', without leaking internal traceback details.
    """
    mock_db = MockDB()
    tutor = AITutorService(db=mock_db)

    # Generator that yields one chunk then raises an exception
    def failing_chunk_generator():
        yield MagicMock(text="Initial part of answer...")
        raise RuntimeError("Connection dropped by internal socket 10.0.0.12:9000")

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = lambda *args, **kwargs: failing_chunk_generator()
    tutor.model = mock_model

    req = MockChatRequest(prompt="Explain momentum")

    raw_output = ""
    async for event_str in tutor.stream_chat(req, user_id="student_123"):
        raw_output += event_str

    frames = parse_sse_frames(raw_output)
    event_types = [f["event"] for f in frames]

    assert SSEEventName.METADATA in event_types
    assert SSEEventName.TOKEN in event_types
    assert SSEEventName.ERROR in event_types

    # Find the error event
    error_frame = next(f for f in frames if f["event"] == SSEEventName.ERROR)
    err_data = error_frame["data"]
    assert err_data["error_code"] in ("PARTIAL_STREAM_FAILURE", "MODEL_STREAM_ERROR")
    assert err_data["error"] in ("The tutor stream was interrupted.", "The tutor is temporarily unavailable.")
    # Ensure sensitive socket and internal traceback are NOT leaked
    assert "10.0.0.12" not in str(err_data)
    assert "RuntimeError" not in str(err_data)


@pytest.mark.asyncio
async def test_client_cancellation_during_stream():
    """
    Verification:
    Tests client disconnect detection.
    When request.is_disconnected() returns True, the stream exits immediately
    and the concurrency semaphore is released cleanly.
    """
    mock_db = MockDB()
    tutor = AITutorService(db=mock_db)
    initial_semaphore_slots = tutor._concurrency_semaphore._value

    # Simulate client disconnected before generation
    disconnect_req = AsyncMockRequest(disconnected=True)
    req = MockChatRequest(prompt="Explain waves")

    emitted_events = []
    async for event in tutor.stream_chat(req, user_id="student_123", request=disconnect_req):
        emitted_events.append(event)

    # Disconnected early: should abort before emitting tokens
    assert len(emitted_events) == 0
    # Semaphore must be strictly released
    assert tutor._concurrency_semaphore._value == initial_semaphore_slots


@pytest.mark.asyncio
async def test_upstream_timeout_error_handling():
    """
    Verification:
    Simulates an upstream model timeout.
    Confirms client receives an SSE error frame with error_code='MODEL_TIMEOUT'
    and safe user message.
    """
    mock_db = MockDB()
    tutor = AITutorService(db=mock_db)

    def timeout_generator(*args, **kwargs):
        raise TimeoutError("Deadline exceeded waiting for inference gateway")

    mock_model = MagicMock()
    mock_model.generate_content.side_effect = timeout_generator
    tutor.model = mock_model

    req = MockChatRequest(prompt="Explain thermodynamics")

    raw_output = ""
    async for event_str in tutor.stream_chat(req, user_id="student_123"):
        raw_output += event_str

    frames = parse_sse_frames(raw_output)
    error_frames = [f for f in frames if f["event"] == SSEEventName.ERROR]
    assert len(error_frames) == 1

    err_data = error_frames[0]["data"]
    assert err_data["error_code"] == "MODEL_TIMEOUT"
    assert "The tutor took too long to respond." in err_data["error"]
    assert "inference gateway" not in err_data["error"]


@pytest.mark.asyncio
async def test_reconnect_last_event_id_header():
    """
    Verification:
    Tests reconnect behavior with Last-Event-ID.
    When a client sends 'Last-Event-ID: 42', metadata frame captures reconnect_last_event_id='42'.
    """
    mock_db = MockDB()
    tutor = AITutorService(db=mock_db)

    mock_model = MagicMock()
    mock_model.generate_content.return_value = [MagicMock(text="Reconnected chunk")]
    tutor.model = mock_model

    req = MockChatRequest(prompt="Continue explanation")

    raw_output = ""
    async for event_str in tutor.stream_chat(req, user_id="student_123", last_event_id="42"):
        raw_output += event_str

    frames = parse_sse_frames(raw_output)
    metadata_frame = frames[0]
    assert metadata_frame["data"]["reconnect_last_event_id"] == "42"


def test_streaming_api_endpoint_headers_and_response():
    """
    Verification:
    Calls POST /api/tutor/chat/stream through FastAPI TestClient.
    Confirms:
    1. HTTP Status 200.
    2. X-Accel-Buffering: no (instructs Nginx/proxies to not buffer chunks).
    3. Cache-Control: no-cache, no-transform.
    4. Content-Type: text/event-stream; charset=utf-8.
    5. SSE data contains structured metadata, token, and done frames.
    """
    from app.core_backend.routes import tutor as tutor_route

    mock_model = MagicMock()
    mock_model.generate_content.return_value = [
        MagicMock(text="Kinetic energy is "),
        MagicMock(text="proportional to velocity squared."),
    ]
    tutor_route.tutor_service.model = mock_model

    headers = {
        **AUTH_HEADERS,
        "Last-Event-ID": "99",
    }
    response = client.post(
        "/api/tutor/chat/stream",
        json={"prompt": "What is kinetic energy?", "session_id": "api_test_sess"},
        headers=headers,
    )

    assert response.status_code == 200

    # Header checks
    assert response.headers.get("x-accel-buffering") == "no"
    assert "no-cache" in response.headers.get("cache-control", "")
    assert "no-transform" in response.headers.get("cache-control", "")
    assert "text/event-stream" in response.headers.get("content-type", "")

    # Parse body
    frames = parse_sse_frames(response.text)
    event_names = [f["event"] for f in frames]
    assert SSEEventName.METADATA in event_names
    assert SSEEventName.TOKEN in event_names
    assert SSEEventName.DONE in event_names

    # Check reconnect metadata was forwarded from headers
    meta = next(f for f in frames if f["event"] == SSEEventName.METADATA)
    assert meta["data"]["reconnect_last_event_id"] == "99"


def test_nginx_configurations_disable_buffering_and_set_timeouts():
    """
    Verification:
    Ensures proxy configurations in both root nginx.conf and backend/nginx.conf:
    1. Have proxy_buffering off;
    2. Have proxy_cache off;
    3. Have chunked_transfer_encoding on;
    4. Have proxy_read_timeout set to 300s.
    """
    configs_to_check = ["nginx.conf", "backend/nginx.conf"]
    for cfg_path in configs_to_check:
        with open(cfg_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "proxy_buffering off;" in content, f"{cfg_path} missing proxy_buffering off;"
        assert "proxy_cache off;" in content, f"{cfg_path} missing proxy_cache off;"
        assert "chunked_transfer_encoding on;" in content, f"{cfg_path} missing chunked_transfer_encoding on;"
        assert "proxy_read_timeout 300s;" in content, f"{cfg_path} missing proxy_read_timeout 300s;"

