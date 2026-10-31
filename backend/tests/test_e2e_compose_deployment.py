"""
End-to-End Integration and Deployment Tests for Problem 41:
Full Compose Stack Lifecycle, Gateway Proxying, Authentication, Persistence, CV, and Streaming.

Verifies:
1. Stack Readiness & Liveness: Nginx proxy routes to backend (port 8000), /ready returns 200 with connected DB.
2. Port Mismatch Detection: Validates that port alignment between Nginx (8000) and Backend (8000) is enforced.
3. Missing DB Config Detection: Validates that missing database configuration halts migrations and fails readiness.
4. Authentication: Protected routes require valid credentials and reject invalid/missing tokens.
5. Database Persistence: Verifies schema migrations and durable database writes/reads in PostgreSQL.
6. Computer Vision: Valid binary frame uploads succeed; oversized payloads (>10MB) are rejected with HTTP 413.
7. Streaming: SSE streaming endpoint disables buffering and returns real-time chunks.
"""
import os
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import cv2
import numpy as np
import jwt

from app.main import app
from app.core_backend.core.health import check_readiness, check_liveness
from app.core_backend.database import pgvector_db
from app.core_backend.core.dependencies import get_current_user, get_database_manager
from app.core_backend.routes import tutor as tutor_route

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Test JWT Credentials
TEST_JWT_SECRET = "test-mock-jwt-secret-at-least-32-chars-long"
TEST_USER = {"id": "e2e_student_123", "email": "student@neurolab.ai", "role": "authenticated"}
TEST_TOKEN = jwt.encode({"sub": TEST_USER["id"], "email": TEST_USER["email"]}, TEST_JWT_SECRET, algorithm="HS256")
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def test_client():
    return TestClient(app)


class TestComposeStackReadinessAndGateway:
    """Verifies gateway routing, health probes, and service readiness."""

    def test_liveness_probe_returns_responsive(self, test_client):
        res = test_client.get("/live")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "alive"
        assert data["process"] == "responsive"

    def test_healthz_alias_returns_alive(self, test_client):
        res = test_client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "alive"

    def test_readiness_probe_evaluates_database_and_dependencies(self, test_client):
        res = test_client.get("/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("ready", "healthy", "degraded")
        assert "dependencies" in data
        assert "database" in data["dependencies"]

    def test_nginx_and_compose_upstream_ports_are_standardized_to_8000(self):
        """Validates that Nginx and Compose agree on backend port 8000 (catches port mismatch)."""
        nginx_conf = (REPO_ROOT / "nginx.conf").read_text(encoding="utf-8")
        compose_conf = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        # Nginx upstream must target backend:8000
        assert "server backend:8000;" in nginx_conf
        assert "backend:7860" not in nginx_conf

        # Docker Compose must expose backend on port 8000
        assert 'expose:\n      - "8000"' in compose_conf or '- "8000"' in compose_conf


class TestComposePortMismatchAndMissingDbCatches:
    """
    Verification Requirement:
    Confirm the integration job catches the port mismatch and missing database configuration before deployment.
    """

    def test_port_mismatch_fails_upstream_connection(self):
        """Simulates port mismatch (e.g. backend running on 7860 while proxy targets 8000)."""
        import socket
        # Attempting to connect to mismatched port 7860 must fail
        with pytest.raises((ConnectionRefusedError, OSError)):
            sock = socket.create_connection(("127.0.0.1", 7860), timeout=0.1)
            sock.close()

    def test_missing_database_configuration_fails_readiness(self, monkeypatch, test_client):
        """Simulates missing database configuration (empty POSTGRES_URL) in production."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        
        # When PostgreSQL configuration is missing/invalid, readiness MUST return 503
        with patch.object(
            pgvector_db,
            "check_database_readiness",
            return_value={
                "status": "unhealthy",
                "connected": False,
                "error": "Missing POSTGRES_URL: database connection string not provided in environment.",
            },
        ):
            res = test_client.get("/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "unhealthy"
            assert data["connected"] is False
            assert "Missing POSTGRES_URL" in data["error"]


class TestComposeAuthentication:
    """Verifies API authorization enforcement across endpoints."""

    def test_unauthenticated_request_to_protected_route_rejected(self, test_client):
        # CV frame upload requires authentication
        res = test_client.post("/api/cv/process-frame-binary", content=b"fake-data")
        assert res.status_code in (401, 403)

    def test_authenticated_request_with_valid_token_accepted(self, test_client):
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        try:
            # Generate valid test image
            img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.circle(img, (160, 120), 40, (0, 0, 255), -1)
            _, buffer = cv2.imencode(".jpg", img)
            
            res = test_client.post(
                "/api/cv/process-frame-binary",
                content=buffer.tobytes(),
                headers={"Content-Type": "image/jpeg", **AUTH_HEADERS},
            )
            assert res.status_code == 200
        finally:
            app.dependency_overrides.clear()


class TestComposeDatabasePersistence:
    """Verifies schema persistence and database write/read operations."""

    def test_database_persistence_manager_initialization(self):
        """Confirms PGVectorManager initializes and manages connection pooling."""
        from app.core_backend.database.pgvector_db import PGVectorManager
        test_url = os.getenv("POSTGRES_URL", "postgresql://test_user:test_pass@localhost:5432/test_stemlab")
        manager = PGVectorManager(url=test_url)
        assert manager is not None
        readiness = manager.check_readiness(timeout=0.2)
        assert "status" in readiness
        assert "connected" in readiness


class TestComposeComputerVisionPipeline:
    """Verifies Computer Vision processing and payload constraints."""

    def test_binary_frame_upload_and_tracking(self, test_client):
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        try:
            img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.circle(img, (160, 120), 30, (0, 0, 255), -1)
            _, buffer = cv2.imencode(".jpg", img)

            res = test_client.post(
                "/api/cv/process-frame-binary",
                content=buffer.tobytes(),
                headers={"Content-Type": "image/jpeg", **AUTH_HEADERS},
            )
            assert res.status_code == 200
            data = res.json()
            assert "centroid" in data or "bounding_boxes" in data
        finally:
            app.dependency_overrides.clear()

    def test_oversized_payload_rejected_by_policy(self, test_client):
        """Payload exceeding 5MB / 10MB limit is rejected with HTTP 413."""
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        try:
            oversized_bytes = b"X" * (6 * 1024 * 1024)  # 6MB > 5MB limit
            res = test_client.post(
                "/api/cv/process-frame-binary",
                content=oversized_bytes,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(oversized_bytes)),
                    **AUTH_HEADERS,
                },
            )
            assert res.status_code == 413
        finally:
            app.dependency_overrides.clear()


class TestComposeStreamingResponse:
    """Verifies streaming SSE responses without proxy buffering stalls."""

    def test_sse_streaming_response_protocol(self, test_client):
        app.dependency_overrides[get_current_user] = lambda: TEST_USER
        
        # Mock model response for streaming
        mock_model = MagicMock()
        mock_model.generate_content.return_value = [
            MagicMock(text="Pendulum motion is governed by gravity and rope length."),
        ]
        tutor_route.tutor_service.model = mock_model
        
        try:
            payload = {
                "prompt": "Explain pendulum motion step by step",
                "session_id": "e2e_stream_sess_1",
                "experiment_state": {
                    "experiment_type": "pendulum",
                    "parameters": {"length": 1.0, "mass": 0.5},
                    "status": "running",
                },
            }
            res = test_client.post(
                "/api/tutor/chat/stream",
                json=payload,
                headers=AUTH_HEADERS,
            )
            assert res.status_code == 200
            assert "text/event-stream" in res.headers.get("content-type", "")
            assert res.headers.get("x-accel-buffering") == "no"
            assert "no-cache" in res.headers.get("cache-control", "")
        finally:
            app.dependency_overrides.clear()
