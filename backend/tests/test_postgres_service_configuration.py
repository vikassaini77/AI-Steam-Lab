import os
import yaml
import pytest
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

load_dotenv("backend/.env")
if not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "mock-test-gemini-api-key"

from fastapi.testclient import TestClient
from app.main import app, validate_production_configuration
from app.core_backend.database.pgvector_db import (
    get_database_url,
    is_container_environment,
    check_database_readiness,
    PGVectorManager,
    ConfigurationError,
)
from app.core_backend.database.migrations import REQUIRED_SCHEMA_VERSION
from app.worker import check_worker_db_connectivity

client = TestClient(app)


def test_docker_compose_postgres_url_and_service_wiring():
    """
    Verification:
    1. Compose PostgreSQL service is named 'db' on port 5432 with pgvector image.
    2. 'backend' explicitly receives POSTGRES_URL: ${POSTGRES_URL:?...}.
    3. 'celery_worker' explicitly receives POSTGRES_URL: ${POSTGRES_URL:?...}.
    4. 'backend' and 'celery_worker' depend on db healthcheck.
    """
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    services = compose_cfg.get("services", {})
    assert "db" in services, "Compose configuration missing 'db' service"
    assert "backend" in services, "Compose configuration missing 'backend' service"
    assert "celery_worker" in services, "Compose configuration missing 'celery_worker' service"

    # 1. db service assertions
    db_svc = services["db"]
    assert "pgvector/pgvector" in db_svc["image"]
    assert "5432" in str(db_svc.get("expose", []))
    assert "healthcheck" in db_svc
    assert "pg_isready" in str(db_svc["healthcheck"].get("test", []))

    # 2. backend service assertions
    backend_svc = services["backend"]
    backend_env = backend_svc.get("environment", [])
    postgres_env = next((e for e in backend_env if e.startswith("POSTGRES_URL=")), None)
    assert postgres_env is not None, "backend service missing explicit POSTGRES_URL"
    assert "${POSTGRES_URL:" in postgres_env, "POSTGRES_URL must fail fast if unset"
    assert "@db:5432/" in postgres_env, "POSTGRES_URL default must point to db:5432"

    backend_deps = backend_svc.get("depends_on", {})
    assert "db" in backend_deps
    assert backend_deps["db"].get("condition") == "service_healthy"

    # 3. celery_worker service assertions
    worker_svc = services["celery_worker"]
    worker_env = worker_svc.get("environment", [])
    worker_pg_env = next((e for e in worker_env if e.startswith("POSTGRES_URL=")), None)
    assert worker_pg_env is not None, "celery_worker service missing explicit POSTGRES_URL"
    assert "${POSTGRES_URL:" in worker_pg_env, "celery_worker POSTGRES_URL must fail fast if unset"
    assert "@db:5432/" in worker_pg_env, "celery_worker POSTGRES_URL default must point to db:5432"

    worker_deps = worker_svc.get("depends_on", {})
    assert "db" in worker_deps
    assert worker_deps["db"].get("condition") == "service_healthy"


def test_render_yaml_cloud_configuration():
    """
    Verification:
    1. Managed database 'stemlab-db' defined.
    2. 'stemlab-backend' wires POSTGRES_URL fromDatabase stemlab-db (DATABASE_URL).
    3. 'stemlab-worker' wires POSTGRES_URL fromDatabase stemlab-db (DATABASE_URL).
    4. healthCheckPath set to /ready.
    """
    with open("render.yaml", "r", encoding="utf-8") as f:
        render_cfg = yaml.safe_load(f)

    databases = render_cfg.get("databases", [])
    db_names = [d.get("name") for d in databases]
    assert "stemlab-db" in db_names

    services = render_cfg.get("services", [])
    backend_svc = next((s for s in services if s.get("name") == "stemlab-backend"), None)
    assert backend_svc is not None
    assert backend_svc.get("healthCheckPath") == "/ready"

    # Verify backend envVars
    backend_vars = backend_svc.get("envVars", [])
    pg_var = next((v for v in backend_vars if v.get("key") == "POSTGRES_URL"), None)
    assert pg_var is not None
    assert pg_var.get("fromDatabase", {}).get("name") == "stemlab-db"
    assert pg_var.get("fromDatabase", {}).get("envVarKey") == "DATABASE_URL"

    # Verify worker envVars
    worker_svc = next((s for s in services if s.get("name") == "stemlab-worker"), None)
    assert worker_svc is not None
    worker_vars = worker_svc.get("envVars", [])
    worker_pg_var = next((v for v in worker_vars if v.get("key") == "POSTGRES_URL"), None)
    assert worker_pg_var is not None
    assert worker_pg_var.get("fromDatabase", {}).get("name") == "stemlab-db"


def test_container_environment_rejects_localhost_postgres_url(monkeypatch):
    """
    Verification:
    When running in a container, 'localhost:5432' refers to the container itself,
    not the PostgreSQL service container. get_database_url() must reject this.
    """
    monkeypatch.setenv("IS_CONTAINER", "true")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app_user:secret_pass@localhost:5432/stemlab")

    assert is_container_environment() is True
    with pytest.raises(ConfigurationError) as exc_info:
        get_database_url()

    err_msg = str(exc_info.value)
    assert "localhost" in err_msg
    assert "db:5432" in err_msg


def test_host_environment_accepts_localhost_postgres_url(monkeypatch):
    """
    Verification:
    When running directly on the developer host machine (outside container),
    'localhost:5432' is valid and accepted.
    """
    monkeypatch.setenv("IS_CONTAINER", "false")
    monkeypatch.delenv("DOCKER_CONTAINER", raising=False)
    # Ensure /.dockerenv is not detected
    monkeypatch.setattr("os.path.exists", lambda path: False if ".dockerenv" in path else os.path.exists(path))

    host_url = "postgresql://stemlab_app:strong_host_pass@localhost:5432/stemlab"
    monkeypatch.setenv("POSTGRES_URL", host_url)

    assert get_database_url() == host_url


def test_production_startup_fails_when_container_uses_localhost(monkeypatch):
    """
    Verification:
    Production startup validation rejects localhost inside container environments.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("IS_CONTAINER", "true")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app_user:secret_pass@localhost:5432/stemlab")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()

    assert "localhost" in str(exc_info.value)
    assert "db:5432" in str(exc_info.value)


def test_pgvector_manager_check_readiness_healthy():
    """
    Verification:
    check_readiness() executes 'SELECT 1;' and returns ready status with latency.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (REQUIRED_SCHEMA_VERSION,)
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg2.connect", return_value=mock_conn):
        manager = PGVectorManager(url="postgresql://app_user:secret_pass@db:5432/stemlab")
        readiness = manager.check_readiness()

    assert readiness["status"] == "ready"
    assert readiness["connected"] is True
    assert readiness["latency_ms"] >= 0.0
    assert readiness["database_host"] == "db:5432"
    mock_cursor.execute.assert_any_call("SELECT 1;")


def test_pgvector_manager_check_readiness_unhealthy():
    """
    Verification:
    When database connection fails, check_readiness() returns unhealthy status with masked error.
    """
    with patch("psycopg2.connect", side_effect=Exception("could not connect to server at db:5432: Connection refused")):
        # In development, constructor falls back to in-memory mode without crashing
        manager = PGVectorManager(url="postgresql://app_user:secret_pass@db:5432/stemlab")
        readiness = manager.check_readiness()

    assert readiness["status"] in ("unhealthy", "degraded")
    assert readiness["connected"] is False
    assert "could not connect" in readiness["error"]


def test_celery_worker_db_connectivity_task():
    """
    Verification:
    Celery worker can invoke check_worker_db_connectivity to verify database reachability.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (REQUIRED_SCHEMA_VERSION,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg2.connect", return_value=mock_conn):
        with patch.dict(os.environ, {"POSTGRES_URL": "postgresql://worker:secret@db:5432/stemlab"}):
            result = check_worker_db_connectivity()

    assert result["status"] == "ready"
    assert result["connected"] is True
    assert result["database_host"] == "db:5432"


def test_readiness_endpoint_http():
    """
    Verification:
    /ready endpoint returns:
    - 200 OK when database is reachable.
    - 503 Service Unavailable when database check fails in production.
    """
    # 1. Healthy database probe
    with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "ready", "connected": True}):
        res = client.get("/ready")
        assert res.status_code == 200
        assert res.json()["status"] == "ready"

    # 2. Unhealthy database probe
    with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "unhealthy", "connected": False, "error": "Connection refused"}):
        res = client.get("/ready")
        assert res.status_code == 503
        assert res.json()["status"] == "unhealthy"


def test_env_example_documentation_contains_canonical_urls():
    """
    Verification:
    Both root .env.example and backend/.env.example explicitly specify db:5432 for Compose.
    """
    for path in [".env.example", "backend/.env.example"]:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "@db:5432/" in content, f"{path} must document canonical db:5432 hostname for Compose"
