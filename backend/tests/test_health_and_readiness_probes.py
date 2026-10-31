"""
Unit and Integration Tests for Problem 35:
Health checks separate Liveness from Readiness and check operational dependencies.

Key Verifications:
1. Liveness (/live, /healthz):
   - Confirms process is alive and responsive.
   - Independent of external dependencies: Upstream database or Gemini outages MUST NOT fail liveness
     (preventing orchestrator restart storms and crash loops).
2. Readiness (/ready, /health/ready):
   - Confirms instance can serve required workload.
   - Evaluates essential dependencies (PostgreSQL, model provider, task broker) with short timeouts.
   - When PostgreSQL fails/stops in production, /ready returns HTTP 503.
   - When PostgreSQL is restored, /ready recovers to HTTP 200.
3. Root route (/):
   - Evaluates operational state of dependencies while returning top-level liveness.
   - Reports both liveness and readiness statuses explicitly.
"""
import os
import time
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core_backend.core.health import check_liveness, check_readiness
from app.core_backend.database.pgvector_db import (
    PGVectorManager,
    DatabaseMode,
    DatabasePoolTimeoutError,
)

client = TestClient(app)


class TestLivenessProbe:
    """Verifies liveness probe is fast, in-process, and independent of external outages."""

    def test_liveness_endpoint_returns_200_and_process_alive(self):
        res = client.get("/live")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "alive"
        assert data["process"] == "responsive"
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
        assert "timestamp" in data

    def test_healthz_alias_returns_200_and_alive(self):
        res = client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "alive"

    def test_liveness_remains_alive_during_database_outage(self, monkeypatch):
        """
        Verification: Stopping/breaking PostgreSQL must NOT fail liveness.
        The process is alive, so orchestrators must not restart the container.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        from app.core_backend.database import pgvector_db
        monkeypatch.setattr(
            pgvector_db,
            "check_database_readiness",
            lambda *args, **kwargs: {"status": "unhealthy", "connected": False, "error": "Postgres stopped"},
        )

        res_live = client.get("/live")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"

    def test_liveness_remains_alive_during_gemini_outage(self, monkeypatch):
        """
        Verification: An upstream Gemini API outage or missing API key must NOT fail liveness.
        Does not cause endless application restarts.
        """
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        res_live = client.get("/live")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"

    def test_liveness_remains_alive_during_redis_outage(self, monkeypatch):
        """Stopping Redis must not fail liveness."""
        monkeypatch.setenv("REDIS_URL", "redis://nonexistent-host:6379/0")

        res_live = client.get("/live")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"


class TestReadinessProbe:
    """Verifies readiness evaluates dependencies with short timeouts and fails when essential dependencies stop."""

    def test_readiness_returns_200_when_dependencies_healthy(self):
        with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "ready", "connected": True}):
            res = client.get("/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ready"
            assert data["connected"] is True
            assert "dependencies" in data
            assert data["dependencies"]["database"]["status"] == "ready"

    def test_health_ready_alias_returns_200(self):
        with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "ready", "connected": True}):
            res = client.get("/health/ready")
            assert res.status_code == 200
            assert res.json()["status"] == "ready"

    def test_postgresql_outage_fails_readiness_and_restoration_recovers(self, monkeypatch):
        """
        Verification Requirement:
        Stop PostgreSQL and verify that readiness fails while the process remains alive.
        Restore PostgreSQL and confirm readiness recovers.
        """
        monkeypatch.setenv("ENVIRONMENT", "production")
        from app.core_backend.database import pgvector_db

        # 1. Simulate PostgreSQL stopped / down
        monkeypatch.setattr(
            pgvector_db,
            "check_database_readiness",
            lambda *args, **kwargs: {
                "status": "unhealthy",
                "connected": False,
                "error": "Connection refused: database server stopped",
            },
        )

        # Liveness MUST stay 200 alive (process is alive)
        res_live = client.get("/live")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"

        # Readiness MUST fail with 503
        res_ready = client.get("/ready")
        assert res_ready.status_code == 503
        data_down = res_ready.json()
        assert data_down["status"] == "unhealthy"
        assert data_down["connected"] is False
        assert "Connection refused" in data_down["error"]

        # 2. Restore PostgreSQL
        monkeypatch.setattr(
            pgvector_db,
            "check_database_readiness",
            lambda *args, **kwargs: {
                "status": "ready",
                "connected": True,
                "schema_status": "up_to_date",
            },
        )

        # Readiness MUST recover to 200 OK
        res_recovered = client.get("/ready")
        assert res_recovered.status_code == 200
        data_up = res_recovered.json()
        assert data_up["status"] == "ready"
        assert data_up["connected"] is True

        # Liveness continues 200
        res_live_after = client.get("/live")
        assert res_live_after.status_code == 200

    def test_readiness_enforces_short_bounded_timeout(self, monkeypatch):
        """Readiness check must pass timeout to database readiness check."""
        recorded_timeout = []

        def mock_db_check(timeout=None):
            recorded_timeout.append(timeout)
            return {"status": "ready", "connected": True}

        from app.core_backend.database import pgvector_db
        monkeypatch.setattr(pgvector_db, "check_database_readiness", mock_db_check)

        res = client.get("/ready")
        assert res.status_code == 200
        assert len(recorded_timeout) > 0
        assert recorded_timeout[0] is not None
        assert recorded_timeout[0] <= 2.0, "Readiness probe must enforce short timeout <= 2.0s"

    def test_async_task_broker_outage_fails_readiness_when_enabled(self, monkeypatch):
        """When ASYNC_TASKS_ENABLED=true, broker failure must fail readiness with 503."""
        monkeypatch.setenv("ASYNC_TASKS_ENABLED", "true")

        with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "ready", "connected": True}), \
             patch("app.worker.check_broker_health", return_value={"status": "unhealthy", "connected": False, "error": "Redis broker unreachable"}):
            res = client.get("/ready")
            assert res.status_code == 503
            assert res.json()["status"] == "unhealthy"
            assert res.json()["dependencies"]["task_broker"]["status"] == "unhealthy"


class TestRootRouteChecksDependencies:
    """Verifies GET / checks operational dependencies without crashing on upstream outages."""

    def test_root_route_returns_operational_dependencies(self):
        with patch("app.core_backend.database.pgvector_db.check_database_readiness", return_value={"status": "ready", "connected": True}):
            res = client.get("/")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ok"
            assert "liveness" in data
            assert data["liveness"]["status"] == "alive"
            assert "readiness" in data
            assert "dependencies" in data
            assert "database" in data["dependencies"]
            assert "model_provider" in data["dependencies"]

    def test_root_route_remains_responsive_when_database_unhealthy(self, monkeypatch):
        """Root route reports database unhealthiness while maintaining responsiveness."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        from app.core_backend.database import pgvector_db
        monkeypatch.setattr(
            pgvector_db,
            "check_database_readiness",
            lambda *args, **kwargs: {"status": "unhealthy", "connected": False, "error": "Down"},
        )

        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["liveness"]["status"] == "alive"
        assert data["readiness"]["database"] == "unhealthy"

    def test_root_route_remains_responsive_during_gemini_outage(self, monkeypatch):
        """Gemini outage is reflected in model_provider status without crashing root route."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        res = client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["readiness"]["model_provider"] == "unconfigured"


class TestNginxProxyHealthRouteConfiguration:
    """Verifies nginx.conf forwards /ready, /live, and /healthz to the backend service."""

    def test_nginx_conf_proxies_readiness_and_liveness(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        nginx_conf = (repo_root / "nginx.conf").read_text(encoding="utf-8")

        assert "location ~ ^/(ready|live|healthz)" in nginx_conf, (
            "nginx.conf must configure proxy forwarding for /ready, /live, and /healthz"
        )
        assert "proxy_pass http://backend_service;" in nginx_conf

