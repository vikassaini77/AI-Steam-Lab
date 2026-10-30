import os
import uuid
import time
import pytest
from unittest.mock import MagicMock, patch
import psycopg2
from psycopg2.extensions import QueryCanceledError
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.pgvector_db import (
    PGVectorManager,
    DatabaseMode,
    DatabasePersistenceError,
    DatabaseConnectionError,
    DatabaseTimeoutError,
    DatabaseIntegrityError,
    DatabasePoolTimeoutError,
    is_transient_error,
    classify_db_exception,
    GLOBAL_DB_METRICS,
    get_database_metrics,
)

client = TestClient(app)

TEST_USER = {
    "id": "student_err_test",
    "sub": "student_err_test",
    "role": "student",
    "name": "Resilience Test User",
}


@pytest.fixture(autouse=True)
def reset_metrics_and_overrides():
    GLOBAL_DB_METRICS.reset()
    app.dependency_overrides.clear()
    yield
    GLOBAL_DB_METRICS.reset()
    app.dependency_overrides.clear()


# =====================================================================
# 1. Classification & Domain Exception Hierarchy Tests
# =====================================================================

def test_exception_classification_hierarchy():
    """
    Verifies that expected raw database exceptions are explicitly mapped
    to classified domain exception subclasses of DatabasePersistenceError.
    """
    op_id = "test_op_123"

    # Query timeout -> DatabaseTimeoutError
    q_cancel = QueryCanceledError("canceling statement due to statement timeout")
    classified_timeout = classify_db_exception(q_cancel, "test_query", op_id)
    assert isinstance(classified_timeout, DatabaseTimeoutError)
    assert isinstance(classified_timeout, DatabasePersistenceError)
    assert "timeout" in str(classified_timeout).lower()

    # Connection refused -> DatabaseConnectionError
    op_err = psycopg2.OperationalError("could not connect to server: Connection refused")
    classified_conn = classify_db_exception(op_err, "connect", op_id)
    assert isinstance(classified_conn, DatabaseConnectionError)
    assert isinstance(classified_conn, DatabasePersistenceError)

    # Pool timeout -> DatabasePoolTimeoutError (subclass of DatabaseConnectionError)
    pool_err = DatabasePoolTimeoutError("timed out waiting for pool")
    classified_pool = classify_db_exception(pool_err, "acquire", op_id)
    assert isinstance(classified_pool, DatabasePoolTimeoutError)
    assert isinstance(classified_pool, DatabaseConnectionError)

    # Constraint violation -> DatabaseIntegrityError
    integ_err = psycopg2.IntegrityError("duplicate key value violates unique constraint")
    classified_integ = classify_db_exception(integ_err, "insert", op_id)
    assert isinstance(classified_integ, DatabaseIntegrityError)
    assert isinstance(classified_integ, DatabasePersistenceError)

    # Generic persistence failure
    gen_err = RuntimeError("Unexpected disk error")
    classified_gen = classify_db_exception(gen_err, "write", op_id)
    assert isinstance(classified_gen, DatabasePersistenceError)
    assert not isinstance(classified_gen, DatabaseConnectionError)


def test_transient_error_detection():
    """
    Confirms only genuine transient connection drops are classified as retryable.
    Integrity violations, syntax errors, and query timeouts are strictly non-transient.
    """
    # Transient errors
    assert is_transient_error(psycopg2.OperationalError("server closed the connection unexpectedly"))
    assert is_transient_error(psycopg2.InterfaceError("connection already closed"))
    assert is_transient_error(ConnectionRefusedError("Connection refused"))
    assert is_transient_error(DatabasePoolTimeoutError("pool saturated"))
    assert is_transient_error(Exception("The database system is starting up"))

    # Non-transient errors
    assert not is_transient_error(psycopg2.IntegrityError("unique constraint"))
    assert not is_transient_error(QueryCanceledError("statement timeout"))
    assert not is_transient_error(psycopg2.ProgrammingError("syntax error in SQL"))
    assert not is_transient_error(psycopg2.DataError("value too long for varchar"))
    assert not is_transient_error(ValueError("invalid parameter"))


# =====================================================================
# 2. Bounded Retry Logic strictly for Transient & Idempotent Operations
# =====================================================================

def test_transient_retry_succeeds_for_idempotent_operation():
    """
    An idempotent operation encountering a transient connection failure on attempt 1
    should be retried and succeed on attempt 2, recording retry metrics.
    """
    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/nl")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    attempt_counter = 0

    def flaky_operation():
        nonlocal attempt_counter
        attempt_counter += 1
        if attempt_counter == 1:
            raise psycopg2.OperationalError("could not connect to server: Connection refused")
        return {"status": "recovered", "data": 42}

    result = manager._execute(
        operation_name="flaky_read",
        operation_fn=flaky_operation,
        is_idempotent=True,
        is_write=False,
        user_id="usr_1",
        max_retries=1,
    )

    assert result == {"status": "recovered", "data": 42}
    assert attempt_counter == 2
    metrics = manager.get_metrics()
    assert metrics["retries_attempted"] == 1
    assert metrics["retries_succeeded"] == 1
    assert metrics["connection_errors"] == 1


def test_non_idempotent_operation_is_never_retried():
    """
    CRITICAL: Non-idempotent operations (such as save_memory with auto-increment ID)
    MUST NEVER be retried upon transient errors, to prevent duplicate record insertion.
    """
    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/nl")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    call_count = 0

    def insert_serial_memory():
        nonlocal call_count
        call_count += 1
        raise psycopg2.OperationalError("server closed the connection unexpectedly")

    with pytest.raises(DatabaseConnectionError):
        manager._execute(
            operation_name="save_memory",
            operation_fn=insert_serial_memory,
            is_idempotent=False,  # strictly non-idempotent
            is_write=True,
            user_id="usr_1",
            max_retries=2,
        )

    # Executed exactly once; no retries attempted
    assert call_count == 1
    metrics = manager.get_metrics()
    assert metrics["retries_attempted"] == 0
    assert metrics["retries_succeeded"] == 0
    assert metrics["failed_writes"] == 1
    assert metrics["connection_errors"] == 1


def test_non_transient_error_is_never_retried_even_for_idempotent_operation():
    """
    Non-transient errors (IntegrityError, QueryCanceledError) fail immediately
    without retrying.
    """
    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/nl")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    call_count = 0

    def fail_with_integrity():
        nonlocal call_count
        call_count += 1
        raise psycopg2.IntegrityError("unique constraint violation")

    with pytest.raises(DatabaseIntegrityError):
        manager._execute(
            operation_name="idempotent_write",
            operation_fn=fail_with_integrity,
            is_idempotent=True,
            is_write=True,
            user_id="usr_1",
            max_retries=2,
        )

    assert call_count == 1
    metrics = manager.get_metrics()
    assert metrics["retries_attempted"] == 0
    assert metrics["failed_writes"] == 1


# =====================================================================
# 3. Telemetry Metrics Recording & Monitoring Endpoint
# =====================================================================

def test_telemetry_metrics_tracking_and_api_exposure():
    """
    Verifies that write failures, connection errors, query timeouts, and operation counts
    are recorded in DatabaseMetrics and served via /metrics/database and /api/monitoring/db-metrics.
    """
    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/nl")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    # Simulate query timeout
    with pytest.raises(DatabaseTimeoutError):
        manager._execute(
            operation_name="slow_search",
            operation_fn=MagicMock(side_effect=QueryCanceledError("canceling statement due to statement timeout")),
            is_idempotent=True,
            is_write=False,
        )

    # Simulate failed write
    with pytest.raises(DatabasePersistenceError):
        manager._execute(
            operation_name="save_experiment",
            operation_fn=MagicMock(side_effect=RuntimeError("Disk write failed")),
            is_idempotent=True,
            is_write=True,
        )

    metrics = manager.get_metrics()
    assert metrics["query_timeouts"] == 1
    assert metrics["failed_writes"] == 1
    assert metrics["failed_operations"] == 2

    # Verify monitoring API endpoint
    res = client.get("/metrics/database")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["metrics"]["query_timeouts"] == 1
    assert data["metrics"]["failed_writes"] == 1

    # Verify alternate alias endpoint
    res2 = client.get("/api/monitoring/db-metrics")
    assert res2.status_code == 200
    assert res2.json()["metrics"]["query_timeouts"] == 1


# =====================================================================
# 4. Outage Simulation Across Endpoints (Controlled HTTP 503 & Fail-Fast)
# =====================================================================

def test_save_experiment_during_database_outage_returns_503(monkeypatch):
    """
    When PostgreSQL is down in production mode, saving an experiment must fail fast
    with HTTP 503 and not silently claim the experiment was saved.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOW_IN_MEMORY_FALLBACK", "false")

    mock_db = MagicMock()
    mock_db.save_experiment.side_effect = DatabaseConnectionError("Database connection lost")

    from app.core_backend.routes import experiments as exp_module
    monkeypatch.setattr(exp_module, "db", mock_db)
    monkeypatch.setattr(exp_module.router, "db", mock_db, raising=False)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = {
        "user_id": TEST_USER["id"],
        "type": "Free-Fall",
        "metrics": {"height": 50.0},
    }

    res = client.post("/api/experiments/save", json=payload, headers={"Authorization": "Bearer tok"})
    assert res.status_code == 503
    assert "Database persistence unavailable" in res.json()["detail"]


def test_gamification_add_xp_during_database_outage_returns_503(monkeypatch):
    """
    When PostgreSQL is down in production mode, awarding XP must fail fast
    with HTTP 503 rather than fabricating success.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    mock_db = MagicMock()
    mock_db.record_xp_event.side_effect = DatabaseConnectionError("Database connection refused")

    from app.core_backend.routes import gamification as gam_module
    monkeypatch.setattr(gam_module, "db", mock_db)
    monkeypatch.setattr(gam_module.router, "db", mock_db, raising=False)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    payload = {
        "amount": 100,
        "action": "concept_mastery",
        "concept": "Gravity",
        "user_id": TEST_USER["id"],
    }

    res = client.post("/api/gamification/add-xp", json=payload, headers={"Authorization": "Bearer tok"})
    assert res.status_code == 503
    assert "Database persistence unavailable" in res.json()["detail"]


def test_tutor_memories_deletion_during_database_outage_returns_503(monkeypatch):
    """
    When PostgreSQL is down in production mode, memory deletion must report HTTP 503
    rather than reporting 0 deleted.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    mock_db = MagicMock()
    mock_db.delete_user_memories.side_effect = DatabaseConnectionError("Connection lost to database")

    from app.core_backend.routes import tutor as tutor_module
    monkeypatch.setattr(tutor_module, "db", mock_db)
    monkeypatch.setattr(tutor_module.router, "db", mock_db, raising=False)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    res = client.delete("/api/tutor/memories", headers={"Authorization": "Bearer tok"})
    assert res.status_code == 503
    assert "Database persistence unavailable" in res.json()["detail"]


def test_tutor_memories_export_during_database_outage_returns_503(monkeypatch):
    """
    When PostgreSQL is down in production mode, memory export must report HTTP 503.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")

    mock_db = MagicMock()
    mock_db.export_user_memories.side_effect = DatabaseConnectionError("Connection lost to database")

    from app.core_backend.routes import tutor as tutor_module
    monkeypatch.setattr(tutor_module, "db", mock_db)
    monkeypatch.setattr(tutor_module.router, "db", mock_db, raising=False)

    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    res = client.get("/api/tutor/memories/export", headers={"Authorization": "Bearer tok"})
    assert res.status_code == 503
    assert "Database persistence unavailable" in res.json()["detail"]


def test_readiness_probe_during_database_outage(monkeypatch):
    """
    Readiness probe (/ready) must return HTTP 503 and status 'unhealthy'
    when database is unreachable in production mode, recording connection failure.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://usr:secpwd@db:5432/stemlab")

    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/stemlab")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False

    # Simulate get_connection failing with OperationalError
    def mock_broken_conn():
        raise psycopg2.OperationalError("Connection to db:5432 failed: Connection refused")

    monkeypatch.setattr(manager, "get_connection", mock_broken_conn)

    from app.core_backend.database import pgvector_db
    monkeypatch.setattr(pgvector_db, "check_database_readiness", manager.check_readiness)

    res = client.get("/ready")
    assert res.status_code == 503
    data = res.json()
    assert data["status"] == "unhealthy"
    assert data["connected"] is False
    assert "Connection refused" in data["error"]
    assert "metrics" in data
    assert data["metrics"]["connection_errors"] >= 1


# =====================================================================
# 5. Production Mode Never Silently Falls Back to In-Memory Store
# =====================================================================

def test_production_mode_raises_on_unconfigured_or_failed_database():
    """
    In production mode, operations must raise DatabasePersistenceError immediately
    if the database is unconfigured or unavailable, rather than silently creating
    in-memory dictionaries.
    """
    manager = PGVectorManager(url="postgresql://usr:secpwd@db:5432/nl")
    manager.mode = DatabaseMode.PRODUCTION
    manager.allow_in_memory_fallback = False
    manager.is_in_memory_fallback = True  # force simulated fallback flag

    with pytest.raises(DatabasePersistenceError):
        manager.save_memory(
            session_id="sess_1",
            text="hello",
            embedding=[0.1] * 768,
            user_id="user_1",
        )

    with pytest.raises(DatabasePersistenceError):
        manager.save_experiment(
            data={"type": "pendulum"},
            user_id="user_1",
        )

    with pytest.raises(DatabasePersistenceError):
        manager.record_xp_event(
            user_id="user_1",
            action="test",
            amount=50,
        )

    with pytest.raises(DatabasePersistenceError):
        manager.search_memories(
            query_text="pendulum",
            user_id="user_1",
        )
