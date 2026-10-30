"""
Tests for Problem 18 (Connection Management & Pool Efficiency) and
Problem 19 (Side-Effect-Free Imports & Versioned Migrations Lifecycle).
"""
import os
import sys
import time
import importlib
import threading
from unittest.mock import MagicMock, patch, call
import pytest

from app.core_backend.database.pgvector_db import (
    DatabaseConnectionPool,
    DatabasePoolTimeoutError,
    DatabasePersistenceError,
    DatabaseMode,
    PGVectorManager,
    get_database_pool,
    init_database_pool,
    close_database_pool,
)
from app.core_backend.database.migrations import (
    REQUIRED_SCHEMA_VERSION,
    get_current_schema_version,
    verify_schema_version,
    run_migrations,
    MIGRATIONS,
)


# =====================================================================
# Problem 18: Connection Pool, Concurrency, Metrics & Timeouts
# =====================================================================

def test_connection_pool_acquisition_and_reuse():
    """
    Verification:
    Connection pool acquires connections, releases them cleanly back to the pool,
    and reuses connections across sequential and concurrent operations.
    """
    mock_conn = MagicMock()
    mock_conn.closed = 0
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    pool = DatabaseConnectionPool(
        url="postgresql://user:pass@db:5432/stemlab",
        minconn=1,
        maxconn=3,
        timeout=2.0,
        statement_timeout_ms=3000,
        idle_tx_timeout_ms=6000,
    )

    with patch("psycopg2.connect", return_value=mock_conn) as mock_connect:
        # First acquisition creates the connection in the pool
        with pool.acquire() as conn:
            assert conn is mock_conn
            status = pool.get_status()
            assert status["active_connections"] == 1
            assert status["available_connections"] == 2

        # After exiting context, connection is released back to pool
        status = pool.get_status()
        assert status["active_connections"] == 0
        assert status["available_connections"] == 3
        assert status["total_acquisitions"] == 1
        assert status["total_queries"] == 1

        # Second acquisition reuses existing connection without reconnecting
        with pool.acquire() as conn2:
            assert conn2 is mock_conn
            assert pool.get_status()["active_connections"] == 1

        status = pool.get_status()
        assert status["active_connections"] == 0
        assert status["total_acquisitions"] == 2
        # Only 1 physical connection was established and then reused
        assert mock_connect.call_count == 1

    pool.close()


def test_connection_pool_sets_statement_and_transaction_timeouts():
    """
    Verification:
    Connection pool configures statement_timeout and idle_in_transaction_session_timeout
    in PostgreSQL connection startup options.
    """
    with patch("psycopg2.connect", return_value=MagicMock()) as mock_connect:
        pool = DatabaseConnectionPool(
            url="postgresql://user:pass@db:5432/stemlab",
            minconn=1,
            maxconn=5,
            timeout=2.0,
            statement_timeout_ms=4500,
            idle_tx_timeout_ms=9000,
        )
        with pool.acquire() as conn:
            pass

        assert mock_connect.called
        kwargs = mock_connect.call_args.kwargs
        assert "options" in kwargs
        options_str = kwargs["options"]
        assert "statement_timeout=4500" in options_str
        assert "idle_in_transaction_session_timeout=9000" in options_str
        pool.close()


def test_connection_pool_saturation_and_timeout():
    """
    Verification:
    When pool is saturated (all maxconn connections checked out), acquisition
    waits up to timeout and raises DatabasePoolTimeoutError if none become available.
    """
    mock_conn = MagicMock()
    mock_conn.closed = 0

    pool = DatabaseConnectionPool(
        url="postgresql://user:pass@db:5432/stemlab",
        minconn=1,
        maxconn=2,
        timeout=0.2,  # 200ms timeout for test speed
    )

    with patch("psycopg2.connect", return_value=mock_conn):
        # Check out all 2 connections
        ctx1 = pool.acquire()
        c1 = ctx1.__enter__()

        ctx2 = pool.acquire()
        c2 = ctx2.__enter__()

        assert pool.get_status()["active_connections"] == 2
        assert pool.get_status()["available_connections"] == 0

        # Attempt to acquire a 3rd connection: must timeout
        start = time.perf_counter()
        with pytest.raises(DatabasePoolTimeoutError) as exc_info:
            with pool.acquire(timeout=0.15):
                pass
        elapsed = time.perf_counter() - start

        assert elapsed >= 0.14
        assert "pool saturated" in str(exc_info.value).lower()
        assert pool.get_status()["failed_acquisitions"] == 1

        # Release one connection; subsequent acquisition must immediately succeed
        ctx1.__exit__(None, None, None)
        assert pool.get_status()["active_connections"] == 1

        with pool.acquire(timeout=0.5) as c3:
            assert c3 is not None
            assert pool.get_status()["active_connections"] == 2

        ctx2.__exit__(None, None, None)
        pool.close()


def test_concurrent_history_and_memory_retrieval_pool_saturation():
    """
    Verification:
    Run concurrent history and memory-retrieval requests across multiple threads
    while monitoring pool saturation, connection counts, and query metrics.
    """
    mock_conn = MagicMock()
    mock_conn.closed = 0
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = (1,)
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    max_pool_size = 4
    pool = DatabaseConnectionPool(
        url="postgresql://user:pass@db:5432/stemlab",
        minconn=1,
        maxconn=max_pool_size,
        timeout=2.0,
    )
    manager = PGVectorManager(url="postgresql://user:pass@db:5432/stemlab", pool=pool)

    num_threads = 12
    iterations_per_thread = 5
    exceptions = []
    max_observed_active = 0
    lock = threading.Lock()

    def worker_task(thread_id: int):
        nonlocal max_observed_active
        try:
            for i in range(iterations_per_thread):
                if i % 2 == 0:
                    # History retrieval
                    manager.get_experiments(user_id=f"user_{thread_id}")
                else:
                    # Memory retrieval / search
                    manager.search_memories(
                        query_embedding=[0.05] * 768,
                        top_k=2,
                        user_id=f"user_{thread_id}",
                    )

                with lock:
                    current_active = pool.get_status()["active_connections"]
                    if current_active > max_observed_active:
                        max_observed_active = current_active
        except Exception as e:
            with lock:
                exceptions.append(e)

    with patch("psycopg2.connect", return_value=mock_conn):
        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(exceptions) == 0, f"Concurrent workers raised exceptions: {exceptions}"
    # Crucial assertion: active connections never exceeded max_pool_size
    assert max_observed_active <= max_pool_size
    status = pool.get_status()
    assert status["total_acquisitions"] == num_threads * iterations_per_thread
    assert status["active_connections"] == 0
    assert status["failed_transactions"] == 0
    assert status["average_query_latency_ms"] >= 0.0

    pool.close()


def test_exception_in_transaction_triggers_rollback_and_preserves_pool():
    """
    Verification:
    When a database query raises an exception within acquire(), transaction is rolled back
    and connection is safely returned to the pool without leaking.
    """
    mock_conn = MagicMock()
    mock_conn.closed = 0
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("Syntax error or deadlock")
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    pool = DatabaseConnectionPool(
        url="postgresql://user:pass@db:5432/stemlab",
        minconn=1,
        maxconn=2,
        timeout=1.0,
    )

    with patch("psycopg2.connect", return_value=mock_conn):
        with pytest.raises(Exception) as exc_info:
            with pool.acquire() as conn:
                with conn.cursor() as cur:
                    cur.execute("INVALID SQL")

        assert "Syntax error" in str(exc_info.value)
        assert mock_conn.rollback.call_count >= 1
        status = pool.get_status()
        assert status["failed_transactions"] == 1
        assert status["active_connections"] == 0  # Reclaimed by pool!
        assert status["available_connections"] == 2

    pool.close()


# =====================================================================
# Problem 19: Side-Effect-Free Imports & Versioned Migrations Lifecycle
# =====================================================================

def test_side_effect_free_imports_with_no_database_available(monkeypatch):
    """
    Verification:
    Importing application modules with NO database available succeeds without
    performing any schema mutations (CREATE EXTENSION, CREATE TABLE, etc.)
    and without attempting network calls at import time.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app_user:prod_pass@unreachable.host:5432/stemlab")

    # Connect must NOT be called during module import or constructor
    with patch("psycopg2.connect", side_effect=AssertionError("psycopg2.connect was called during import!")):
        # 1. Instantiating PGVectorManager is side-effect-free
        manager = PGVectorManager()
        assert manager is not None
        assert manager.url == "postgresql://app_user:prod_pass@unreachable.host:5432/stemlab"

        # 2. Importing tutor service is side-effect-free
        from app.ai_agent.tutor_service import AITutorService
        tutor = AITutorService()
        assert tutor is not None

        # 3. Importing main FastAPI app is side-effect-free
        from app.main import app as main_app
        assert main_app is not None


def test_migrations_create_versioned_schema_and_track_versions():
    """
    Verification:
    run_migrations() executes schema creation using a dedicated administrative
    connection, creates schema_migrations, and records the current schema version.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Simulate: first check schema_migrations doesn't exist, then after migration version is 1
    call_counts = {"count": 0}

    def mock_fetchone():
        call_counts["count"] += 1
        if call_counts["count"] == 1:
            # Table exists check -> False (fresh database)
            return (False,)
        elif call_counts["count"] == 2:
            # After migration table exists check -> True
            return (True,)
        elif call_counts["count"] >= 3:
            # Current max version -> REQUIRED_SCHEMA_VERSION
            return (REQUIRED_SCHEMA_VERSION,)
        return (0,)

    mock_cursor.fetchone.side_effect = mock_fetchone

    with patch("psycopg2.connect", return_value=mock_conn) as mock_connect:
        version = run_migrations("postgresql://admin:admin_pass@db:5432/stemlab")
        assert version == REQUIRED_SCHEMA_VERSION

        # Verify DDL statements were executed
        executed_sqls = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert any("CREATE TABLE IF NOT EXISTS schema_migrations" in s for s in executed_sqls)
        assert any("INSERT INTO schema_migrations" in s for s in executed_sqls)
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()  # Dedicated administrative connection closed


def test_readiness_check_verifies_required_schema_version():
    """
    Verification:
    Readiness check verifies that the required schema version is present in PostgreSQL.
    If migrations are pending (version < REQUIRED_SCHEMA_VERSION), it reports
    unhealthy/degraded status with a clear schema migration error.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Case A: Outdated schema (version 0 or missing migrations)
    # 1. SELECT 1; -> (1,)
    # 2. Table exists check -> (True,)
    # 3. SELECT MAX(version) -> (0,)
    mock_cursor.fetchone.side_effect = [(1,), (True,), (0,)]

    with patch("psycopg2.connect", return_value=mock_conn):
        manager = PGVectorManager(url="postgresql://app_user:pass@db:5432/stemlab")
        readiness = manager.check_readiness()

        assert readiness["connected"] is True
        assert readiness["schema_status"] == "migration_pending"
        assert readiness["current_schema_version"] == 0
        assert "Schema migration pending" in readiness["error"]

    # Case B: Up to date schema (version 1 == REQUIRED_SCHEMA_VERSION)
    mock_cursor.fetchone.side_effect = [(1,), (True,), (REQUIRED_SCHEMA_VERSION,)]
    with patch("psycopg2.connect", return_value=mock_conn):
        manager = PGVectorManager(url="postgresql://app_user:pass@db:5432/stemlab")
        readiness = manager.check_readiness()

        assert readiness["status"] == "ready"
        assert readiness["connected"] is True
        assert readiness["schema_status"] == "up_to_date"
        assert readiness["schema_version"] == REQUIRED_SCHEMA_VERSION
        assert "pool" in readiness
