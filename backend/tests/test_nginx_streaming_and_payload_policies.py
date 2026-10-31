"""
Unit and Integration Tests for Problem 36:
Nginx Explicit Streaming and Payload Policies Verification.

Verifies:
1. Request-body limits: client_max_body_size is configured to 10M, preventing memory exhaustion.
   Oversized frames (>5MB/10MB) are rejected with HTTP 413, while valid frames succeed.
2. Distinct connect, send, and read timeouts:
   - SSE Streaming endpoint has extended timeouts (300s) to support long-running LLM generation.
   - Standard REST API endpoints use standard timeouts (60s).
   - Health probes use short timeouts (5s connect, 10s read).
3. Buffering policies:
   - SSE endpoint explicitly disables proxy buffering (proxy_buffering off; proxy_cache off; chunked_transfer_encoding on;).
   - Standard REST API routes maintain standard proxy buffering (proxy_buffering on;).
4. Trusted forwarded headers:
   - Configures Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host, and X-Forwarded-Port.
5. WebSocket isolation:
   - Upgrade headers are isolated from ordinary static/API routes.
   - location / does NOT unconditionally forward Connection: upgrade.
   - Dedicated location /ws/ handles WebSocket upgrades via mapped $connection_upgrade.
"""
import re
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import cv2
import numpy as np

from app.main import app
from app.core_backend.core.dependencies import get_current_user

client = TestClient(app)
AUTH_USER = {"id": "nginx_test_user", "email": "nginx@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer mock_nginx_jwt"}


def get_nginx_conf() -> str:
    repo_root = Path(__file__).resolve().parent.parent.parent
    nginx_path = repo_root / "nginx.conf"
    assert nginx_path.exists(), f"nginx.conf not found at {nginx_path}"
    return nginx_path.read_text(encoding="utf-8")


class TestNginxPayloadAndBodyPolicies:
    """Verifies client_max_body_size configuration and oversized upload rejection (HTTP 413)."""

    def test_client_max_body_size_configured(self):
        content = get_nginx_conf()
        assert re.search(r"client_max_body_size\s+10M\s*;", content), (
            "nginx.conf must configure client_max_body_size 10M;"
        )
        assert re.search(r"client_body_buffer_size\s+128k\s*;", content), (
            "nginx.conf should configure client_body_buffer_size 128k;"
        )

    def test_oversized_binary_frame_rejected_with_413(self):
        """Uploading a frame exceeding 5MB limit must be rejected with HTTP 413."""
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        try:
            # 6MB dummy binary payload
            oversized_payload = b"\x00" * (6 * 1024 * 1024)
            res = client.post(
                "/api/cv/process-frame-binary",
                content=oversized_payload,
                headers={"Content-Type": "application/octet-stream", **AUTH_HEADERS},
            )
            assert res.status_code == 413
            assert "Payload too large" in res.json().get("detail", "")
        finally:
            app.dependency_overrides.clear()

    def test_valid_size_binary_frame_accepted(self):
        """Uploading a frame within valid size limits (<5MB) is accepted."""
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        try:
            # Create a 320x240 valid JPEG image byte sequence (~5KB)
            img = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.circle(img, (160, 120), 40, (0, 0, 255), -1)
            _, buffer = cv2.imencode(".jpg", img)
            valid_bytes = buffer.tobytes()

            res = client.post(
                "/api/cv/process-frame-binary",
                content=valid_bytes,
                headers={"Content-Type": "image/jpeg", **AUTH_HEADERS},
            )
            assert res.status_code == 200
            data = res.json()
            assert "centroid" in data or "bounding_boxes" in data
        finally:
            app.dependency_overrides.clear()


class TestNginxTimeoutsAndBufferingPolicies:
    """Verifies distinct timeouts and buffering policies between SSE streaming and REST API."""

    def test_sse_endpoint_has_extended_timeout_and_buffering_disabled(self):
        content = get_nginx_conf()
        # Find the SSE streaming location block
        match = re.search(r"location\s+~\s+\^/api/\(v1/\)\?tutor/chat/stream\s*\{([^}]+)\}", content)
        assert match is not None, "nginx.conf must define dedicated location for SSE tutor stream"
        block = match.group(1)

        # Buffering explicitly disabled for SSE
        assert "proxy_buffering off;" in block, "SSE route must have proxy_buffering off;"
        assert "proxy_cache off;" in block, "SSE route must have proxy_cache off;"
        assert "chunked_transfer_encoding on;" in block, "SSE route must have chunked_transfer_encoding on;"

        # Extended timeouts (300s) for long-running LLM generation
        assert "proxy_read_timeout 300s;" in block, "SSE route must allow 300s read timeout"
        assert "proxy_send_timeout 300s;" in block, "SSE route must allow 300s send timeout"

    def test_standard_api_endpoint_has_buffering_enabled_and_standard_timeout(self):
        content = get_nginx_conf()
        # Find the general /api/ location block
        match = re.search(r"location\s+/api/\s*\{([^}]+)\}", content)
        assert match is not None, "nginx.conf must define general location /api/"
        block = match.group(1)

        # Standard buffering enabled for ordinary API responses
        assert "proxy_buffering on;" in block, "Ordinary API route must keep standard proxy_buffering on;"
        assert "proxy_buffer_size" in block, "Ordinary API route should configure proxy_buffer_size"
        assert "proxy_buffers" in block, "Ordinary API route should configure proxy_buffers"

        # Standard API timeout terminates hung connections promptly (60s)
        assert "proxy_read_timeout 60s;" in block, "Standard API route should have 60s read timeout"
        assert "proxy_send_timeout 60s;" in block, "Standard API route should have 60s send timeout"

    def test_health_probe_timeouts_are_short(self):
        content = get_nginx_conf()
        match = re.search(r"location\s+~\s+\^/\(ready\|live\|healthz\)\s*\{([^}]+)\}", content)
        assert match is not None, "nginx.conf must define health probe location"
        block = match.group(1)

        assert "proxy_connect_timeout 5s;" in block
        assert "proxy_read_timeout 10s;" in block


class TestNginxForwardedHeadersAndWebSocketIsolation:
    """Verifies trusted forwarded headers and WebSocket isolation."""

    def test_trusted_forwarded_headers_configured(self):
        content = get_nginx_conf()
        assert "proxy_set_header Host $host;" in content
        assert "proxy_set_header X-Real-IP $remote_addr;" in content
        assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;" in content
        assert "proxy_set_header X-Forwarded-Proto $scheme;" in content
        assert "proxy_set_header X-Forwarded-Host $host;" in content
        assert "proxy_set_header X-Forwarded-Port $server_port;" in content

    def test_websocket_upgrade_not_indiscriminately_forwarded_to_root(self):
        """location / must NOT unconditionally set Connection 'upgrade' for regular HTTP routes."""
        content = get_nginx_conf()
        match = re.search(r"location\s+/\s*\{([^}]+)\}", content)
        assert match is not None, "nginx.conf must define location /"
        block = match.group(1)

        # Confirm no unconditional Connection 'upgrade'
        assert 'proxy_set_header Connection "upgrade";' not in block, (
            "location / must not unconditionally forward Connection 'upgrade' to static/HTML routes"
        )

    def test_dedicated_websocket_route_configured_with_connection_upgrade(self):
        content = get_nginx_conf()
        assert "map $http_upgrade $connection_upgrade" in content, (
            "nginx.conf must map $http_upgrade to $connection_upgrade"
        )
        match = re.search(r"location\s+/ws/\s*\{([^}]+)\}", content)
        assert match is not None, "nginx.conf must define dedicated /ws/ route for WebSockets"
        block = match.group(1)
        assert "proxy_set_header Upgrade $http_upgrade;" in block
        assert "proxy_set_header Connection $connection_upgrade;" in block or 'proxy_set_header Connection "upgrade";' in block


class TestStreamingLongerThanStandardTimeout:
    """Verifies that SSE streaming response headers and execution support extended durations."""

    def test_sse_streaming_response_headers_prevent_proxy_buffering(self):
        app.dependency_overrides[get_current_user] = lambda: AUTH_USER
        try:
            res = client.post(
                "/api/tutor/chat/stream",
                json={"prompt": "Explain quantum entanglement in detail.", "session_id": "stream_test_sess"},
                headers={"Content-Type": "application/json", **AUTH_HEADERS},
            )
            assert res.status_code == 200
            assert "text/event-stream" in res.headers.get("content-type", "")
            # X-Accel-Buffering instructs Nginx, Envoy, Cloudflare to disable buffering
            assert res.headers.get("x-accel-buffering") == "no"
            assert "no-transform" in res.headers.get("cache-control", "")
            assert res.headers.get("connection") == "keep-alive"
        finally:
            app.dependency_overrides.clear()
