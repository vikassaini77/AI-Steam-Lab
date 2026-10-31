"""
Tests for Problem 42: Production Observability, Structured Logging, Metrics, Tracing, and Alerting.
Verifies:
1. Structured logs throughout the backend with request and trace IDs.
2. Request and trace ID propagation via contextvars and HTTP headers.
3. API latency, model latency, token usage, cache hit rate, database failures, and queue depth.
4. Computer Vision (CV) inference latency and error rates.
5. Operational alerts for sustained failures, database outage, and quota exhaustion.
6. Automatic redaction of sensitive credentials, JWTs, and database URLs from logs and alert metadata.
7. Dynamic trace sampling rules (0% health, 5% CV, 100% LLM, 20% standard API).
8. Failure diagnosis drill: Model timeout and database outage clearly identified without leaking secrets.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.logger import (
    redact_sensitive_data,
    clear_request_context,
)
from app.core_backend.core.observability import (
    alert_manager,
    record_model_inference_metrics,
    record_cache_metric,
    record_database_failure,
    record_cv_inference_metric,
    update_queue_depth,
    sentry_traces_sampler,
    CACHE_HIT_RATIO,
    CV_FRAMES_PROCESSED_TOTAL,
    CV_INFERENCE_ERRORS_TOTAL,
    CONCURRENCY_QUEUE_DEPTH,
)
from app.cache import CACHE_METRICS


@pytest.fixture(autouse=True)
def clean_alerts_and_context():
    """Ensure clean alert manager and contextvars state before each test."""
    alert_manager.clear()
    clear_request_context()
    yield
    alert_manager.clear()
    clear_request_context()


def test_sensitive_data_redaction():
    """Verifies credentials, tokens, DB URLs, and secrets are scrubbed."""
    raw_dict = {
        "user_id": "usr_12345",
        "password": "SuperSecretPassword123!",
        "api_key": "AIzaSyD-1234567890abcdefghijklmnopqr",
        "nested": {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
            "safe_field": "visible_data",
            "db_uri": "postgresql://postgres:secret_db_pass@db.internal:5432/neurolab",
        },
        "list_items": [
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz.abc",
            "normal string",
        ],
    }

    sanitized = redact_sensitive_data(raw_dict)

    # Key-based redaction
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["token"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "visible_data"

    # Pattern-based redaction in strings and nested structures
    assert "secret_db_pass" not in sanitized["nested"]["db_uri"]
    assert "postgresql://postgres:[REDACTED]@" in sanitized["nested"]["db_uri"]

    assert "Bearer [REDACTED]" in sanitized["list_items"][0]
    assert sanitized["list_items"][1] == "normal string"


def test_request_and_trace_id_headers_propagation():
    """Verifies X-Request-ID and X-Trace-ID are echoed or auto-generated."""
    client = TestClient(app)

    # Case 1: Client provides custom Request and Trace IDs
    custom_headers = {
        "X-Request-ID": "req-custom-client-123",
        "X-Trace-ID": "trace-custom-client-456",
    }
    response = client.get("/live", headers=custom_headers)
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "req-custom-client-123"
    assert response.headers.get("X-Trace-ID") == "trace-custom-client-456"

    # Case 2: Client does not provide IDs; middleware must generate them
    response2 = client.get("/live")
    assert response2.status_code == 200
    gen_req_id = response2.headers.get("X-Request-ID")
    gen_trace_id = response2.headers.get("X-Trace-ID")
    assert gen_req_id is not None and gen_req_id.startswith("req_")
    assert gen_trace_id is not None and gen_trace_id.startswith("trace_")


def test_operational_alert_manager_lifecycle():
    """Verifies operational alert triggering, querying, resolution, and Prometheus gauge."""
    assert not alert_manager.has_critical_alerts()
    assert len(alert_manager.get_active_alerts()) == 0

    # Trigger a warning alert
    alert_manager.trigger_alert(
        alert_name="MODEL_TIMEOUT_THRESHOLD_EXCEEDED",
        severity="WARNING",
        message="Model inference exceeded latency threshold.",
        metadata={"duration_seconds": 32.5, "password": "leak_attempt"},
    )

    alerts = alert_manager.get_active_alerts()
    assert len(alerts) == 1
    assert alerts[0]["name"] == "MODEL_TIMEOUT_THRESHOLD_EXCEEDED"
    assert alerts[0]["severity"] == "WARNING"
    assert alerts[0]["metadata"]["password"] == "[REDACTED]"
    assert not alert_manager.has_critical_alerts()

    # Trigger a critical alert
    alert_manager.trigger_alert(
        alert_name="CRITICAL_DATABASE_OUTAGE",
        severity="CRITICAL",
        message="PostgreSQL cluster unreachable.",
        metadata={"url": "postgresql://user:pass123@host:5432/db"},
    )

    assert alert_manager.has_critical_alerts()
    assert len(alert_manager.get_active_alerts()) == 2
    active_names = [a["name"] for a in alert_manager.get_active_alerts()]
    assert "CRITICAL_DATABASE_OUTAGE" in active_names
    assert "MODEL_TIMEOUT_THRESHOLD_EXCEEDED" in active_names

    # Resolve the warning alert
    alert_manager.resolve_alert("MODEL_TIMEOUT_THRESHOLD_EXCEEDED")
    assert len(alert_manager.get_active_alerts()) == 1
    assert alert_manager.has_critical_alerts()

    # Resolve the critical alert
    alert_manager.resolve_alert("CRITICAL_DATABASE_OUTAGE")
    assert len(alert_manager.get_active_alerts()) == 0
    assert not alert_manager.has_critical_alerts()


def test_sentry_traces_sampler_rules():
    """Verifies dynamic trace sampling rules across health probes, CV, LLM, and API."""
    # Health checks should be 0.0 (prevent noise and spam)
    assert sentry_traces_sampler({"transaction_context": {"name": "/live"}}) == 0.0
    assert sentry_traces_sampler({"transaction_context": {"name": "/ready"}}) == 0.0
    assert sentry_traces_sampler({"transaction_context": {"name": "/healthz"}}) == 0.0
    assert sentry_traces_sampler({"transaction_context": {"name": "/metrics"}}) == 0.0

    # High-throughput CV frame processing: 5% (0.05)
    assert sentry_traces_sampler({"transaction_context": {"name": "/api/cv/process-frame"}}) == 0.05
    assert sentry_traces_sampler({"transaction_context": {"name": "/api/v1/cv/process-frame-binary"}}) == 0.05

    # Core AI Tutor streaming & LLM reasoning: 100% (1.0)
    assert sentry_traces_sampler({"transaction_context": {"name": "/api/tutor/stream"}}) == 1.0
    assert sentry_traces_sampler({"transaction_context": {"name": "/api/v1/tutor/chat"}}) == 1.0

    # Standard endpoints: 20% (0.2)
    assert sentry_traces_sampler({"transaction_context": {"name": "/api/experiments/list"}}) == 0.2


def test_cache_metrics_and_hit_ratio():
    """Verifies cache operation counters and hit ratio calculation."""
    CACHE_METRICS["redis_hits"] = 80
    CACHE_METRICS["redis_misses"] = 20
    record_cache_metric(operation="read", status="hit")

    # Hit ratio should be 80 / (80 + 20) = 0.8
    # Test reading the gauge value
    gauge_val = CACHE_HIT_RATIO._value.get()
    assert abs(gauge_val - 0.8) < 1e-4


def test_cv_inference_metrics_and_errors():
    """Verifies Computer Vision inference latency and error counters."""
    initial_frames = CV_FRAMES_PROCESSED_TOTAL.labels(tracking_method="optical_flow", status="success")._value.get()
    initial_errors = CV_INFERENCE_ERRORS_TOTAL.labels(error_type="payload_too_large")._value.get()

    record_cv_inference_metric(
        tracking_method="optical_flow",
        duration_seconds=0.042,
        status="success",
    )
    record_cv_inference_metric(
        tracking_method="optical_flow",
        duration_seconds=0.010,
        status="error",
        error_type="payload_too_large",
    )

    new_frames = CV_FRAMES_PROCESSED_TOTAL.labels(tracking_method="optical_flow", status="success")._value.get()
    new_errors = CV_INFERENCE_ERRORS_TOTAL.labels(error_type="payload_too_large")._value.get()

    assert new_frames == initial_frames + 1
    assert new_errors == initial_errors + 1


def test_queue_depth_metrics():
    """Verifies concurrency queue depth gauge is properly set."""
    update_queue_depth(service="tutor_concurrency", depth=4.0)
    val = CONCURRENCY_QUEUE_DEPTH.labels(service="tutor_concurrency")._value.get()
    assert val == 4.0

    update_queue_depth(service="tutor_concurrency", depth=0.0)
    val_after = CONCURRENCY_QUEUE_DEPTH.labels(service="tutor_concurrency")._value.get()
    assert val_after == 0.0


def test_model_quota_exhaustion_alert_and_metrics():
    """Verifies upstream quota exhaustion (HTTP 429) triggers alert and updates metrics."""
    record_model_inference_metrics(
        model="gemini-2.5-flash",
        operation="chat_stream",
        duration_seconds=0.25,
        status="quota_exhausted",
        error_message="Resource has been exhausted (e.g. check quota): 429 Too Many Requests",
    )

    alerts = alert_manager.get_active_alerts()
    quota_alerts = [a for a in alerts if a["name"] == "MODEL_QUOTA_EXHAUSTED"]
    assert len(quota_alerts) == 1
    assert quota_alerts[0]["severity"] == "CRITICAL"
    assert "gemini-2.5-flash" in quota_alerts[0]["message"]


def test_diagnostics_drill_model_timeout_and_db_outage():
    """
    Simulates production failure drill:
    1. Triggers a model timeout.
    2. Triggers a database outage with connection error containing raw credentials.
    3. Verifies logs, metrics, alerts, and HTTP readiness diagnose the causes without exposing secrets.
    """
    client = TestClient(app)

    # 1. Simulate Model Timeout
    record_model_inference_metrics(
        model="gemini-2.5-flash",
        operation="chat_stream",
        duration_seconds=30.5,
        status="timeout",
        error_message="Model generation timed out after 30.0s",
    )

    # 2. Simulate Database Outage with sensitive connection string
    db_outage_error = (
        "psycopg2.OperationalError: could not connect to server: "
        "connection refused at postgresql://neurolab_admin:superSecretP@ssw0rd!@10.0.0.12:5432/neurolab_prod"
    )
    record_database_failure(
        operation="retrieve_memories",
        error_type="psycopg2.OperationalError",
        error_msg=db_outage_error,
    )

    # 3. Query /api/monitoring/alerts endpoint
    alert_resp = client.get("/api/monitoring/alerts")
    assert alert_resp.status_code == 200
    alert_data = alert_resp.json()
    assert alert_data["has_critical"] is True

    alerts = alert_data["alerts"]
    alert_names = [a["name"] for a in alerts]
    assert "MODEL_TIMEOUT_THRESHOLD_EXCEEDED" in alert_names
    assert "CRITICAL_DATABASE_OUTAGE" in alert_names

    # 4. Confirm NO credentials leaked in alert responses or details
    response_text = alert_resp.text
    assert "superSecretP@ssw0rd!" not in response_text
    assert "postgresql://neurolab_admin:[REDACTED]@" in response_text

    # 5. Check /ready endpoint: must report 503 Service Unavailable because critical DB outage alert is active
    ready_resp = client.get("/ready")
    assert ready_resp.status_code == 503
    ready_data = ready_resp.json()
    assert ready_data["status"] == "unhealthy"
    assert "superSecretP@ssw0rd!" not in ready_resp.text


def test_metrics_endpoint_exposes_custom_telemetry():
    """Verifies that protected /metrics endpoint exposes our custom Prometheus metric names."""
    client = TestClient(app)

    # Protected endpoint rejects invalid credentials with 401
    unauth = client.get("/metrics", headers={"Authorization": "Bearer invalid-metrics-token"})
    assert unauth.status_code == 401

    token = "test-mock-metrics-token"
    auth_resp = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200
    content = auth_resp.text

    # Verify custom metric families are registered and scraped
    assert "neurolab_api_request_duration_seconds" in content
    assert "neurolab_api_requests_total" in content
    assert "neurolab_model_inference_duration_seconds" in content
    assert "neurolab_model_requests_total" in content
    assert "neurolab_cache_operations_total" in content
    assert "neurolab_cache_hit_ratio" in content
    assert "neurolab_database_failures_total" in content
    assert "neurolab_cv_frames_processed_total" in content
    assert "neurolab_active_alerts_total" in content
