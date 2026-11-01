"""
Pytest configuration and hermetic test environment initialization.
Problem 38: Run tests without production credentials, provide isolated service defaults,
and ensure hermetic test execution.
"""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Ensure hermetic, non-production credentials are set for test execution
os.environ["ENVIRONMENT"] = "test"
os.environ["TESTING"] = "true"
if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") == "unconfigured":
    os.environ["GEMINI_API_KEY"] = "test-mock-gemini-key"

os.environ.setdefault("SUPABASE_URL", "https://mock-supabase.test")
os.environ.setdefault("SUPABASE_KEY", "test-mock-supabase-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-mock-jwt-secret-at-least-32-chars-long")
os.environ.setdefault("METRICS_TOKEN", "test-mock-metrics-token")
os.environ.setdefault("ALLOW_FAKE_VECTORS", "true")
os.environ.setdefault("DISABLE_SENTRY", "true")
os.environ.setdefault("ALLOW_IN_MEMORY_FALLBACK", "true")

import pytest

@pytest.fixture(autouse=True)
def reset_global_observability_alerts():
    """Resets alert manager, circuit breaker, and contextvars between tests to prevent test cross-contamination."""
    try:
        from app.core_backend.core.observability import alert_manager
        alert_manager.clear()
    except Exception:
        pass
    try:
        from app.cache import clear_local_cache
        clear_local_cache()
    except Exception:
        pass
    try:
        from app.ai_agent.embedding_service import reset_embedding_circuit_breaker
        reset_embedding_circuit_breaker()
    except Exception:
        pass
    yield
    try:
        from app.core_backend.core.observability import alert_manager
        alert_manager.clear()
    except Exception:
        pass
    try:
        from app.cache import clear_local_cache
        clear_local_cache()
    except Exception:
        pass
    try:
        from app.ai_agent.embedding_service import reset_embedding_circuit_breaker
        reset_embedding_circuit_breaker()
    except Exception:
        pass
