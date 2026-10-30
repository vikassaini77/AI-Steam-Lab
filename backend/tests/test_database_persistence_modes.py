import os
import json
import pytest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.pgvector_db import (
    PGVectorManager,
    DatabaseMode,
    DatabasePersistenceError,
    get_database_mode,
)
import app.core_backend.routes.experiments as exp_module

client = TestClient(app)

AUTH_USER = {"id": "prod_student_999", "email": "prod_student@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_token_persistence"}


@pytest.fixture(autouse=True)
def setup_auth_override():
    async def override_user(authorization=None):
        return AUTH_USER

    app.dependency_overrides[get_current_user] = override_user
    yield
    app.dependency_overrides.clear()


# ==============================================================================
# Problem 17 Verifications: Explicit Modes & Durable Persistence Failures
# ==============================================================================

def test_production_mode_stops_and_fails_on_save_experiment(monkeypatch):
    """
    Verification:
    Stop PostgreSQL and attempt to save an experiment.
    Production mode MUST report a controlled failure (HTTP 503 Service Unavailable)
    rather than claim that the record was saved with HTTP 200.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app:pass@db:5432/stemlab")

    # Simulate PostgreSQL stopped / down
    def mock_dead_postgres(*args, **kwargs):
        raise ConnectionRefusedError("could not connect to server at db:5432: Connection refused")

    with patch("psycopg2.connect", side_effect=mock_dead_postgres):
        # In Problem 19, manager instantiation is side-effect-free; write operation fails fast
        prod_manager = PGVectorManager()
        with pytest.raises(DatabasePersistenceError):
            prod_manager.save_experiment({"type": "Free-Fall", "metrics": {}}, user_id="user_1")

        monkeypatch.setattr(exp_module, "db", prod_manager)

        payload = {
            "user_id": "prod_student_999",
            "type": "Free-Fall",
            "metrics": {"height": 50.0, "time_of_flight": 3.19},
        }

        # Attempt to save experiment
        response = client.post("/api/experiments/save", json=payload, headers=AUTH_HEADERS)

        # Critical assertion: Must NOT claim 'saved' with 200
        assert response.status_code == 503, f"Expected 503 on persistence failure, got {response.status_code}: {response.text}"
        res_data = response.json()
        assert "Database persistence unavailable" in res_data.get("detail", "")
        # Confirm no fake in-memory list exists or claims saved status
        assert not hasattr(prod_manager, "fallback_experiments")


def test_production_mode_save_memory_raises_database_persistence_error(monkeypatch):
    """
    Verification:
    When PostgreSQL connection fails during memory saving in production,
    save_memory() raises DatabasePersistenceError rather than silently saving to memory.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    prod_manager = object.__new__(PGVectorManager)
    prod_manager.last_retrieval_metadata = []
    prod_manager.mode = DatabaseMode.PRODUCTION
    prod_manager.allow_in_memory_fallback = False
    prod_manager.is_in_memory_fallback = False
    prod_manager.url = "postgresql://app:pass@db:5432/stemlab"

    with patch("psycopg2.connect", side_effect=Exception("Database socket disconnected")):
        with pytest.raises(DatabasePersistenceError) as exc_info:
            prod_manager.save_memory(
                session_id="sess_123",
                text="Newton's third law",
                embedding=[0.05] * 768,
                user_id="user_123",
            )

    assert "Durable persistence failure" in str(exc_info.value)
    assert not hasattr(prod_manager, "fallback_memories")


def test_production_mode_add_xp_raises_database_persistence_error(monkeypatch):
    """
    Verification:
    add_xp() in production mode raises DatabasePersistenceError when PostgreSQL fails.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    prod_manager = object.__new__(PGVectorManager)
    prod_manager.mode = DatabaseMode.PRODUCTION
    prod_manager.allow_in_memory_fallback = False
    prod_manager.is_in_memory_fallback = False
    prod_manager.url = "postgresql://app:pass@db:5432/stemlab"

    with patch("psycopg2.connect", side_effect=Exception("PostgreSQL host unreachable")):
        with pytest.raises(DatabasePersistenceError) as exc_info:
            prod_manager.add_xp(user_id="user_123", amount=50)

    assert "Durable persistence failure" in str(exc_info.value)
    assert not hasattr(prod_manager, "fallback_xp")


def test_production_mode_award_mastery_xp_raises_database_persistence_error(monkeypatch):
    """
    Verification:
    award_mastery_xp() in production mode raises DatabasePersistenceError when PostgreSQL fails.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    prod_manager = object.__new__(PGVectorManager)
    prod_manager.mode = DatabaseMode.PRODUCTION
    prod_manager.allow_in_memory_fallback = False
    prod_manager.is_in_memory_fallback = False
    prod_manager.url = "postgresql://app:pass@db:5432/stemlab"

    with patch("psycopg2.connect", side_effect=Exception("PostgreSQL transaction aborted")):
        with pytest.raises(DatabasePersistenceError) as exc_info:
            prod_manager.award_mastery_xp(user_id="user_123", concept="Kinematics", amount=100)

    assert "Durable persistence failure" in str(exc_info.value)


def test_development_mode_allows_labeled_in_memory_fallback(monkeypatch):
    """
    Verification:
    In development mode with ALLOW_IN_MEMORY_FALLBACK=true:
    1. On connection failure, clearly labeled in-memory fallback is initialized.
    2. is_in_memory_fallback is flagged True.
    3. check_readiness() reports status='degraded' and mode='in-memory-fallback'.
    4. save_experiment succeeds in-memory for local testing/demoing.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_IN_MEMORY_FALLBACK", "true")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://dev_user:dev_pass@localhost:5432/stemlab")

    with patch("psycopg2.connect", side_effect=Exception("Local postgres not running")):
        dev_manager = PGVectorManager()
        # Readiness check verifies connection and engages fallback when unavailable
        readiness = dev_manager.check_readiness()

    assert dev_manager.mode == DatabaseMode.DEVELOPMENT
    assert dev_manager.is_in_memory_fallback is True
    assert hasattr(dev_manager, "fallback_experiments")
    assert hasattr(dev_manager, "fallback_memories")
    assert hasattr(dev_manager, "fallback_xp")

    # Readiness check reflects labeled degraded status
    assert readiness["status"] == "degraded"
    assert readiness["mode"] == "in-memory-fallback"
    assert readiness["connected"] is False

    # Experiment save works in-memory during development
    record = dev_manager.save_experiment(
        {"type": "Pendulum", "metrics": {"period": 2.0}},
        user_id="dev_student_1",
    )
    assert record["user_id"] == "dev_student_1"
    assert len(dev_manager.fallback_experiments) == 1
    assert dev_manager.fallback_experiments[0]["type"] == "Pendulum"


def test_production_mode_marks_readiness_as_unhealthy_when_unpersisted(monkeypatch):
    """
    Verification:
    In production mode, if persistence is unavailable, check_readiness() reports 'unhealthy'.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    prod_manager = object.__new__(PGVectorManager)
    prod_manager.mode = DatabaseMode.PRODUCTION
    prod_manager.allow_in_memory_fallback = False
    prod_manager.is_in_memory_fallback = False
    prod_manager.url = "postgresql://app:pass@db:5432/stemlab"

    with patch("psycopg2.connect", side_effect=Exception("Connection refused")):
        readiness = prod_manager.check_readiness()

    assert readiness["status"] == "unhealthy"
    assert readiness["connected"] is False
    assert "Connection refused" in readiness["error"]


def test_production_mode_successful_durable_commit(monkeypatch):
    """
    Verification:
    In production mode with PostgreSQL online:
    1. save_experiment commits SQL to PostgreSQL.
    2. save_memory commits SQL to PostgreSQL.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (42,)
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg2.connect", return_value=mock_conn):
        manager = PGVectorManager(url="postgresql://app:pass@db:5432/stemlab")

        # 1. Save experiment
        exp_record = manager.save_experiment(
            {"type": "Collision", "metrics": {"momentum": 10.0}},
            user_id="prod_user_42",
        )
        assert exp_record["user_id"] == "prod_user_42"
        mock_conn.commit.assert_called()

        # 2. Save memory
        doc_id = manager.save_memory(
            session_id="prod_sess",
            text="Conservation of momentum",
            embedding=[0.1] * 768,
            user_id="prod_user_42",
        )
        assert doc_id == 42
