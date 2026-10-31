"""
NeuroLab AI: Structured Logging with Context Propagation and Sensitive Data Redaction
Problem 42: Structured logs throughout the backend with request and trace IDs,
automatic redaction of sensitive credentials and PII.
"""
import re
import sys
import logging
from typing import Any, Dict
import structlog
from structlog.contextvars import merge_contextvars, bind_contextvars, clear_contextvars

# Keys whose values should always be redacted in structured logs
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "api_key",
    "token",
    "authorization",
    "auth",
    "jwt",
    "access_token",
    "refresh_token",
    "supabase_key",
    "supabase_jwt_secret",
    "gemini_api_key",
    "metrics_token",
    "cookie",
    "session_cookie",
}

# Regex patterns matching sensitive strings in freeform log messages or URLs
SENSITIVE_PATTERNS = [
    (re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"postgresql://([^:]+):([^@]+)@", re.IGNORECASE), r"postgresql://\1:[REDACTED]@"),
    (re.compile(r"AIza[0-9A-Za-z-_]{35}", re.IGNORECASE), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"sbp_[0-9a-zA-Z]{30,}", re.IGNORECASE), "[REDACTED_SUPABASE_KEY]"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", re.IGNORECASE), "[REDACTED_JWT]"),
]


def redact_string(val: str) -> str:
    """Sanitizes sensitive patterns in a string."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        val = pattern.sub(replacement, val)
    return val


def redact_sensitive_data(val: Any) -> Any:
    """Recursively redacts sensitive values from dictionaries, lists, and strings."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if str(k).lower() in SENSITIVE_KEYS:
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = redact_sensitive_data(v)
        return sanitized
    elif isinstance(val, list):
        return [redact_sensitive_data(item) for item in val]
    elif isinstance(val, tuple):
        return tuple(redact_sensitive_data(item) for item in val)
    elif isinstance(val, str):
        return redact_string(val)
    return val


def redact_sensitive_data_processor(logger, method_name, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Structlog processor that sanitizes the entire event dictionary."""
    return redact_sensitive_data(event_dict)


def setup_logger():
    """Configures structlog for JSON structured logging with redaction and contextvars."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive_data_processor,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("neurolab_api")


logger = setup_logger()


def bind_request_context(request_id: str, trace_id: str, user_id: str = "anonymous"):
    """Binds request identifiers to contextvars for structured log correlation."""
    bind_contextvars(
        request_id=request_id,
        trace_id=trace_id,
        user_id=user_id,
    )


def clear_request_context():
    """Clears contextvars after request processing."""
    clear_contextvars()
