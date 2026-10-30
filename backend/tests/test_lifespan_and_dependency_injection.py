"""
Test Suite for Problem 28: The application creates global service instances at import time
Files: routes/tutor.py, routes/experiments.py, routes/gamification.py, tutor_service.py

Validates:
1. Application and route modules can be imported with zero network connections or side-effects.
2. FastAPI lifespan initializes connection pools and shared service clients (app.state.db, app.state.tutor_service).
3. FastAPI lifespan cleanly shuts down and releases resources (close_database_pool, shutdown_tutor_executor).
4. Route handlers receive services via FastAPI dependency injection (Depends(get_db), Depends(get_tutor)).
5. Service dependencies can be replaced with test doubles in unit tests via app.dependency_overrides.
6. Test isolation is maintained across requests.
"""
import os
import socket
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app, lifespan
from app.core_backend.core.dependencies import (
    get_db,
    get_tutor_service,
    get_database_manager,
    get_current_user,
    reset_shared_dependencies,
)
from app.ai_agent.learning_evaluation import EvaluationResult, LearningState

client = TestClient(app)

TEST_USER = {
    "id": "student_di_test_user",
    "email": "student@neurolab.test",
    "role": "authenticated",
}


@pytest.fixture(autouse=True)
def clean_dependencies():
    """Ensures dependency overrides are clean before and after each test."""
    app.dependency_overrides.clear()
    reset_shared_dependencies()
    yield
    app.dependency_overrides.clear()
    reset_shared_dependencies()


# =============================================================================
# 1. Network Side-Effect-Free Imports
# =============================================================================

def test_application_imports_are_free_of_network_side_effects(monkeypatch):
    """
    Importing the application in an environment without live external services
    must NOT attempt network or database socket connections.
    """
    connection_attempts = []

    def guarded_connect(sock_self, *args, **kwargs):
        connection_attempts.append(args)
        raise ConnectionRefusedError(f"Network call forbidden during import: {args}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setenv("ENVIRONMENT", "test")

    # Import critical service and route modules
    import app.main
    import app.core_backend.routes.tutor
    import app.core_backend.routes.experiments
    import app.core_backend.routes.gamification
    import app.ai_agent.tutor_service

    assert len(connection_attempts) == 0, f"Unexpected socket connections: {connection_attempts}"


# =============================================================================
# 2. FastAPI Lifespan Startup & Shutdown Resource Management
# =============================================================================

@pytest.mark.asyncio
async def test_fastapi_lifespan_initializes_and_closes_resources(monkeypatch):
    """
    FastAPI lifespan must:
    1. Initialize connection pool and shared services during startup.
    2. Attach db, tutor_service, and tutor_executor to app.state.
    3. Close connection pool and executor on shutdown.
    """
    pool_inited = []
    pool_closed = []
    executor_shutdown = []

    monkeypatch.setenv("POSTGRES_URL", "postgresql://test_user:test_pass@remote-db:5432/neurolab")

    with patch("app.main.init_database_pool", lambda url: pool_inited.append(url)), \
         patch("app.main.close_database_pool", lambda: pool_closed.append(True)), \
         patch("app.main.shutdown_tutor_executor", lambda wait=False: executor_shutdown.append(wait)):

        async with lifespan(app):
            # Assert startup initialization
            assert len(pool_inited) == 1
            assert hasattr(app.state, "db")
            assert app.state.db is not None
            assert hasattr(app.state, "tutor_service")
            assert app.state.tutor_service is not None
            assert hasattr(app.state, "tutor_executor")

        # Assert shutdown cleanup
        assert len(pool_closed) == 1
        assert len(executor_shutdown) == 1


# =============================================================================
# 3. Dependency Injection & Test Double Overrides
# =============================================================================

def test_inject_mock_database_into_experiments_routes():
    """
    Replacing get_db dependency with a mock database double must isolate the experiment route.
    """
    mock_db = MagicMock()
    mock_db.get_experiments.return_value = [
        {"id": "exp_mock_1", "user_id": TEST_USER["id"], "type": "free_fall", "metrics": {"h": 50}}
    ]

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: mock_db

    res = client.get("/api/experiments/history")
    assert res.status_code == 200
    assert len(res.json()["history"]) == 1
    assert res.json()["history"][0]["id"] == "exp_mock_1"

    # Verify mock was directly invoked by the route handler
    mock_db.get_experiments.assert_called_once_with(user_id=TEST_USER["id"])


def test_inject_mock_database_into_gamification_routes():
    """
    Replacing get_db dependency with a mock database double must isolate the gamification route.
    """
    mock_db = MagicMock()
    mock_db.get_user_xp.return_value = 1750

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_db] = lambda: mock_db

    res = client.get("/api/gamification/my-xp")
    assert res.status_code == 200
    assert res.json() == {"user_id": TEST_USER["id"], "xp": 1750}

    # Verify mock was directly invoked by the route handler
    mock_db.get_user_xp.assert_called_once_with(user_id=TEST_USER["id"])


def test_inject_mock_tutor_service_into_tutor_routes():
    """
    Replacing get_tutor_service dependency with a mock service double must isolate the tutor route.
    """
    mock_tutor = MagicMock()
    mock_tutor.evaluate_answer = AsyncMock(return_value=EvaluationResult(
        concept="Momentum",
        is_correct=True,
        confidence=0.98,
        explanation="In an inelastic collision, momentum is conserved while kinetic energy is lost.",
        feedback="Outstanding conceptual accuracy!",
        state=LearningState.MASTERY_CONFIRMED,
        mastery_awarded=True,
        xp_awarded=50,
    ))

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    app.dependency_overrides[get_tutor_service] = lambda: mock_tutor

    payload = {
        "concept": "Momentum",
        "question": "What happens in an inelastic collision?",
        "answer": "Objects stick together and kinetic energy is not conserved.",
    }
    res = client.post("/api/tutor/evaluate-answer", json=payload)
    assert res.status_code == 200
    assert res.json()["is_correct"] is True
    assert res.json()["mastery_awarded"] is True

    # Verify mock was directly invoked by the route handler
    mock_tutor.evaluate_answer.assert_called_once_with(
        user_id=TEST_USER["id"],
        concept="Momentum",
        question="What happens in an inelastic collision?",
        answer="Objects stick together and kinetic energy is not conserved.",
    )


def test_dependency_overrides_clearing_restores_isolation():
    """
    Clearing app.dependency_overrides restores default dependency resolution.
    """
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    mock_db = MagicMock()
    mock_db.get_user_xp.return_value = 9999
    app.dependency_overrides[get_db] = lambda: mock_db

    # With override
    res1 = client.get("/api/gamification/my-xp")
    assert res1.json()["xp"] == 9999

    # Clear override
    app.dependency_overrides.pop(get_db, None)

    # Restores real / local db manager without test double
    res2 = client.get("/api/gamification/my-xp")
    assert res2.status_code == 200
    assert res2.json()["xp"] != 9999
