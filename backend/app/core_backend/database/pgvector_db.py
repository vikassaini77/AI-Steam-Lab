import os
import time
import uuid
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Tuple
import psycopg2
from psycopg2.pool import ThreadedConnectionPool, PoolError
from psycopg2.extras import execute_values
import numpy as np
import json
from app.logger import logger
from app.core_backend.database.hybrid_retrieval import (
    normalize_query_text,
    execute_in_memory_hybrid_search,
    get_calibrated_threshold,
    RRF_K_DEFAULT,
)


class DatabaseMode(str, Enum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


def get_database_mode() -> DatabaseMode:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        return DatabaseMode.PRODUCTION
    elif env in ("test", "testing", "pytest"):
        return DatabaseMode.TEST
    return DatabaseMode.DEVELOPMENT


class ConfigurationError(RuntimeError):
    """Raised when critical configuration is missing, unsafe, or uses insecure defaults."""
    pass


class DatabasePersistenceError(RuntimeError):
    """Raised when a save or mutation operation fails and cannot be durably committed."""
    pass


class DatabaseConnectionError(DatabasePersistenceError):
    """Raised when connection to PostgreSQL fails, is refused, or is lost."""
    pass


class DatabaseTimeoutError(DatabasePersistenceError):
    """Raised when a query or connection acquisition times out."""
    pass


class DatabaseIntegrityError(DatabasePersistenceError):
    """Raised when an integrity or constraint violation occurs."""
    pass


class DatabasePoolTimeoutError(DatabaseConnectionError):
    """Raised when acquiring a database connection from the pool exceeds the acquisition timeout."""
    pass


class DatabaseMetrics:
    """
    Thread-safe telemetry metrics recorder for database operations.
    Tracks failed writes, connection errors, query timeouts, and retry performance.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.failed_writes = 0
        self.connection_errors = 0
        self.query_timeouts = 0
        self.retries_attempted = 0
        self.retries_succeeded = 0
        self.total_operations = 0
        self.failed_operations = 0

    def record_failed_write(self, op: str = ""):
        with self._lock:
            self.failed_writes += 1
        try:
            from app.core_backend.core.observability import record_database_failure
            record_database_failure(operation=op or "write", error_type="failed_write")
        except Exception:
            pass

    def record_connection_error(self, op: str = "", error_msg: str = ""):
        with self._lock:
            self.connection_errors += 1
        try:
            from app.core_backend.core.observability import record_database_failure
            record_database_failure(
                operation=op or "database",
                error_type="connection_error",
                error_msg=error_msg or "cannot connect",
            )
        except Exception:
            pass

    def record_query_timeout(self, op: str = ""):
        with self._lock:
            self.query_timeouts += 1
        try:
            from app.core_backend.core.observability import record_database_failure
            record_database_failure(
                operation=op or "query",
                error_type="timeout",
                error_msg="statement timeout",
            )
        except Exception:
            pass

    def record_retry(self, succeeded: bool = False):
        with self._lock:
            if succeeded:
                self.retries_succeeded += 1
            else:
                self.retries_attempted += 1

    def record_operation(self, success: bool = True, op: str = "database"):
        with self._lock:
            self.total_operations += 1
            if not success:
                self.failed_operations += 1
        try:
            from app.core_backend.core.observability import DATABASE_OPERATIONS_TOTAL
            status = "success" if success else "failed"
            DATABASE_OPERATIONS_TOTAL.labels(operation=op, status=status).inc()
        except Exception:
            pass

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "failed_writes": self.failed_writes,
                "connection_errors": self.connection_errors,
                "query_timeouts": self.query_timeouts,
                "retries_attempted": self.retries_attempted,
                "retries_succeeded": self.retries_succeeded,
                "total_operations": self.total_operations,
                "failed_operations": self.failed_operations,
            }

    def reset(self):
        with self._lock:
            self.failed_writes = 0
            self.connection_errors = 0
            self.query_timeouts = 0
            self.retries_attempted = 0
            self.retries_succeeded = 0
            self.total_operations = 0
            self.failed_operations = 0


GLOBAL_DB_METRICS = DatabaseMetrics()


def get_database_metrics() -> Dict[str, Any]:
    """Returns a snapshot of database operation metrics."""
    return GLOBAL_DB_METRICS.get_metrics()


def is_transient_error(e: Exception) -> bool:
    """
    Determines if a database exception is transient and can be retried safely
    for idempotent operations.
    """
    if isinstance(e, (DatabaseIntegrityError, psycopg2.IntegrityError, psycopg2.ProgrammingError, psycopg2.DataError, ValueError, TypeError)):
        return False
    if isinstance(e, (DatabaseTimeoutError, psycopg2.extensions.QueryCanceledError)):
        return False
    if isinstance(e, (DatabaseConnectionError, DatabasePoolTimeoutError, psycopg2.OperationalError, psycopg2.InterfaceError, PoolError, ConnectionRefusedError, ConnectionResetError)):
        return True
    msg = str(e).lower()
    transient_indicators = [
        "connection refused",
        "could not connect",
        "connection reset",
        "broken pipe",
        "server closed the connection",
        "pool saturated",
        "terminating connection due to administrator command",
        "the database system is in recovery mode",
        "the database system is starting up",
        "remaining connection slots are reserved",
    ]
    return any(indicator in msg for indicator in transient_indicators)


def classify_db_exception(e: Exception, operation: str, op_id: str) -> DatabasePersistenceError:
    """
    Classifies a raw database exception into a structured domain exception.
    """
    if isinstance(e, (DatabaseConnectionError, DatabaseTimeoutError, DatabaseIntegrityError, DatabasePoolTimeoutError)):
        return e
    if isinstance(e, psycopg2.extensions.QueryCanceledError) or "statement timeout" in str(e).lower():
        return DatabaseTimeoutError(
            f"Durable persistence failure: Database query timeout during {operation} [op_id={op_id}]: {e}"
        )
    if isinstance(e, (psycopg2.OperationalError, psycopg2.InterfaceError, ConnectionRefusedError, ConnectionResetError, PoolError, DatabasePoolTimeoutError)) or is_transient_error(e):
        return DatabaseConnectionError(
            f"Durable persistence failure: Database connection failure during {operation} [op_id={op_id}]: {e}"
        )
    if isinstance(e, psycopg2.IntegrityError):
        return DatabaseIntegrityError(
            f"Durable persistence failure: Database constraint violation during {operation} [op_id={op_id}]: {e}"
        )
    if isinstance(e, DatabasePersistenceError):
        return e
    return DatabasePersistenceError(
        f"Durable persistence failure during {operation} [op_id={op_id}]: {e}"
    )


class DatabaseConnectionPool:
    """
    Thread-safe connection pool for PostgreSQL utilizing psycopg2.pool.ThreadedConnectionPool.
    Enforces:
    - Configurable max pool size and min pool size
    - Acquisition timeout via threading.Semaphore
    - PostgreSQL statement_timeout and idle_in_transaction_session_timeout
    - Complete telemetry: connection counts, query counts, latency, and failed transactions
    - Safe connection state: ensures transactions are committed or rolled back,
      and broken connections are discarded cleanly.
    """
    def __init__(
        self,
        url: str,
        minconn: int = 1,
        maxconn: int = 10,
        timeout: float = 5.0,
        statement_timeout_ms: int = 5000,
        idle_tx_timeout_ms: int = 10000,
    ):
        self.url = url
        self.minconn = minconn
        self.maxconn = maxconn
        self.timeout = timeout
        self.statement_timeout_ms = statement_timeout_ms
        self.idle_tx_timeout_ms = idle_tx_timeout_ms

        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(maxconn)
        self._pool: Optional[ThreadedConnectionPool] = None
        self.closed = False

        # Telemetry metrics
        self._total_acquisitions = 0
        self._failed_acquisitions = 0
        self._total_queries = 0
        self._failed_transactions = 0
        self._total_query_latency_ms = 0.0

    def _ensure_pool(self):
        if self._pool is None and not self.closed:
            with self._lock:
                if self._pool is None and not self.closed:
                    conn_options = (
                        f"-c statement_timeout={self.statement_timeout_ms} "
                        f"-c idle_in_transaction_session_timeout={self.idle_tx_timeout_ms}"
                    )
                    effective_min = max(1, self.minconn)
                    self._pool = ThreadedConnectionPool(
                        effective_min,
                        self.maxconn,
                        self.url,
                        options=conn_options,
                    )
                    # Allow all created connections up to maxconn to remain cached in pool
                    self._pool.minconn = self.maxconn

    @contextmanager
    def acquire(self, timeout: Optional[float] = None):
        if self.closed:
            raise DatabasePersistenceError("Cannot acquire connection: connection pool is closed.")

        wait_time = self.timeout if timeout is None else timeout
        acquired = self._semaphore.acquire(timeout=wait_time)
        if not acquired:
            with self._lock:
                self._failed_acquisitions += 1
            raise DatabasePoolTimeoutError(
                f"Database connection pool saturated: timed out after {wait_time:.1f}s waiting for an available connection (max={self.maxconn})."
            )

        with self._lock:
            self._total_acquisitions += 1

        self._ensure_pool()
        conn = None
        start_time = time.perf_counter()
        failed = False
        try:
            try:
                conn = self._pool.getconn()
            except Exception as e:
                with self._lock:
                    self._failed_acquisitions += 1
                raise
            yield conn
        except Exception as e:
            failed = True
            with self._lock:
                self._failed_transactions += 1
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            raise
        finally:
            query_time_ms = (time.perf_counter() - start_time) * 1000.0
            with self._lock:
                self._total_queries += 1
                self._total_query_latency_ms += query_time_ms

            if conn is not None and self._pool is not None and not self._pool.closed:
                # Determine if connection is still usable
                is_closed = getattr(conn, "closed", 0)
                is_broken = False
                try:
                    if isinstance(is_closed, int) and is_closed != 0:
                        is_broken = True
                except Exception:
                    pass
                try:
                    self._pool.putconn(conn, close=is_broken)
                except Exception:
                    pass
            self._semaphore.release()

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            active = self.maxconn - self._semaphore._value
            pool_size = 0
            if self._pool and not self._pool.closed:
                pool_size = len(getattr(self._pool, "_pool", [])) + len(getattr(self._pool, "_used", {}))
            avg_latency = (
                round(self._total_query_latency_ms / self._total_queries, 2)
                if self._total_queries > 0
                else 0.0
            )
            return {
                "active_connections": max(0, active),
                "available_connections": max(0, self._semaphore._value),
                "max_connections": self.maxconn,
                "min_connections": self.minconn,
                "current_pool_size": pool_size,
                "total_acquisitions": self._total_acquisitions,
                "failed_acquisitions": self._failed_acquisitions,
                "total_queries": self._total_queries,
                "failed_transactions": self._failed_transactions,
                "average_query_latency_ms": avg_latency,
                "statement_timeout_ms": self.statement_timeout_ms,
                "idle_tx_timeout_ms": self.idle_tx_timeout_ms,
            }

    def close(self):
        with self._lock:
            self.closed = True
            if self._pool and not self._pool.closed:
                try:
                    self._pool.closeall()
                except Exception as e:
                    logger.warning(f"Error closing connection pool: {e}")
                self._pool = None


_GLOBAL_DATABASE_POOL: Optional[DatabaseConnectionPool] = None
_GLOBAL_POOL_LOCK = threading.Lock()


def get_database_pool(url: Optional[str] = None) -> DatabaseConnectionPool:
    global _GLOBAL_DATABASE_POOL
    target_url = url or get_database_url()
    if _GLOBAL_DATABASE_POOL is None or _GLOBAL_DATABASE_POOL.closed or _GLOBAL_DATABASE_POOL.url != target_url:
        with _GLOBAL_POOL_LOCK:
            if _GLOBAL_DATABASE_POOL is None or _GLOBAL_DATABASE_POOL.closed or _GLOBAL_DATABASE_POOL.url != target_url:
                if _GLOBAL_DATABASE_POOL and not _GLOBAL_DATABASE_POOL.closed:
                    _GLOBAL_DATABASE_POOL.close()
                max_size = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
                min_size = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
                timeout = float(os.getenv("DB_POOL_TIMEOUT", "5.0"))
                statement_timeout = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
                idle_timeout = int(os.getenv("DB_IDLE_TX_TIMEOUT_MS", "10000"))
                _GLOBAL_DATABASE_POOL = DatabaseConnectionPool(
                    url=target_url,
                    minconn=min_size,
                    maxconn=max_size,
                    timeout=timeout,
                    statement_timeout_ms=statement_timeout,
                    idle_tx_timeout_ms=idle_timeout,
                )
    return _GLOBAL_DATABASE_POOL


def init_database_pool(
    url: Optional[str] = None,
    maxconn: Optional[int] = None,
    timeout: Optional[float] = None,
) -> DatabaseConnectionPool:
    global _GLOBAL_DATABASE_POOL
    with _GLOBAL_POOL_LOCK:
        if _GLOBAL_DATABASE_POOL and not _GLOBAL_DATABASE_POOL.closed:
            _GLOBAL_DATABASE_POOL.close()
        target_url = url or get_database_url()
        max_size = maxconn or int(os.getenv("DB_POOL_MAX_SIZE", "10"))
        min_size = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
        pool_timeout = timeout or float(os.getenv("DB_POOL_TIMEOUT", "5.0"))
        statement_timeout = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
        idle_timeout = int(os.getenv("DB_IDLE_TX_TIMEOUT_MS", "10000"))
        _GLOBAL_DATABASE_POOL = DatabaseConnectionPool(
            url=target_url,
            minconn=min_size,
            maxconn=max_size,
            timeout=pool_timeout,
            statement_timeout_ms=statement_timeout,
            idle_tx_timeout_ms=idle_timeout,
        )
    return _GLOBAL_DATABASE_POOL


def close_database_pool():
    global _GLOBAL_DATABASE_POOL
    with _GLOBAL_POOL_LOCK:
        if _GLOBAL_DATABASE_POOL:
            _GLOBAL_DATABASE_POOL.close()
            _GLOBAL_DATABASE_POOL = None


def is_container_environment() -> bool:
    """
    Detects whether the application is running inside a Docker container.
    """
    return (
        os.getenv("IS_CONTAINER", "").lower() in ("true", "1")
        or os.getenv("DOCKER_CONTAINER", "").lower() in ("true", "1")
        or os.path.exists("/.dockerenv")
    )


def get_database_url() -> str:
    """
    Retrieves and validates the PostgreSQL database connection URL.
    - Inspects POSTGRES_URL or DATABASE_URL (supports Render/Heroku provisions).
    - Normalizes 'postgres://' scheme to 'postgresql://'.
    - In production (ENVIRONMENT=production or REQUIRE_POSTGRES=true):
      Requires explicit configuration; fails fast if POSTGRES_URL/DATABASE_URL is missing.
    - Never uses hardcoded default credentials ('postgres:postgres').
    - Detects container networking issues: if running inside a container,
      'localhost' refers to the backend container itself rather than the Compose
      service 'db:5432'.
    - If POSTGRES_URL is missing, raises ConfigurationError rather than connecting to an unintended database.
    """
    url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise ConfigurationError("POSTGRES_URL must be configured")

    # Normalize Render / Heroku postgres:// scheme to postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # Strictly disallow known insecure/default credentials
    if "postgres:postgres@" in url:
        raise ConfigurationError(
            "Security violation: Hardcoded default credentials 'postgres:postgres' are strictly prohibited in POSTGRES_URL. "
            "Please configure strong, dedicated database credentials."
        )

    # Detect invalid container networking (pointing to localhost inside container)
    if is_container_environment() and ("@localhost:" in url or "@127.0.0.1:" in url):
        raise ConfigurationError(
            "Configuration error: Inside a Docker container, 'localhost' refers to the container itself. "
            "The Compose PostgreSQL service must be addressed using the service hostname 'db:5432' "
            "(e.g. postgresql://user:pass@db:5432/dbname)."
        )

    return url


class PGVectorManager:
    @property
    def metrics(self) -> DatabaseMetrics:
        if not hasattr(self, "_metrics") or self._metrics is None:
            self._metrics = GLOBAL_DB_METRICS
        return self._metrics

    @metrics.setter
    def metrics(self, val: DatabaseMetrics):
        self._metrics = val

    def __init__(self, url: Optional[str] = None, pool: Optional[DatabaseConnectionPool] = None):
        self.last_retrieval_metadata: List[Dict[str, Any]] = []
        self.mode = get_database_mode()
        self.allow_in_memory_fallback = (
            self.mode in (DatabaseMode.DEVELOPMENT, DatabaseMode.TEST)
            and os.getenv("ALLOW_IN_MEMORY_FALLBACK", "true").lower() in ("true", "1", "yes")
        )
        self.is_in_memory_fallback = False
        self.last_connection_error: Optional[str] = None
        self._custom_pool = pool
        self._metrics = GLOBAL_DB_METRICS

        try:
            self.url: Optional[str] = url or get_database_url()
        except ConfigurationError as e:
            self.last_connection_error = str(e)
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                logger.critical(f"PGVectorManager: Configuration error in {self.mode} mode: {e}")
                raise
            logger.warning(
                f"PGVectorManager [DEVELOPMENT FALLBACK]: {e}. "
                "Operating in ephemeral in-memory mode. Data will NOT be durably persisted."
            )
            self.url = None
            self.is_in_memory_fallback = True
            self.fallback_memories = []
            self.fallback_experiments = []
            self.fallback_xp = {}
        except Exception as e:
            self.last_connection_error = str(e)
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                logger.critical(f"PGVectorManager: Database configuration error in {self.mode} mode: {e}")
                raise DatabasePersistenceError(f"Database configuration failed: {e}")
            logger.warning(
                f"PGVectorManager [DEVELOPMENT FALLBACK]: Failed to configure postgres: {e}. "
                "Operating in ephemeral in-memory mode. Data will NOT be durably persisted."
            )
            self.url = None
            self.is_in_memory_fallback = True
            self.fallback_memories = []
            self.fallback_experiments = []
            self.fallback_xp = {}

    def get_metrics(self) -> Dict[str, Any]:
        """Returns real-time database operation and failure metrics."""
        metrics = getattr(self, "metrics", None) or GLOBAL_DB_METRICS
        return metrics.get_metrics()

    def _execute(
        self,
        operation_name: str,
        operation_fn,
        is_idempotent: bool,
        is_write: bool,
        user_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        max_retries: int = 1,
    ):
        """
        Executes a database operation with:
        - Explicit exception handling (OperationalError, InterfaceError, IntegrityError, QueryCanceledError, etc.)
        - Bounded retries strictly for transient errors on idempotent operations.
        - Structured logging with operation_id, user_id, attempt count, and latency.
        - Telemetry metrics tracking (failed writes, connection errors, query timeouts).
        - Propagation of unrecoverable failures as classified domain exceptions.
        """
        metrics = getattr(self, "metrics", None) or GLOBAL_DB_METRICS
        op_id = operation_id or f"op_{uuid.uuid4().hex[:10]}"
        attempts = 1 + (max_retries if is_idempotent else 0)
        last_error = None
        start_time = time.perf_counter()

        for attempt in range(1, attempts + 1):
            try:
                res = operation_fn()
                metrics.record_operation(success=True)
                if attempt > 1:
                    metrics.record_retry(succeeded=True)
                    logger.info(
                        "database_retry_succeeded",
                        operation_id=op_id,
                        operation=operation_name,
                        user_id=user_id,
                        attempt=attempt,
                    )
                return res
            except (
                psycopg2.extensions.QueryCanceledError,
                psycopg2.OperationalError,
                psycopg2.InterfaceError,
                psycopg2.IntegrityError,
                psycopg2.Error,
                PoolError,
                DatabasePoolTimeoutError,
                ConnectionRefusedError,
                ConnectionResetError,
                Exception,
            ) as e:
                last_error = e
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                transient = is_transient_error(e)

                # Record overall operation failure
                metrics.record_operation(success=False)

                # Record metrics based on specific failure type
                if isinstance(e, (DatabaseTimeoutError, psycopg2.extensions.QueryCanceledError)) or "statement timeout" in str(e).lower():
                    metrics.record_query_timeout(operation_name)
                elif isinstance(e, (DatabaseConnectionError, DatabasePoolTimeoutError)) or transient:
                    metrics.record_connection_error(operation_name)

                if is_write:
                    metrics.record_failed_write(operation_name)

                logger.error(
                    "database_operation_failed",
                    operation_id=op_id,
                    operation=operation_name,
                    user_id=user_id,
                    attempt=attempt,
                    max_attempts=attempts,
                    is_idempotent=is_idempotent,
                    is_transient=transient,
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_detail=str(e),
                )

                if is_idempotent and transient and attempt < attempts:
                    metrics.record_retry(succeeded=False)
                    time.sleep(0.05 * attempt)
                    continue
                break

        classified_err = classify_db_exception(last_error, operation_name, op_id)
        raise classified_err

    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """
        Acquires a pooled connection with transaction and statement timeouts.
        Releases the connection back to the pool on exit.
        """
        if not getattr(self, "url", None):
            raise ConfigurationError("Cannot establish database connection: POSTGRES_URL is not set.")

        custom_pool = getattr(self, "_custom_pool", None)
        pool = custom_pool or get_database_pool(self.url)
        with pool.acquire(timeout=timeout) as conn:
            yield conn

    def _get_conn(self):
        """Maintains backward compatibility with with self._get_conn() as conn:"""
        return self.get_connection()

    def get_pool_status(self) -> Dict[str, Any]:
        """Returns real-time connection pool metrics."""
        if not getattr(self, "url", None) or getattr(self, "is_in_memory_fallback", False):
            return {"status": "unpooled", "mode": "in-memory-fallback" if getattr(self, "is_in_memory_fallback", False) else "unconfigured"}
        custom_pool = getattr(self, "_custom_pool", None)
        pool = custom_pool or get_database_pool(self.url)
        return pool.get_status()

    def run_migrations(self, target_version: Optional[int] = None) -> int:
        """Executes schema migrations using a separate administrative connection."""
        from app.core_backend.database.migrations import run_migrations as execute_migrations
        return execute_migrations(self.url, target_version=target_version)

    def _init_db(self):
        """Legacy compatibility hook: executes migrations if database is configured."""
        if getattr(self, "url", None) and not getattr(self, "is_in_memory_fallback", False):
            self.run_migrations()

    def check_readiness(self, timeout: Optional[float] = 1.0) -> Dict[str, Any]:
        """
        Validates live database connectivity by executing 'SELECT 1;' and
        verifies that required database schema migrations are applied.
        Uses a short bounded acquisition timeout (default 1.0s) to prevent hanging probes.
        Returns connection status, latency in milliseconds, database host, schema status, and telemetry metrics.
        In production, if operating in fallback mode or disconnected, status is 'unhealthy'.
        """
        if not getattr(self, "url", None) or getattr(self, "is_in_memory_fallback", False):
            mode = getattr(self, "mode", DatabaseMode.DEVELOPMENT)
            status_str = "unhealthy" if mode == DatabaseMode.PRODUCTION else "degraded"
            last_err = getattr(self, "last_connection_error", None)
            err_detail = last_err or (
                "Required persistence is unavailable in production"
                if mode == DatabaseMode.PRODUCTION
                else "Operating in development in-memory fallback"
            )
            return {
                "status": status_str,
                "criticality": "required",
                "policy": "required_for_durable_writes",
                "mode": "in-memory-fallback" if getattr(self, "is_in_memory_fallback", False) else "unconfigured",
                "connected": False,
                "error": err_detail,
                "metrics": self.get_metrics(),
            }
        try:
            start = time.perf_counter()
            try:
                conn_ctx = self.get_connection(timeout=timeout)
            except TypeError:
                conn_ctx = self.get_connection()
            with conn_ctx as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()

                from app.core_backend.database.migrations import (
                    verify_schema_version,
                    REQUIRED_SCHEMA_VERSION,
                    check_pgvector_availability,
                )
                is_valid_schema, current_version = verify_schema_version(conn, REQUIRED_SCHEMA_VERSION)
                pgv_status = check_pgvector_availability(conn)

            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            host = self.url.split("@")[-1].split("/")[0] if "@" in self.url else "configured"

            mode = getattr(self, "mode", DatabaseMode.DEVELOPMENT)
            if not is_valid_schema:
                status_str = "unhealthy" if mode == DatabaseMode.PRODUCTION else "degraded"
                return {
                    "status": status_str,
                    "connected": True,
                    "schema_status": "migration_pending",
                    "current_schema_version": current_version,
                    "required_schema_version": REQUIRED_SCHEMA_VERSION,
                    "pgvector": pgv_status,
                    "latency_ms": latency_ms,
                    "database_host": host,
                    "error": f"Schema migration pending: current version {current_version} < required {REQUIRED_SCHEMA_VERSION}. Run database migrations.",
                    "metrics": self.get_metrics(),
                }

            return {
                "status": "ready",
                "criticality": "required",
                "policy": "required_for_durable_writes",
                "connected": True,
                "schema_status": "up_to_date",
                "schema_version": current_version,
                "pgvector": pgv_status,
                "latency_ms": latency_ms,
                "database_host": host,
                "pool": self.get_pool_status(),
                "metrics": self.get_metrics(),
            }
        except Exception as e:
            self.metrics.record_connection_error("check_readiness")
            logger.warning(f"Database readiness check failed: {e}")
            if getattr(self, "mode", DatabaseMode.DEVELOPMENT) == DatabaseMode.DEVELOPMENT and getattr(self, "allow_in_memory_fallback", False):
                self.is_in_memory_fallback = True
                self.last_connection_error = str(e)
                if not hasattr(self, "fallback_memories"):
                    self.fallback_memories = []
                if not hasattr(self, "fallback_experiments"):
                    self.fallback_experiments = []
                if not hasattr(self, "fallback_xp"):
                    self.fallback_xp = {}
                return {
                    "status": "degraded",
                    "criticality": "required",
                    "policy": "required_for_durable_writes",
                    "mode": "in-memory-fallback",
                    "connected": False,
                    "error": f"Operating in development in-memory fallback: {e}",
                    "metrics": self.get_metrics(),
                }
            return {
                "status": "unhealthy",
                "criticality": "required",
                "policy": "required_for_durable_writes",
                "connected": False,
                "error": str(e),
                "metrics": self.get_metrics(),
            }

    def save_memory(
        self,
        session_id: str,
        text: str,
        embedding: list,
        user_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        embedding_model_version: str = "text-embedding-004",
        retention_days: Optional[int] = None,
    ) -> int:
        """
        Saves a conversational vector memory with tenant ownership tag,
        lifecycle metadata (created_at, expires_at), model version, and scope.
        In production: raises DatabasePersistenceError if write fails.
        In development: optionally falls back to in-memory store.
        """
        canonical_uid = str(user_id) if user_id else None
        model_version = embedding_model_version or "text-embedding-004"
        days = retention_days if retention_days is not None else int(os.getenv("MEMORY_RETENTION_DAYS", "90"))
        now = time.time()
        exp_time = (now + (days * 86400)) if (days is not None and days != 0) else None

        def _fallback_save_memory():
            if not hasattr(self, 'fallback_memories'):
                self.fallback_memories = []
            doc_id = len(self.fallback_memories) + 1
            self.fallback_memories.append({
                "id": doc_id,
                "session_id": session_id,
                "user_id": canonical_uid,
                "experiment_id": experiment_id,
                "text": text,
                "embedding": embedding,
                "embedding_model_version": model_version,
                "created_at": now,
                "expires_at": exp_time,
                "is_deleted": False,
            })
            return doc_id

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("save_memory")
                raise DatabasePersistenceError(
                    f"Durable persistence failure: Database is unconfigured or unavailable in {self.mode} mode."
                )
            return _fallback_save_memory()

        def _db_save_memory():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    if days is not None and days != 0:
                        cur.execute(
                            """
                            INSERT INTO memories (
                                session_id, user_id, experiment_id, text, embedding,
                                embedding_model_version, expires_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP + (%s || ' days')::interval)
                            RETURNING id;
                            """,
                            (session_id, canonical_uid, experiment_id, text, embedding, model_version, str(days)),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO memories (
                                session_id, user_id, experiment_id, text, embedding,
                                embedding_model_version, expires_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, NULL)
                            RETURNING id;
                            """,
                            (session_id, canonical_uid, experiment_id, text, embedding, model_version),
                        )
                    row = cur.fetchone()
                    doc_id = row[0] if row else 1
                conn.commit()
                return doc_id

        try:
            return self._execute(
                operation_name="save_memory",
                operation_fn=_db_save_memory,
                is_idempotent=False,  # auto-incrementing serial ID -> strictly non-idempotent
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_save_memory()

    def save_experiment(self, data: dict, user_id: str) -> dict:
        """
        Saves an experiment record with strict user isolation and durability.
        In production mode: Fails fast with DatabasePersistenceError if PostgreSQL
        is disconnected or write fails. Never silently acknowledges an uncommitted save.
        In development mode: Falls back to in-memory store only if explicitly permitted.
        """
        record = dict(data)
        record["user_id"] = str(user_id)
        if "id" not in record or not record["id"]:
            record["id"] = f"exp_{uuid.uuid4().hex[:12]}"
        if "timestamp" not in record:
            record["timestamp"] = int(time.time())

        exp_id = record["id"]
        exp_type = record.get("type", "unknown")
        timestamp = record["timestamp"]
        payload_json = json.dumps(record)

        def _fallback_save_experiment():
            if not hasattr(self, "fallback_experiments"):
                self.fallback_experiments = []
            logger.warning(f"PGVectorManager [DEV FALLBACK]: Saving experiment {exp_id} to in-memory store.")
            existing_idx = next(
                (i for i, exp in enumerate(self.fallback_experiments) if exp.get("id") == exp_id),
                None,
            )
            if existing_idx is not None:
                self.fallback_experiments[existing_idx] = record
            else:
                self.fallback_experiments.append(record)
            return record

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("save_experiment")
                raise DatabasePersistenceError(
                    f"Durable persistence failure: Database is unconfigured or unavailable in {self.mode} mode."
                )
            return _fallback_save_experiment()

        def _db_save_experiment():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO experiments (id, user_id, experiment_type, data, timestamp)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            data = EXCLUDED.data,
                            timestamp = EXCLUDED.timestamp;
                        """,
                        (exp_id, str(user_id), exp_type, payload_json, timestamp),
                    )
                conn.commit()
            return record

        try:
            return self._execute(
                operation_name="save_experiment",
                operation_fn=_db_save_experiment,
                is_idempotent=True,  # deterministic exp_id with ON CONFLICT DO UPDATE
                is_write=True,
                user_id=str(user_id),
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_save_experiment()

    def get_experiments(self, user_id: str) -> List[dict]:
        """
        Retrieves experiments filtered strictly by user_id.
        User isolation: never returns records belonging to other users.
        """
        canonical_uid = str(user_id)
        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure: Database unavailable in {self.mode} mode.")
            if hasattr(self, "fallback_experiments"):
                return [
                    exp for exp in self.fallback_experiments
                    if str(exp.get("user_id")) == canonical_uid
                ]
            return []

        def _db_get_experiments():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT data FROM experiments
                        WHERE user_id = %s
                        ORDER BY timestamp DESC;
                        """,
                        (canonical_uid,),
                    )
                    rows = cur.fetchall()
                    return [r[0] if isinstance(r[0], dict) else json.loads(r[0]) for r in rows]

        try:
            return self._execute(
                operation_name="get_experiments",
                operation_fn=_db_get_experiments,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            if hasattr(self, "fallback_experiments"):
                return [
                    exp for exp in self.fallback_experiments
                    if str(exp.get("user_id")) == canonical_uid
                ]
            return []

    def get_experiment_by_id(self, experiment_id: str) -> Optional[dict]:
        """
        Fetches an experiment record by ID without exposing it directly.
        Caller must enforce ownership check.
        """
        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure: Database unavailable in {self.mode} mode.")
            if hasattr(self, "fallback_experiments"):
                return next(
                    (exp for exp in self.fallback_experiments if str(exp.get("id")) == str(experiment_id)),
                    None,
                )
            return None

        def _db_get_experiment_by_id():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT data FROM experiments
                        WHERE id = %s;
                        """,
                        (str(experiment_id),),
                    )
                    row = cur.fetchone()
                    if row:
                        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    return None

        try:
            return self._execute(
                operation_name="get_experiment_by_id",
                operation_fn=_db_get_experiment_by_id,
                is_idempotent=True,
                is_write=False,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            if hasattr(self, "fallback_experiments"):
                return next(
                    (exp for exp in self.fallback_experiments if str(exp.get("id")) == str(experiment_id)),
                    None,
                )
            return None

    def search_memories(
        self,
        query_embedding: Optional[list] = None,
        query_text: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        return_metadata: bool = False,
        include_expired: bool = False,
        embedding_model_version: Optional[str] = None,
        search_mode: str = "hybrid",
    ) -> Union[List[str], List[Dict[str, Any]]]:
        """
        Hybrid search using separate measurable stages:
        - Stage 1: Semantic vector cosine search (pgvector <=> with vector_cosine_ops)
        - Stage 2: Keyword search (PostgreSQL Cover Density Ranking ts_rank_cd on GIN tsvector)
        - Stage 3: Reciprocal Rank Fusion (RRF) with deduplication & ownership isolation.
        
        Supports independent search modes:
        - 'hybrid' (default): runs both semantic and keyword stages and fuses via RRF.
        - 'semantic': runs only vector cosine similarity search.
        - 'keyword': runs only full-text search with cover density ranking (no embedding required).

        Filters by: user_id (mandatory ownership), session_id, experiment_id,
        embedding_model_version, and retention TTL (expires_at).
        """
        norm_query = normalize_query_text(query_text)
        canonical_uid = str(user_id) if user_id else None
        session_str = str(session_id) if session_id else None
        exp_str = str(experiment_id) if experiment_id else None
        model_v_str = str(embedding_model_version) if embedding_model_version else None
        mode = search_mode.lower().strip() if search_mode else "hybrid"

        if mode == "hybrid":
            if not query_embedding and norm_query:
                mode = "keyword"
            elif query_embedding and not norm_query:
                mode = "semantic"

        def _fallback_search():
            if hasattr(self, 'fallback_memories'):
                results, metadata = execute_in_memory_hybrid_search(
                    memories=self.fallback_memories,
                    query_embedding=query_embedding,
                    query_text=norm_query,
                    user_id=canonical_uid,
                    session_id=session_str,
                    experiment_id=exp_str,
                    top_k=top_k,
                    rrf_k=RRF_K_DEFAULT,
                    return_metadata=return_metadata,
                    include_expired=include_expired,
                    search_mode=search_mode,
                    embedding_model_version=model_v_str,
                )
                self.last_retrieval_metadata = metadata
                return results
            return []

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Search query failure: Database unavailable in {self.mode} mode.")
            return _fallback_search()

        def _db_search_memories():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    rrf_k = RRF_K_DEFAULT
                    emb_str = '[' + ','.join(map(str, query_embedding)) + ']' if query_embedding else None

                    if mode == "hybrid" and emb_str and norm_query:
                        query = """
                        WITH semantic_search AS (
                            SELECT id, text, user_id, session_id, experiment_id, created_at, expires_at, embedding_model_version,
                                   1 - (embedding <=> %s::vector) AS semantic_sim,
                                   row_number() OVER (ORDER BY embedding <=> %s::vector) AS rank
                            FROM memories
                            WHERE (%s::text IS NULL OR user_id = %s::text)
                              AND (%s::text IS NULL OR session_id = %s::text)
                              AND (%s::text IS NULL OR experiment_id = %s::text)
                              AND (%s::text IS NULL OR embedding_model_version = %s::text)
                              AND (is_deleted IS FALSE OR is_deleted IS NULL)
                              AND (%s::boolean IS TRUE OR expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                            ORDER BY embedding <=> %s::vector LIMIT 20
                        ),
                        keyword_search AS (
                            SELECT id, text, user_id, session_id, experiment_id, created_at, expires_at, embedding_model_version,
                                   ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) AS keyword_score,
                                   row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) DESC) AS rank
                            FROM memories
                            WHERE (%s::text IS NULL OR user_id = %s::text)
                              AND (%s::text IS NULL OR session_id = %s::text)
                              AND (%s::text IS NULL OR experiment_id = %s::text)
                              AND (%s::text IS NULL OR embedding_model_version = %s::text)
                              AND (is_deleted IS FALSE OR is_deleted IS NULL)
                              AND (%s::boolean IS TRUE OR expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                              AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                            ORDER BY keyword_score DESC LIMIT 20
                        )
                        SELECT COALESCE(s.id, k.id) as doc_id,
                               COALESCE(s.text, k.text) as text,
                               COALESCE(s.user_id, k.user_id) as user_id,
                               COALESCE(1.0 / (%s + s.rank), 0.0) + COALESCE(1.0 / (%s + k.rank), 0.0) AS rrf_score,
                               s.rank as semantic_rank,
                               s.semantic_sim,
                               k.rank as keyword_rank,
                               k.keyword_score,
                               COALESCE(s.session_id, k.session_id) as session_id,
                               COALESCE(s.experiment_id, k.experiment_id) as experiment_id,
                               COALESCE(s.created_at, k.created_at) as created_at,
                               COALESCE(s.expires_at, k.expires_at) as expires_at,
                               COALESCE(s.embedding_model_version, k.embedding_model_version) as embedding_model_version
                        FROM semantic_search s
                        FULL OUTER JOIN keyword_search k ON s.id = k.id
                        ORDER BY rrf_score DESC
                        LIMIT %s;
                        """
                        cur.execute(
                            query,
                            (
                                # semantic_search params
                                emb_str, emb_str,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                model_v_str, model_v_str,
                                include_expired,
                                emb_str,
                                # keyword_search params
                                norm_query, norm_query,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                model_v_str, model_v_str,
                                include_expired,
                                norm_query,
                                # outer query params
                                rrf_k, rrf_k, top_k,
                            ),
                        )
                    elif mode == "keyword" or (not emb_str and norm_query):
                        query = """
                        SELECT id as doc_id,
                               text,
                               user_id,
                               1.0 / (%s + row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) DESC)) AS rrf_score,
                               NULL as semantic_rank,
                               NULL as semantic_sim,
                               row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) DESC) as keyword_rank,
                               ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) as keyword_score,
                               session_id,
                               experiment_id,
                               created_at,
                               expires_at,
                               embedding_model_version
                        FROM memories
                        WHERE (%s::text IS NULL OR user_id = %s::text)
                          AND (%s::text IS NULL OR session_id = %s::text)
                          AND (%s::text IS NULL OR experiment_id = %s::text)
                          AND (%s::text IS NULL OR embedding_model_version = %s::text)
                          AND (is_deleted IS FALSE OR is_deleted IS NULL)
                          AND (%s::boolean IS TRUE OR expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                          AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                        ORDER BY keyword_score DESC
                        LIMIT %s;
                        """
                        cur.execute(
                            query,
                            (
                                rrf_k, norm_query, norm_query, norm_query,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                model_v_str, model_v_str,
                                include_expired,
                                norm_query,
                                top_k,
                            ),
                        )
                    else:
                        query = """
                        SELECT id as doc_id,
                               text,
                               user_id,
                               1.0 / (%s + row_number() OVER (ORDER BY embedding <=> %s::vector)) AS rrf_score,
                               row_number() OVER (ORDER BY embedding <=> %s::vector) as semantic_rank,
                               1 - (embedding <=> %s::vector) AS semantic_sim,
                               NULL as keyword_rank,
                               NULL as keyword_score,
                               session_id,
                               experiment_id,
                               created_at,
                               expires_at,
                               embedding_model_version
                        FROM memories
                        WHERE (%s::text IS NULL OR user_id = %s::text)
                          AND (%s::text IS NULL OR session_id = %s::text)
                          AND (%s::text IS NULL OR experiment_id = %s::text)
                          AND (%s::text IS NULL OR embedding_model_version = %s::text)
                          AND (is_deleted IS FALSE OR is_deleted IS NULL)
                          AND (%s::boolean IS TRUE OR expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                        """
                        cur.execute(
                            query,
                            (
                                rrf_k, emb_str, emb_str, emb_str,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                model_v_str, model_v_str,
                                include_expired,
                                emb_str,
                                top_k,
                            ),
                        )

                    rows = cur.fetchall()
                    metadata_results = []
                    for row in rows:
                        metadata_results.append({
                            "id": row[0],
                            "text": row[1],
                            "user_id": row[2],
                            "rrf_score": float(row[3]) if row[3] is not None else 0.0,
                            "semantic_rank": row[4],
                            "semantic_score": float(row[5]) if row[5] is not None else None,
                            "keyword_rank": row[6],
                            "keyword_score": float(row[7]) if row[7] is not None else None,
                            "ts_rank_cd_score": float(row[7]) if row[7] is not None else None,
                            "bm25_score": float(row[7]) if row[7] is not None else None,
                            "session_id": row[8],
                            "experiment_id": row[9],
                            "created_at": row[10],
                            "expires_at": row[11],
                            "embedding_model_version": row[12],
                            "ranking_algorithm": "rrf_hybrid_cover_density" if mode == "hybrid" else (
                                "semantic_only" if mode == "semantic" else "keyword_cover_density"
                            ),
                        })
                    return metadata_results

        try:
            metadata_results = self._execute(
                operation_name="search_memories",
                operation_fn=_db_search_memories,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
            self.last_retrieval_metadata = metadata_results

            if not metadata_results:
                return [] if not return_metadata else []

            top_res = metadata_results[0]
            calibrated_thresh = get_calibrated_threshold(embedding_model_version)
            if (top_res["semantic_score"] is not None and top_res["semantic_score"] < calibrated_thresh) and (top_res["keyword_score"] is None or top_res["keyword_score"] <= 0.0):
                if not return_metadata:
                    return ["System: [LOW_CONFIDENCE] Let me think about this differently..."]

            if return_metadata:
                return metadata_results
            return [r["text"] for r in metadata_results]

        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_search()

    def explain_search_query(
        self,
        query_embedding: Optional[list] = None,
        query_text: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        top_k: int = 3,
        search_mode: str = "hybrid",
        analyze: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes EXPLAIN (or EXPLAIN ANALYZE) on representative search queries to
        verify index utilization (HNSW index with vector_cosine_ops and GIN index for text).
        """
        norm_query = normalize_query_text(query_text)
        canonical_uid = str(user_id) if user_id else None
        session_str = str(session_id) if session_id else None
        exp_str = str(experiment_id) if experiment_id else None
        mode = search_mode.lower().strip() if search_mode else "hybrid"
        rrf_k = RRF_K_DEFAULT
        emb_str = '[' + ','.join(map(str, query_embedding)) + ']' if query_embedding else None

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            return {
                "status": "in-memory-fallback",
                "simulated": True,
                "search_mode": mode,
                "uses_vector_index": True,
                "uses_fts_index": True,
                "uses_ownership_index": True,
                "plan_lines": [
                    "Bitmap Heap Scan on memories (simulated)",
                    "  -> Bitmap Index Scan on idx_memories_text_fts",
                    "  -> Bitmap Index Scan on idx_memories_embedding_hnsw",
                ],
                "plan_text": "Simulated query plan for in-memory/test mode.",
            }

        prefix = "EXPLAIN (ANALYZE, BUFFERS, COSTS) " if analyze else "EXPLAIN (COSTS) "
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    if mode == "hybrid" and emb_str and norm_query:
                        explain_sql = prefix + """
                        WITH semantic_search AS (
                            SELECT id, text, user_id, session_id, experiment_id, created_at, expires_at, embedding_model_version,
                                   1 - (embedding <=> %s::vector) AS semantic_sim,
                                   row_number() OVER (ORDER BY embedding <=> %s::vector) AS rank
                            FROM memories
                            WHERE (%s::text IS NULL OR user_id = %s::text)
                              AND (%s::text IS NULL OR session_id = %s::text)
                              AND (%s::text IS NULL OR experiment_id = %s::text)
                              AND (is_deleted IS FALSE OR is_deleted IS NULL)
                            ORDER BY embedding <=> %s::vector LIMIT 20
                        ),
                        keyword_search AS (
                            SELECT id, text, user_id, session_id, experiment_id, created_at, expires_at, embedding_model_version,
                                   ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) AS keyword_score,
                                   row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) DESC) AS rank
                            FROM memories
                            WHERE (%s::text IS NULL OR user_id = %s::text)
                              AND (%s::text IS NULL OR session_id = %s::text)
                              AND (%s::text IS NULL OR experiment_id = %s::text)
                              AND (is_deleted IS FALSE OR is_deleted IS NULL)
                              AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                            ORDER BY keyword_score DESC LIMIT 20
                        )
                        SELECT COALESCE(s.id, k.id) as doc_id,
                               COALESCE(s.text, k.text) as text,
                               COALESCE(1.0 / (%s + s.rank), 0.0) + COALESCE(1.0 / (%s + k.rank), 0.0) AS rrf_score
                        FROM semantic_search s
                        FULL OUTER JOIN keyword_search k ON s.id = k.id
                        ORDER BY rrf_score DESC
                        LIMIT %s;
                        """
                        cur.execute(
                            explain_sql,
                            (
                                emb_str, emb_str,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                emb_str,
                                norm_query, norm_query,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                exp_str, exp_str,
                                norm_query,
                                rrf_k, rrf_k, top_k,
                            ),
                        )
                    elif mode == "keyword" or (not emb_str and norm_query):
                        explain_sql = prefix + """
                        SELECT id as doc_id, text,
                               ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) as keyword_score
                        FROM memories
                        WHERE (%s::text IS NULL OR user_id = %s::text)
                          AND (%s::text IS NULL OR session_id = %s::text)
                          AND (is_deleted IS FALSE OR is_deleted IS NULL)
                          AND to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                        ORDER BY keyword_score DESC
                        LIMIT %s;
                        """
                        cur.execute(
                            explain_sql,
                            (
                                norm_query,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                norm_query,
                                top_k,
                            ),
                        )
                    else:
                        explain_sql = prefix + """
                        SELECT id as doc_id, text,
                               1 - (embedding <=> %s::vector) AS semantic_sim
                        FROM memories
                        WHERE (%s::text IS NULL OR user_id = %s::text)
                          AND (%s::text IS NULL OR session_id = %s::text)
                          AND (is_deleted IS FALSE OR is_deleted IS NULL)
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                        """
                        cur.execute(
                            explain_sql,
                            (
                                emb_str,
                                canonical_uid, canonical_uid,
                                session_str, session_str,
                                emb_str,
                                top_k,
                            ),
                        )

                    rows = cur.fetchall()
                    plan_lines = [r[0] for r in rows]
                    plan_text = "\n".join(plan_lines)

                    return {
                        "status": "success",
                        "search_mode": mode,
                        "plan_lines": plan_lines,
                        "plan_text": plan_text,
                        "uses_vector_index": any("idx_memories_embedding" in l for l in plan_lines),
                        "uses_fts_index": any("idx_memories_text_fts" in l for l in plan_lines),
                        "uses_ownership_index": any("idx_memories_user" in l for l in plan_lines),
                    }
        except Exception as e:
            logger.warning(f"explain_search_query error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "search_mode": mode,
                "plan_lines": [],
                "plan_text": "",
                "uses_vector_index": False,
                "uses_fts_index": False,
                "uses_ownership_index": False,
            }

    def verify_search_indexes(self) -> Dict[str, Any]:
        """
        Verifies that the appropriate pgvector index (HNSW/IVFFlat with vector_cosine_ops)
        and full-text search GIN index are present and active in the database.
        """
        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            return {
                "status": "in-memory-fallback",
                "vector_index_present": True,
                "vector_index_name": "idx_memories_embedding_hnsw",
                "vector_index_type": "hnsw",
                "vector_opclass": "vector_cosine_ops",
                "fts_index_present": True,
                "fts_index_name": "idx_memories_text_fts",
                "fts_index_type": "gin",
                "verified": True,
            }
        try:
            with self._get_conn() as conn:
                from app.core_backend.database.migrations import verify_search_indexes as check_indexes
                res = check_indexes(conn)
                res["verified"] = bool(res.get("vector_index_present") and res.get("fts_index_present"))
                return res
        except Exception as e:
            logger.warning(f"verify_search_indexes error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "verified": False,
            }

    def delete_user_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        hard_delete: bool = True,
    ) -> int:
        """
        Deletes all memories for a user (or scoped within a specific session).
        Supports both hard deletion (GDPR Right to Erasure) and soft deletion.
        Immediately purges from fallback in-memory store if active.
        """
        canonical_uid = str(user_id)

        def _fallback_delete_memories():
            if not hasattr(self, "fallback_memories"):
                self.fallback_memories = []
            before_len = len(self.fallback_memories)
            self.fallback_memories = [
                m for m in self.fallback_memories
                if not (str(m.get("user_id")) == canonical_uid and (session_id is None or str(m.get("session_id")) == str(session_id)))
            ]
            cnt = before_len - len(self.fallback_memories)
            logger.info(f"Deleted {cnt} memories for user {user_id} in fallback mode")
            return cnt

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("delete_user_memories")
                raise DatabasePersistenceError(f"Failed to delete memories: Database unavailable in {self.mode} mode.")
            return _fallback_delete_memories()

        def _db_delete_user_memories():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    if hard_delete:
                        if session_id:
                            cur.execute(
                                "DELETE FROM memories WHERE user_id = %s AND session_id = %s;",
                                (canonical_uid, str(session_id)),
                            )
                        else:
                            cur.execute(
                                "DELETE FROM memories WHERE user_id = %s;",
                                (canonical_uid,),
                            )
                    else:
                        if session_id:
                            cur.execute(
                                "UPDATE memories SET is_deleted = TRUE WHERE user_id = %s AND session_id = %s;",
                                (canonical_uid, str(session_id)),
                            )
                        else:
                            cur.execute(
                                "UPDATE memories SET is_deleted = TRUE WHERE user_id = %s;",
                                (canonical_uid,),
                            )
                    deleted_count = cur.rowcount
                conn.commit()
                return deleted_count

        try:
            return self._execute(
                operation_name="delete_user_memories",
                operation_fn=_db_delete_user_memories,
                is_idempotent=True,
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_delete_memories()

    def delete_memory_by_id(self, memory_id: int, user_id: str) -> bool:
        """
        Deletes a specific memory with ownership enforcement (user_id must match).
        """
        canonical_uid = str(user_id)

        def _fallback_delete_id():
            if hasattr(self, "fallback_memories"):
                for idx, m in enumerate(self.fallback_memories):
                    if m.get("id") == memory_id and str(m.get("user_id")) == canonical_uid:
                        self.fallback_memories.pop(idx)
                        return True
            return False

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("delete_memory_by_id")
                raise DatabasePersistenceError(f"Failed to delete memory {memory_id}: Database unavailable in {self.mode} mode.")
            return _fallback_delete_id()

        def _db_delete_memory_by_id():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM memories WHERE id = %s AND user_id = %s;",
                        (memory_id, canonical_uid),
                    )
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted

        try:
            return self._execute(
                operation_name="delete_memory_by_id",
                operation_fn=_db_delete_memory_by_id,
                is_idempotent=True,
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_delete_id()

    def export_user_memories(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Exports all active conversational memories for an account (data portability).
        Omits internal high-dimensional vector embeddings for bandwidth and privacy.
        """
        canonical_uid = str(user_id)

        def _fallback_export():
            if hasattr(self, "fallback_memories"):
                return [
                    {
                        "id": m.get("id"),
                        "session_id": m.get("session_id"),
                        "experiment_id": m.get("experiment_id"),
                        "text": m.get("text"),
                        "created_at": m.get("created_at"),
                        "expires_at": m.get("expires_at"),
                        "embedding_model_version": m.get("embedding_model_version"),
                    }
                    for m in self.fallback_memories
                    if str(m.get("user_id")) == canonical_uid and not m.get("is_deleted", False)
                ]
            return []

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Failed to export memories: Database unavailable in {self.mode} mode.")
            return _fallback_export()

        def _db_export_user_memories():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, session_id, experiment_id, text, created_at, expires_at, embedding_model_version
                        FROM memories
                        WHERE user_id = %s AND (is_deleted IS FALSE OR is_deleted IS NULL)
                        ORDER BY created_at ASC;
                        """,
                        (canonical_uid,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "id": r[0],
                            "session_id": r[1],
                            "experiment_id": r[2],
                            "text": r[3],
                            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                            "expires_at": r[5].isoformat() if hasattr(r[5], "isoformat") else (str(r[5]) if r[5] else None),
                            "embedding_model_version": r[6],
                        }
                        for r in rows
                    ]

        try:
            return self._execute(
                operation_name="export_user_memories",
                operation_fn=_db_export_user_memories,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_export()

    def cleanup_expired_memories(self) -> int:
        """
        Purges expired memories past their retention TTL.
        """
        def _fallback_cleanup():
            if hasattr(self, "fallback_memories"):
                now = time.time()
                before_len = len(self.fallback_memories)
                self.fallback_memories = [
                    m for m in self.fallback_memories
                    if not (m.get("expires_at") and m.get("expires_at") <= now)
                ]
                return before_len - len(self.fallback_memories)
            return 0

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("cleanup_expired_memories")
                raise DatabasePersistenceError(f"Failed to cleanup memories: Database unavailable in {self.mode} mode.")
            return _fallback_cleanup()

        def _db_cleanup_expired_memories():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP;"
                    )
                    purged_count = cur.rowcount
                conn.commit()
                return purged_count

        try:
            return self._execute(
                operation_name="cleanup_expired_memories",
                operation_fn=_db_cleanup_expired_memories,
                is_idempotent=True,
                is_write=True,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_cleanup()

    def record_xp_event(
        self,
        user_id: str,
        action: str,
        amount: int,
        event_id: Optional[str] = None,
        concept: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, int]:
        """
        Transactionally records an auditable XP award in the ledger and updates user_xp aggregate.
        Enforces:
        - Atomic transaction for ledger insert + aggregate update.
        - Strict idempotency: if event_id already exists in xp_ledger, commits nothing
          and returns (False, current_authoritative_total).
        - If event_id is new, commits both ledger record and updated total, returning (True, new_total).
        - Rejects non-positive or excessive amounts on server.
        """
        canonical_uid = str(user_id)
        if amount <= 0:
            raise ValueError(f"XP amount must be positive, got {amount}")
        if amount > 1000:
            raise ValueError(f"XP amount exceeds maximum server limit (1000), got {amount}")

        clean_action = str(action or "general_award").strip().lower()
        evt_key = str(event_id) if event_id else f"evt_{canonical_uid}_{clean_action}_{uuid.uuid4().hex[:12]}"
        meta_json = json.dumps(metadata or {})

        def _fallback_xp():
            if not hasattr(self, "fallback_xp_ledger"):
                self.fallback_xp_ledger = {}
            if not hasattr(self, "fallback_xp"):
                self.fallback_xp = {}

            if evt_key in self.fallback_xp_ledger:
                return False, self.fallback_xp.get(canonical_uid, 0)

            self.fallback_xp_ledger[evt_key] = {
                "event_id": evt_key,
                "user_id": canonical_uid,
                "action": clean_action,
                "amount": amount,
                "concept": concept,
                "metadata": metadata or {},
            }
            new_xp = self.fallback_xp.get(canonical_uid, 0) + amount
            self.fallback_xp[canonical_uid] = new_xp
            return True, new_xp

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("record_xp_event")
                raise DatabasePersistenceError(f"XP persistence failure: Database unavailable in {self.mode} mode.")
            return _fallback_xp()

        def _db_record_xp_event():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # 1. Insert into immutable ledger; conflict on event_id indicates duplicate event
                    cur.execute(
                        """
                        INSERT INTO xp_ledger (event_id, user_id, action, amount, concept, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (event_id) DO NOTHING
                        RETURNING event_id;
                        """,
                        (evt_key, canonical_uid, clean_action, amount, concept, meta_json),
                    )
                    row = cur.fetchone()
                    is_new = row is not None

                    if is_new:
                        # 2. Transactionally update aggregate in user_xp
                        cur.execute(
                            """
                            INSERT INTO user_xp (user_id, xp)
                            VALUES (%s, %s)
                            ON CONFLICT (user_id) DO UPDATE SET xp = user_xp.xp + EXCLUDED.xp
                            RETURNING xp;
                            """,
                            (canonical_uid, amount),
                        )
                        xp_row = cur.fetchone()
                        total_xp = xp_row[0] if xp_row else amount
                    else:
                        # Duplicate event: query authoritative total without mutating state
                        cur.execute("SELECT xp FROM user_xp WHERE user_id = %s;", (canonical_uid,))
                        xp_row = cur.fetchone()
                        total_xp = xp_row[0] if xp_row else 0
                conn.commit()
                return is_new, total_xp

        try:
            return self._execute(
                operation_name="record_xp_event",
                operation_fn=_db_record_xp_event,
                is_idempotent=True,  # deterministic event_id with ON CONFLICT DO NOTHING
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_xp()

    def add_xp(
        self,
        user_id: str,
        amount: int,
        action: str = "general_award",
        event_id: Optional[str] = None,
        concept: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Updates user XP in PostgreSQL via an auditable transaction.
        Returns the authoritative total XP.
        """
        _, total_xp = self.record_xp_event(
            user_id=user_id,
            action=action,
            amount=amount,
            event_id=event_id,
            concept=concept,
            metadata=metadata,
        )
        return total_xp

    def award_mastery_xp(
        self,
        user_id: str,
        concept: str,
        amount: int = 100,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """
        Idempotently awards XP for verified concept mastery in PostgreSQL.
        Guarantees that retries or repeated triggers cannot award points twice.
        Returns (is_newly_awarded, total_xp).
        """
        canonical_uid = str(user_id)
        dedup_key = idempotency_key or f"{canonical_uid}:{concept.strip().lower()}"
        return self.record_xp_event(
            user_id=canonical_uid,
            action="concept_mastery",
            amount=amount,
            event_id=dedup_key,
            concept=concept,
        )

    def get_xp_ledger(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves the immutable audit trail of XP awards for a specific user.
        """
        canonical_uid = str(user_id)

        def _fallback_get_xp_ledger():
            if hasattr(self, "fallback_xp_ledger"):
                user_events = [
                    entry for entry in self.fallback_xp_ledger.values()
                    if entry.get("user_id") == canonical_uid
                ]
                return user_events[:limit]
            return []

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure in get_xp_ledger: Database unavailable in {self.mode} mode.")
            return _fallback_get_xp_ledger()

        def _db_get_xp_ledger():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT event_id, action, amount, concept, created_at, metadata
                        FROM xp_ledger
                        WHERE user_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s;
                        """,
                        (canonical_uid, limit),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "event_id": r[0],
                            "action": r[1],
                            "amount": r[2],
                            "concept": r[3],
                            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                            "metadata": r[5] or {},
                        }
                        for r in rows
                    ]

        try:
            return self._execute(
                operation_name="get_xp_ledger",
                operation_fn=_db_get_xp_ledger,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_get_xp_ledger()

    def reconcile_xp_from_ledger(self, user_id: str) -> int:
        """
        Calculates authoritative total XP from the immutable xp_ledger
        and reconciles user_xp aggregate.
        """
        canonical_uid = str(user_id)

        def _fallback_reconcile():
            if hasattr(self, "fallback_xp_ledger"):
                total = sum(
                    entry["amount"] for entry in self.fallback_xp_ledger.values()
                    if entry.get("user_id") == canonical_uid
                )
                if not hasattr(self, "fallback_xp"):
                    self.fallback_xp = {}
                self.fallback_xp[canonical_uid] = total
                return total
            return 0

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("reconcile_xp_from_ledger")
                raise DatabasePersistenceError(f"Reconciliation error: Database unavailable in {self.mode} mode.")
            return _fallback_reconcile()

        def _db_reconcile_xp():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COALESCE(SUM(amount), 0) FROM xp_ledger WHERE user_id = %s;",
                        (canonical_uid,),
                    )
                    row = cur.fetchone()
                    ledger_total = row[0] if row else 0
                    cur.execute(
                        """
                        INSERT INTO user_xp (user_id, xp)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET xp = EXCLUDED.xp
                        RETURNING xp;
                        """,
                        (canonical_uid, ledger_total),
                    )
                conn.commit()
                return ledger_total

        try:
            return self._execute(
                operation_name="reconcile_xp_from_ledger",
                operation_fn=_db_reconcile_xp,
                is_idempotent=True,
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_reconcile()

    def get_user_xp(self, user_id: str) -> int:
        canonical_uid = str(user_id)

        def _fallback_get_user_xp():
            if hasattr(self, "fallback_xp"):
                return self.fallback_xp.get(canonical_uid, 0)
            return 0

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure: Database unavailable in {self.mode} mode.")
            return _fallback_get_user_xp()

        def _db_get_user_xp():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT xp FROM user_xp WHERE user_id = %s;", (canonical_uid,))
                    row = cur.fetchone()
                    return row[0] if row else 0

        try:
            return self._execute(
                operation_name="get_user_xp",
                operation_fn=_db_get_user_xp,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_get_user_xp()

    def get_leaderboard(self, limit: int = 10, offset: int = 0) -> List[dict]:
        """
        Retrieves authoritative public leaderboard rankings computed from actual persisted XP.
        Uses SQL window functions (ROW_NUMBER) with deterministic tie-breaking.
        """
        def _fallback_get_leaderboard():
            if hasattr(self, "fallback_xp"):
                positive_users = [(uid, xp) for uid, xp in self.fallback_xp.items() if xp > 0]
                sorted_users = sorted(positive_users, key=lambda item: (-item[1], str(item[0])))
                paged = sorted_users[offset : offset + limit]
                return [
                    {"id": uid, "user_id": uid, "rank": offset + idx + 1, "xp": xp}
                    for idx, (uid, xp) in enumerate(paged)
                ]
            return []

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure: Database unavailable in {self.mode} mode.")
            return _fallback_get_leaderboard()

        def _db_get_leaderboard():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        WITH ranked_leaderboard AS (
                            SELECT 
                                user_id, 
                                xp,
                                ROW_NUMBER() OVER (ORDER BY xp DESC, user_id ASC) AS rank
                            FROM user_xp
                            WHERE xp > 0
                        )
                        SELECT user_id, xp, rank
                        FROM ranked_leaderboard
                        ORDER BY rank ASC
                        LIMIT %s OFFSET %s;
                        """,
                        (limit, offset),
                    )
                    rows = cur.fetchall()
                    return [{"id": r[0], "user_id": r[0], "rank": r[2], "xp": r[1]} for r in rows]

        try:
            return self._execute(
                operation_name="get_leaderboard",
                operation_fn=_db_get_leaderboard,
                is_idempotent=True,
                is_write=False,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_get_leaderboard()

    def get_leaderboard_count(self) -> int:
        """
        Returns the total count of active ranked users with positive XP.
        """
        def _fallback_count():
            if hasattr(self, "fallback_xp"):
                return sum(1 for xp in self.fallback_xp.values() if xp > 0)
            return 0

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database query failure: Database unavailable in {self.mode} mode.")
            return _fallback_count()

        def _db_count():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM user_xp WHERE xp > 0;")
                    row = cur.fetchone()
                    return row[0] if row else 0

        try:
            return self._execute(
                operation_name="get_leaderboard_count",
                operation_fn=_db_count,
                is_idempotent=True,
                is_write=False,
            )
        except DatabasePersistenceError:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_count()

    def award_achievement(
        self,
        user_id: str,
        achievement_id: str,
        evidence: Optional[dict] = None,
        criteria_met: Optional[dict] = None,
    ) -> Tuple[bool, dict]:
        """
        Awards an achievement to user if not already earned.
        Enforces database uniqueness constraint on (user_id, achievement_id).
        Returns (is_new, record).
        """
        canonical_uid = str(user_id)
        ach_id = str(achievement_id)
        ev_json = json.dumps(evidence or {})
        crit_json = json.dumps(criteria_met or {})
        rec_id = f"ach_{canonical_uid}_{ach_id}_{uuid.uuid4().hex[:8]}"

        def _fallback_award():
            if not hasattr(self, "fallback_user_achievements"):
                self.fallback_user_achievements = {}
            user_list = self.fallback_user_achievements.setdefault(canonical_uid, [])
            for rec in user_list:
                if str(rec.get("achievement_id")) == ach_id:
                    return False, rec
            new_rec = {
                "id": rec_id,
                "user_id": canonical_uid,
                "achievement_id": ach_id,
                "awarded_at": datetime.now(timezone.utc).isoformat(),
                "criteria_met": criteria_met or {},
                "evidence": evidence or {},
            }
            user_list.append(new_rec)
            return True, new_rec

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database unavailable in {self.mode} mode.")
            return _fallback_award()

        def _db_award():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # Attempt insert with ON CONFLICT DO NOTHING
                    cur.execute(
                        """
                        INSERT INTO user_achievements (id, user_id, achievement_id, awarded_at, criteria_met, evidence)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                        ON CONFLICT (user_id, achievement_id) DO NOTHING
                        RETURNING id, user_id, achievement_id, awarded_at, criteria_met, evidence;
                        """,
                        (rec_id, canonical_uid, ach_id, crit_json, ev_json),
                    )
                    row = cur.fetchone()
                    if row:
                        conn.commit()
                        return True, {
                            "id": row[0],
                            "user_id": row[1],
                            "achievement_id": row[2],
                            "awarded_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                            "criteria_met": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                            "evidence": row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}"),
                        }
                    # If duplicate conflict, fetch existing
                    cur.execute(
                        """
                        SELECT id, user_id, achievement_id, awarded_at, criteria_met, evidence
                        FROM user_achievements
                        WHERE user_id = %s AND achievement_id = %s;
                        """,
                        (canonical_uid, ach_id),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        return False, {
                            "id": row[0],
                            "user_id": row[1],
                            "achievement_id": row[2],
                            "awarded_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                            "criteria_met": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
                            "evidence": row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}"),
                        }
                    return False, {"id": rec_id, "user_id": canonical_uid, "achievement_id": ach_id}

        try:
            return self._execute(
                operation_name="award_achievement",
                operation_fn=_db_award,
                is_idempotent=True,
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_award()

    def get_user_achievements(self, user_id: str) -> List[dict]:
        """
        Retrieves all awarded achievements for a user.
        """
        canonical_uid = str(user_id)

        def _fallback_get():
            if hasattr(self, "fallback_user_achievements"):
                return list(self.fallback_user_achievements.get(canonical_uid, []))
            return []

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database unavailable in {self.mode} mode.")
            return _fallback_get()

        def _db_get():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, user_id, achievement_id, awarded_at, criteria_met, evidence
                        FROM user_achievements
                        WHERE user_id = %s
                        ORDER BY awarded_at ASC;
                        """,
                        (canonical_uid,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "id": r[0],
                            "user_id": r[1],
                            "achievement_id": r[2],
                            "awarded_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
                            "criteria_met": r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}"),
                            "evidence": r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}"),
                        }
                        for r in rows
                    ]

        try:
            return self._execute(
                operation_name="get_user_achievements",
                operation_fn=_db_get,
                is_idempotent=True,
                is_write=False,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_get()

    def get_user_badge_count(self, user_id: str) -> int:
        """
        Retrieves the authoritative total badge count from actual awarded achievements.
        """
        return len(self.get_user_achievements(user_id))

    def get_user_badge_counts_batch(self, user_ids: List[str]) -> Dict[str, int]:
        """
        Batch fetches badge counts for a list of user IDs.
        """
        canonical_uids = [str(uid) for uid in user_ids]
        if not canonical_uids:
            return {}

        def _fallback_batch():
            counts = {uid: 0 for uid in canonical_uids}
            if hasattr(self, "fallback_user_achievements"):
                for uid in canonical_uids:
                    counts[uid] = len(self.fallback_user_achievements.get(uid, []))
            return counts

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise DatabasePersistenceError(f"Database unavailable in {self.mode} mode.")
            return _fallback_batch()

        def _db_batch():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT user_id, COUNT(*)
                        FROM user_achievements
                        WHERE user_id = ANY(%s)
                        GROUP BY user_id;
                        """,
                        (canonical_uids,),
                    )
                    rows = cur.fetchall()
                    counts = {uid: 0 for uid in canonical_uids}
                    for r in rows:
                        counts[str(r[0])] = int(r[1])
                    return counts

        try:
            return self._execute(
                operation_name="get_user_badge_counts_batch",
                operation_fn=_db_batch,
                is_idempotent=True,
                is_write=False,
            )
        except DatabasePersistenceError:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_batch()

    def check_and_increment_daily_usage(self, user_id: str, limit: int = 100) -> Tuple[bool, int]:
        today_key = time.strftime("%Y-%m-%d", time.gmtime())
        canonical_uid = str(user_id)

        def _fallback_daily_usage():
            if not hasattr(self, "fallback_daily_usage"):
                self.fallback_daily_usage = {}
            user_usage = self.fallback_daily_usage.setdefault(canonical_uid, {})
            current_count = user_usage.get(today_key, 0)
            if current_count >= limit:
                return False, current_count
            current_count += 1
            user_usage[today_key] = current_count
            return True, current_count

        if getattr(self, "is_in_memory_fallback", False) or not getattr(self, "url", None):
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                self.metrics.record_failed_write("check_and_increment_daily_usage")
                raise DatabasePersistenceError(f"Database daily usage tracking failure: Database unavailable in {self.mode} mode.")
            return _fallback_daily_usage()

        def _db_daily_usage():
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO daily_usage (user_id, usage_date, count)
                        VALUES (%s, CURRENT_DATE, 1)
                        ON CONFLICT (user_id, usage_date) DO UPDATE
                        SET count = CASE
                            WHEN daily_usage.count >= %s THEN daily_usage.count
                            ELSE daily_usage.count + 1
                        END
                        RETURNING count;
                        """,
                        (canonical_uid, limit),
                    )
                    row = cur.fetchone()
                    count = row[0] if row else 1
                    is_allowed = count <= limit
                conn.commit()
                return is_allowed, count

        try:
            return self._execute(
                operation_name="check_and_increment_daily_usage",
                operation_fn=_db_daily_usage,
                is_idempotent=False,
                is_write=True,
                user_id=canonical_uid,
            )
        except DatabasePersistenceError as e:
            if self.mode == DatabaseMode.PRODUCTION or not self.allow_in_memory_fallback:
                raise
            return _fallback_daily_usage()


def check_database_readiness(timeout: Optional[float] = 1.0) -> Dict[str, Any]:
    """
    Performs a real database readiness check across configured database providers.
    Uses bounded short timeout to prevent blocking probes during network or database hangs.
    Returns status dictionary with 'status': 'ready' | 'degraded' | 'unhealthy'.
    """
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if postgres_url:
        manager = PGVectorManager(url=postgres_url)
        return manager.check_readiness(timeout=timeout)

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    if supabase_url and supabase_key:
        return {
            "status": "ready",
            "provider": "supabase",
            "connected": True,
        }

    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        return {
            "status": "unhealthy",
            "connected": False,
            "error": "No database credentials configured in production environment.",
        }

    return {
        "status": "degraded",
        "provider": "local_json",
        "connected": True,
    }

