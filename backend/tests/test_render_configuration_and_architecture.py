"""
Unit and Integration Tests for Problem 34:
Render Configuration and Multi-Service Architecture Verification
Verifies:
1. render.yaml declarative deployment spec defines backend (web), Celery worker, Redis, and PostgreSQL.
2. PostgreSQL service configuration specifies PostgreSQL 16 and access restrictions.
3. Database and Redis configuration parity between stemlab-backend and stemlab-worker.
4. preDeployCommand executes database schema migrations before live traffic.
5. pgvector extension availability checks and graceful conditional migrations.
6. get_database_url() normalizes postgres:// to postgresql:// and supports DATABASE_URL from Render.
7. Server-Sent Events (SSE) streaming responses include required proxy bypass headers:
   X-Accel-Buffering: no, Cache-Control: no-cache, no-transform, Connection: keep-alive.
"""
import os
import yaml
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.core_backend.database.pgvector_db import (
    get_database_url,
    ConfigurationError,
    PGVectorManager,
    DatabaseMode,
)
from app.core_backend.database.migrations import (
    check_pgvector_availability,
    MIGRATION_V1_SQL,
    MIGRATION_V3_SQL,
)
from app.worker import celery_app, check_worker_db_connectivity


def get_render_config() -> dict:
    repo_root = Path(__file__).resolve().parent.parent.parent
    render_yaml_path = repo_root / "render.yaml"
    assert render_yaml_path.exists(), f"render.yaml not found at {render_yaml_path}"
    with open(render_yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRenderConfiguration:
    """Verifies render.yaml architecture conforms to multi-service production requirements."""

    def test_render_services_defined(self):
        cfg = get_render_config()
        services = cfg.get("services", [])
        service_types = {s["name"]: s["type"] for s in services}

        assert "stemlab-backend" in service_types, "stemlab-backend web service must be defined in render.yaml"
        assert service_types["stemlab-backend"] == "web"

        assert "stemlab-worker" in service_types, "stemlab-worker service must be defined for Celery background tasks"
        assert service_types["stemlab-worker"] == "worker"

        assert "stemlab-redis" in service_types, "stemlab-redis service must be defined for cache and task broker"
        assert service_types["stemlab-redis"] == "redis"

    def test_render_database_specification(self):
        cfg = get_render_config()
        databases = cfg.get("databases", [])
        assert len(databases) >= 1, "At least one managed database must be declared in render.yaml"

        db = next((d for d in databases if d["name"] == "stemlab-db"), None)
        assert db is not None, "stemlab-db managed PostgreSQL database must be defined"
        assert db.get("databaseName") == "stemlab"
        assert db.get("user") == "neurolab_app"
        assert db.get("postgresMajorVersion") == 16, "PostgreSQL 16 is required for native pgvector support"
        assert "ipAllowList" in db, "ipAllowList must be configured to restrict unauthorized network access"

    def test_pre_deploy_migrations_configured(self):
        cfg = get_render_config()
        backend = next(s for s in cfg["services"] if s["name"] == "stemlab-backend")
        pre_deploy = backend.get("preDeployCommand")
        assert pre_deploy is not None, "preDeployCommand must be configured on stemlab-backend"
        assert "app.core_backend.database.migrations" in pre_deploy, (
            f"preDeployCommand must execute schema migrations: got '{pre_deploy}'"
        )

    def test_docker_context_configured_for_backend_and_worker(self):
        cfg = get_render_config()
        for name in ("stemlab-backend", "stemlab-worker"):
            svc = next(s for s in cfg["services"] if s["name"] == name)
            assert svc.get("env") == "docker"
            assert svc.get("dockerContext") == "./backend", (
                f"{name} must specify dockerContext: ./backend so Dockerfile COPY commands resolve properly"
            )
            assert "Dockerfile" in svc.get("dockerfilePath", "")

    def test_celery_worker_command_specified(self):
        cfg = get_render_config()
        worker = next(s for s in cfg["services"] if s["name"] == "stemlab-worker")
        cmd = worker.get("dockerCommand", "")
        assert "celery" in cmd and "app.worker.celery_app" in cmd, (
            f"Celery worker command must invoke app.worker.celery_app: got '{cmd}'"
        )

    def test_backend_and_worker_config_parity(self):
        """Verifies both web backend and Celery worker receive identical database and Redis configuration."""
        cfg = get_render_config()
        backend = next(s for s in cfg["services"] if s["name"] == "stemlab-backend")
        worker = next(s for s in cfg["services"] if s["name"] == "stemlab-worker")

        backend_env = {v["key"]: v for v in backend.get("envVars", [])}
        worker_env = {v["key"]: v for v in worker.get("envVars", [])}

        # Check PostgreSQL injection
        assert "POSTGRES_URL" in backend_env, "POSTGRES_URL must be supplied to backend"
        assert "POSTGRES_URL" in worker_env, "POSTGRES_URL must be supplied to worker"
        assert backend_env["POSTGRES_URL"].get("fromDatabase", {}).get("name") == "stemlab-db"
        assert worker_env["POSTGRES_URL"].get("fromDatabase", {}).get("name") == "stemlab-db"

        # Check DATABASE_URL injection for standard Render compatibility
        assert "DATABASE_URL" in backend_env, "DATABASE_URL must be supplied to backend"
        assert "DATABASE_URL" in worker_env, "DATABASE_URL must be supplied to worker"

        # Check Redis injection
        assert "REDIS_URL" in backend_env, "REDIS_URL must be supplied to backend"
        assert "REDIS_URL" in worker_env, "REDIS_URL must be supplied to worker"
        assert backend_env["REDIS_URL"].get("fromService", {}).get("name") == "stemlab-redis"
        assert worker_env["REDIS_URL"].get("fromService", {}).get("name") == "stemlab-redis"

        # Check Environment
        assert backend_env.get("ENVIRONMENT", {}).get("value") == "production"
        assert worker_env.get("ENVIRONMENT", {}).get("value") == "production"
        assert backend_env.get("IS_CONTAINER", {}).get("value") == "true"
        assert worker_env.get("IS_CONTAINER", {}).get("value") == "true"


class TestDatabaseUrlHandling:
    """Verifies get_database_url supports POSTGRES_URL, DATABASE_URL, and normalizes postgres:// schemes."""

    def test_resolves_postgres_url_when_set(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_URL", "postgresql://app_user:s3cr3t@db.example.com:5432/app_db")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = get_database_url()
        assert url == "postgresql://app_user:s3cr3t@db.example.com:5432/app_db"

    def test_falls_back_to_database_url_from_render(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://render_user:pass@dpg-abc.render.com:5432/stemlab")
        url = get_database_url()
        assert url == "postgresql://render_user:pass@dpg-abc.render.com:5432/stemlab"

    def test_normalizes_postgres_scheme_to_postgresql(self, monkeypatch):
        # Render and Heroku frequently provide postgres:// URLs
        monkeypatch.delenv("POSTGRES_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgres://render_user:securepass@dpg-xyz.render.com:5432/stemlab")
        url = get_database_url()
        assert url.startswith("postgresql://")
        assert "postgres://" not in url[:12]
        assert url == "postgresql://render_user:securepass@dpg-xyz.render.com:5432/stemlab"

    def test_fails_fast_when_neither_postgres_nor_database_url_configured(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ConfigurationError) as exc_info:
            get_database_url()
        assert "POSTGRES_URL must be configured" in str(exc_info.value)

    def test_rejects_insecure_default_credentials(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_URL", "postgresql://postgres:postgres@remote-host:5432/stemlab")
        with pytest.raises(ConfigurationError) as exc_info:
            get_database_url()
        assert "Hardcoded default credentials 'postgres:postgres' are strictly prohibited" in str(exc_info.value)


class TestPgVectorAvailabilityAndMigration:
    """Verifies pgvector extension availability checks and conditional migration handling."""

    def test_check_pgvector_availability_installed(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # First query checks pg_extension (installed), second checks pg_available_extensions
        mock_cur.fetchone.side_effect = [("0.5.1",), ("0.5.1",)]

        result = check_pgvector_availability(mock_conn)
        assert result["installed"] is True
        assert result["available"] is True
        assert result["version"] == "0.5.1"

    def test_check_pgvector_availability_available_but_not_installed(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchone.side_effect = [None, ("0.5.1",)]

        result = check_pgvector_availability(mock_conn)
        assert result["installed"] is False
        assert result["available"] is True
        assert result["version"] == "0.5.1"

    def test_check_pgvector_availability_unsupported(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_cur.fetchone.side_effect = [None, None]

        result = check_pgvector_availability(mock_conn)
        assert result["installed"] is False
        assert result["available"] is False
        assert result["version"] is None

    def test_pgvector_availability_in_readiness_telemetry(self, monkeypatch):
        """PGVectorManager.check_readiness() must report pgvector status in readiness output."""
        monkeypatch.setenv("POSTGRES_URL", "postgresql://app_user:s3cr3t@remote-db:5432/app_db")
        manager = PGVectorManager(url="postgresql://app_user:s3cr3t@remote-db:5432/app_db")

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # SELECT 1
        mock_cur.fetchone.side_effect = [
            (1,),            # SELECT 1
            ("0.5.1",),      # pg_extension query from check_pgvector_availability
            ("0.5.1",),      # pg_available_extensions query
        ]

        with patch.object(manager, "get_connection") as mock_get_conn, \
             patch("app.core_backend.database.migrations.verify_schema_version", return_value=(True, 5)):
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            readiness = manager.check_readiness()
            assert readiness["status"] == "ready"
            assert "pgvector" in readiness
            assert readiness["pgvector"]["installed"] is True

    def test_migration_sql_contains_safe_conditional_vector_handling(self):
        """Verifies migration SQL guards against missing pgvector extension gracefully."""
        assert "pg_available_extensions" in MIGRATION_V1_SQL, "Migration 1 must check pg_available_extensions"
        assert "CREATE EXTENSION IF NOT EXISTS vector" in MIGRATION_V1_SQL
        assert "pg_type WHERE typname = 'vector'" in MIGRATION_V1_SQL, (
            "Migration 1 must conditionally declare VECTOR(768) or TEXT based on pgvector availability"
        )
        assert "pg_type WHERE typname = 'vector'" in MIGRATION_V3_SQL, (
            "Migration 3 must conditionally create HNSW/IVFFlat indexes only when vector type is active"
        )


class TestSSEStreamingProxyHeaders:
    """Verifies that long-running Server-Sent Events (SSE) responses include required proxy bypass headers."""

    def test_tutor_stream_response_headers(self):
        """StreamingResponse headers in routes/tutor.py must prevent proxy buffering and caching."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.core_backend.core.dependencies import get_current_user

        mock_user = {"id": "streaming_render_user", "email": "render@neurolab.ai", "role": "authenticated"}
        app.dependency_overrides[get_current_user] = lambda: mock_user

        try:
            client = TestClient(app)
            response = client.post(
                "/api/tutor/chat/stream",
                json={"prompt": "Explain Newton's third law of motion simply.", "session_id": "sess_render_test"},
                headers={"Authorization": "Bearer mock_render_token", "Content-Type": "application/json"},
            )
            assert response.status_code == 200
            # SSE Streaming media type
            assert "text/event-stream" in response.headers.get("content-type", "")

            # Proxy bypass headers
            assert response.headers.get("x-accel-buffering") == "no", (
                "X-Accel-Buffering: no is required for intermediate proxies (Render/Nginx) to stream events immediately"
            )
            assert "no-cache" in response.headers.get("cache-control", "")
            assert "no-transform" in response.headers.get("cache-control", ""), (
                "no-transform prevents proxy gzip/compression from breaking SSE chunk framing"
            )
            assert response.headers.get("connection") == "keep-alive"
        finally:
            app.dependency_overrides.clear()

    def test_nginx_conf_sse_proxy_buffering_disabled(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        nginx_conf_path = repo_root / "nginx.conf"
        assert nginx_conf_path.exists()
        content = nginx_conf_path.read_text(encoding="utf-8")

        assert "proxy_buffering off;" in content, "nginx.conf must disable proxy_buffering for SSE"
        assert "proxy_cache off;" in content, "nginx.conf must disable proxy_cache for SSE"
        assert "chunked_transfer_encoding on;" in content


class TestWorkerExecutionArchitecture:
    """Verifies Celery worker architecture and database verification task."""

    def test_celery_app_instantiated(self):
        assert celery_app.main == "neurolab_worker"
        assert "app.worker.process_heavy_cv_frame" in celery_app.conf.task_routes
        assert "app.worker.generate_ai_tutor_response" in celery_app.conf.task_routes

    def test_worker_db_connectivity_task(self):
        with patch("app.core_backend.database.pgvector_db.PGVectorManager.check_readiness") as mock_check:
            mock_check.return_value = {"status": "ready", "connected": True}
            result = check_worker_db_connectivity()
            assert result["status"] == "ready"
            assert result["connected"] is True
