"""
NeuroLab AI: Production Observability, Metrics, Tracing, and Alerting System
Problem 42:
- Measure API latency, model latency, token usage, cache hit rate, database failures, and queue depth.
- Record CV inference latency and error rates.
- Add alerts for sustained failures and quota exhaustion.
- Redact sensitive data from logs.
- Sample traces where full tracing would be expensive.
- Attach Request and Trace IDs to requests, logs, and responses.
"""
import time
import uuid
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, Gauge

from app.logger import logger, bind_request_context, clear_request_context, redact_sensitive_data

# ==============================================================================
# 1. Prometheus Metric Instruments
# ==============================================================================

# API Latency and Traffic
API_REQUEST_DURATION_SECONDS = Histogram(
    "neurolab_api_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

API_REQUESTS_TOTAL = Counter(
    "neurolab_api_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"],
)

# AI Model Inference & Tokens
MODEL_INFERENCE_DURATION_SECONDS = Histogram(
    "neurolab_model_inference_duration_seconds",
    "LLM inference latency in seconds",
    ["model", "operation"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0),
)

MODEL_TOKEN_USAGE_TOTAL = Counter(
    "neurolab_model_token_usage_total",
    "Tokens consumed by model inference",
    ["model", "token_type"],
)

MODEL_REQUESTS_TOTAL = Counter(
    "neurolab_model_requests_total",
    "Total model generation requests",
    ["model", "status"],
)

# Cache Hit Rate & Telemetry
CACHE_OPERATIONS_TOTAL = Counter(
    "neurolab_cache_operations_total",
    "Redis cache operations",
    ["operation", "status"],
)

CACHE_HIT_RATIO = Gauge(
    "neurolab_cache_hit_ratio",
    "Redis cache hit ratio (0.0 to 1.0)",
)

CACHE_ERRORS_TOTAL = Counter(
    "neurolab_cache_errors_total",
    "Redis cache operation failures by operation and error type",
    ["operation", "error_type"],
)

# Database Failures & Latency
DATABASE_OPERATIONS_TOTAL = Counter(
    "neurolab_database_operations_total",
    "Database operations performed",
    ["operation", "status"],
)

DATABASE_FAILURES_TOTAL = Counter(
    "neurolab_database_failures_total",
    "Database query, connection, or mutation failures",
    ["operation", "error_type"],
)

DATABASE_ACQUISITION_DURATION_SECONDS = Histogram(
    "neurolab_database_acquisition_duration_seconds",
    "Database connection acquisition duration from pool",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# Computer Vision Inference & Latency
CV_INFERENCE_DURATION_SECONDS = Histogram(
    "neurolab_cv_inference_duration_seconds",
    "Computer vision inference latency in seconds",
    ["tracking_method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

CV_FRAMES_PROCESSED_TOTAL = Counter(
    "neurolab_cv_frames_processed_total",
    "Total video frames processed by CV service",
    ["tracking_method", "status"],
)

CV_INFERENCE_ERRORS_TOTAL = Counter(
    "neurolab_cv_inference_errors_total",
    "Computer vision frame decoding or inference errors",
    ["error_type"],
)

# Queue Depth & Resource Saturation
CONCURRENCY_QUEUE_DEPTH = Gauge(
    "neurolab_concurrency_queue_depth",
    "Active waiting tasks in concurrency queue",
    ["service"],
)

# Active Operational Alerts
ACTIVE_ALERTS_TOTAL = Gauge(
    "neurolab_active_alerts_total",
    "Active operational alert count",
    ["alert_name", "severity"],
)


# ==============================================================================
# 2. Automated Alerting Manager
# ==============================================================================

class AlertRecord:
    def __init__(self, name: str, severity: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.name = name
        self.severity = severity
        self.message = message
        self.metadata = metadata or {}
        self.triggered_at = datetime.now(timezone.utc).isoformat()
        self.active = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "severity": self.severity,
            "message": self.message,
            "metadata": redact_sensitive_data(self.metadata),
            "triggered_at": self.triggered_at,
            "active": self.active,
        }


class AlertManager:
    """
    Manages operational alerts for sustained failures, database outages,
    model timeouts, and quota exhaustion.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._alerts: Dict[str, AlertRecord] = {}

    def trigger_alert(
        self,
        alert_name: str,
        severity: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AlertRecord:
        """Triggers or updates an operational alert and logs structured warning/critical."""
        sanitized_meta = redact_sensitive_data(metadata or {})
        with self._lock:
            record = AlertRecord(alert_name, severity, message, sanitized_meta)
            self._alerts[alert_name] = record
            ACTIVE_ALERTS_TOTAL.labels(alert_name=alert_name, severity=severity).set(1)

        log_fn = logger.critical if severity.upper() == "CRITICAL" else logger.warning
        log_fn(
            "operational_alert_triggered",
            alert=alert_name,
            severity=severity,
            message=message,
            **sanitized_meta,
        )
        return record

    def resolve_alert(self, alert_name: str):
        """Resolves an active alert."""
        with self._lock:
            if alert_name in self._alerts:
                record = self._alerts[alert_name]
                record.active = False
                ACTIVE_ALERTS_TOTAL.labels(alert_name=alert_name, severity=record.severity).set(0)
                del self._alerts[alert_name]
                logger.info("operational_alert_resolved", alert=alert_name)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [alert.to_dict() for alert in self._alerts.values() if alert.active]

    def has_critical_alerts(self) -> bool:
        with self._lock:
            return any(a.severity.upper() == "CRITICAL" and a.active for a in self._alerts.values())

    def clear(self):
        with self._lock:
            self._alerts.clear()


alert_manager = AlertManager()


# ==============================================================================
# 3. Telemetry Helper Functions
# ==============================================================================

def record_model_inference_metrics(
    model: str,
    operation: str,
    duration_seconds: float,
    token_usage: Optional[Dict[str, int]] = None,
    status: str = "success",
    error_message: Optional[str] = None,
):
    """Records LLM inference metrics, tokens, and alert conditions."""
    MODEL_INFERENCE_DURATION_SECONDS.labels(model=model, operation=operation).observe(duration_seconds)
    MODEL_REQUESTS_TOTAL.labels(model=model, status=status).inc()

    if token_usage:
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        MODEL_TOKEN_USAGE_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
        MODEL_TOKEN_USAGE_TOTAL.labels(model=model, token_type="completion").inc(completion_tokens)

    # Check for quota exhaustion (HTTP 429 / RESOURCE_EXHAUSTED)
    if status == "quota_exhausted" or (error_message and ("429" in error_message or "quota" in error_message.lower())):
        alert_manager.trigger_alert(
            alert_name="MODEL_QUOTA_EXHAUSTED",
            severity="CRITICAL",
            message=f"Model quota exhausted for '{model}'. Generation requests are being rate-limited by upstream provider.",
            metadata={"model": model, "operation": operation},
        )
    elif status == "timeout":
        alert_manager.trigger_alert(
            alert_name="MODEL_TIMEOUT_THRESHOLD_EXCEEDED",
            severity="WARNING",
            message=f"Model inference timed out after {duration_seconds:.1f}s for model '{model}'.",
            metadata={"model": model, "operation": operation, "duration_seconds": duration_seconds},
        )
    elif status == "success":
        # Resolve transient timeout/quota alerts on sustained success
        alert_manager.resolve_alert("MODEL_TIMEOUT_THRESHOLD_EXCEEDED")


def record_cache_metric(operation: str, status: str):
    """Records Redis cache operation and recalculates the cache hit ratio."""
    CACHE_OPERATIONS_TOTAL.labels(operation=operation, status=status).inc()
    from app.cache import CACHE_METRICS
    hits = CACHE_METRICS.get("redis_hits", 0)
    misses = CACHE_METRICS.get("redis_misses", 0)
    total = hits + misses
    ratio = (hits / total) if total > 0 else 0.0
    CACHE_HIT_RATIO.set(round(ratio, 4))


def record_cache_failure(operation: str, error_type: str, error_msg: str = "", consecutive_errors: int = 1):
    """Records a Redis cache failure, updates metrics, and triggers operational alert if outage is detected."""
    CACHE_ERRORS_TOTAL.labels(operation=operation, error_type=error_type).inc()
    CACHE_OPERATIONS_TOTAL.labels(operation=operation, status="error").inc()
    from app.cache import CACHE_METRICS
    hits = CACHE_METRICS.get("redis_hits", 0)
    misses = CACHE_METRICS.get("redis_misses", 0)
    total = hits + misses
    ratio = (hits / total) if total > 0 else 0.0
    CACHE_HIT_RATIO.set(round(ratio, 4))

    if consecutive_errors >= 3:
        alert_manager.trigger_alert(
            alert_name="REDIS_CACHE_OUTAGE_DETECTED",
            severity="WARNING",
            message=f"Redis cache outage detected: {consecutive_errors} consecutive failures ({error_type}: {error_msg}).",
            metadata={
                "operation": operation,
                "error_type": error_type,
                "consecutive_errors": consecutive_errors,
                "dependency": "redis_cache",
                "policy": "optional_safe_degradation",
            },
        )


def record_database_failure(operation: str, error_type: str, error_msg: str = ""):
    """Records a database failure and triggers operational alert if outage is detected."""
    DATABASE_FAILURES_TOTAL.labels(operation=operation, error_type=error_type).inc()
    DATABASE_OPERATIONS_TOTAL.labels(operation=operation, status="failed").inc()

    err_lower = error_msg.lower()
    if any(sig in err_lower for sig in ("connection refused", "timeout", "pool exhausted", "cannot connect")):
        alert_manager.trigger_alert(
            alert_name="CRITICAL_DATABASE_OUTAGE",
            severity="CRITICAL",
            message=f"Database outage detected during '{operation}': {error_type}",
            metadata={"operation": operation, "error_type": error_type, "detail": error_msg},
        )


def record_cv_inference_metric(
    tracking_method: str,
    duration_seconds: float,
    status: str = "success",
    error_type: Optional[str] = None,
):
    """Records computer vision frame processing duration and errors."""
    CV_INFERENCE_DURATION_SECONDS.labels(tracking_method=tracking_method).observe(duration_seconds)
    CV_FRAMES_PROCESSED_TOTAL.labels(tracking_method=tracking_method, status=status).inc()
    if error_type:
        CV_INFERENCE_ERRORS_TOTAL.labels(error_type=error_type).inc()


def update_queue_depth(service: str, depth: float):
    """Updates the concurrency queue depth gauge."""
    CONCURRENCY_QUEUE_DEPTH.labels(service=service).set(depth)


# ==============================================================================
# 4. Sentry APM Dynamic Trace Sampler
# ==============================================================================

def sentry_traces_sampler(sampling_context: Dict[str, Any]) -> float:
    """
    Intelligent dynamic sampling rule for APM:
    - High-frequency health probes (/live, /ready, /healthz): 0% (prevent spam)
    - Static assets and favicon: 0%
    - High-throughput CV frame streaming: 5% sample rate
    - Critical Tutor LLM generation & session flows: 100% sample rate
    - Standard API routes: 20% sample rate
    - Errored transactions: 100% sample rate
    """
    transaction_context = sampling_context.get("transaction_context", {})
    op = transaction_context.get("op", "")
    name = transaction_context.get("name", "")

    # Sample health probes at 0%
    if any(name.startswith(p) for p in ("/live", "/ready", "/healthz", "/metrics", "/favicon.ico")):
        return 0.0

    # Sample high-throughput CV binary uploads at 5%
    if "/api/cv" in name or "process-frame" in name:
        return 0.05

    # Full 100% trace sampling on Tutor chat streaming and AI inference
    if "/api/tutor" in name or "/api/v1/tutor" in name:
        return 1.0

    # Default API sample rate: 20%
    return 0.2


# ==============================================================================
# 5. Observability & Tracing Middleware
# ==============================================================================

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI Middleware:
    - Injects unique Request-ID and Trace-ID.
    - Propagates IDs into structlog contextvars for unified log correlation.
    - Measures wall-clock API request latency and updates Prometheus metrics.
    - Redacts sensitive headers and outputs structured JSON completion logs.
    - Echoes X-Request-ID and X-Trace-ID in response headers.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        # 1. Extract or generate Request and Trace IDs
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        trace_id = request.headers.get("x-trace-id") or f"trace_{uuid.uuid4().hex[:16]}"

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Bind to contextvars so every log call automatically includes them
        bind_request_context(request_id=request_id, trace_id=trace_id)

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code

            # Attach headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            return response
        except Exception as e:
            status_code = 500
            logger.exception(
                "request_unhandled_exception",
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        finally:
            duration = time.perf_counter() - start_time
            duration_ms = round(duration * 1000, 2)
            path = request.url.path

            # Update Prometheus metrics
            API_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                endpoint=path,
                status_code=str(status_code),
            ).observe(duration)

            API_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=path,
                status_code=str(status_code),
            ).inc()

            # Structured log of completed request
            logger.info(
                "http_request_finished",
                method=request.method,
                path=path,
                status_code=status_code,
                latency_ms=duration_ms,
            )

            # Clear contextvars
            clear_request_context()

