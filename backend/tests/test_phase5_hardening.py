"""
NeuroLab AI — Phase 5 Backend, Security, Database, and MLOps Hardening Test Suite
Verifies:
1. Authentication and Token Validation (Valid, Invalid signature, Expired, Revoked)
2. Strict Tenant Isolation and Authorization (Experiments, Memories, Tasks)
3. Database Probes and Readiness Monitoring (/ready, /live, /metrics/database)
4. Scientific Report Generation & Path Traversal Defense
5. Celery Asynchronous Report Task Execution and Idempotency
6. ML Model Lifecycle Metadata and Device Observability
7. Standardized Exception Handling and Request-ID Propagation
8. Security Headers and Cross-Origin Protections
"""
import os
import time
import uuid
import pytest
import jwt
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.token_revocation import revoke_token, clear_revoked_tokens
from app.core_backend.core.dependencies import reset_shared_dependencies
from app.worker import compile_experiment_report
from app.core_backend.core.report_generator import REPORTS_DIR

SECRET_KEY = "test-mock-jwt-secret-at-least-32-chars-long"
ISSUER = "https://mock-supabase.test/auth/v1"
AUDIENCE = "authenticated"


@pytest.fixture(autouse=True)
def clean_auth_state(monkeypatch):
    """Configures explicit local cryptographic JWT verification for all tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET_KEY)
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", ISSUER)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("SUPABASE_JWT_VERIFY_ISSUER", "true")
    reset_shared_dependencies()
    clear_revoked_tokens()
    yield
    reset_shared_dependencies()
    clear_revoked_tokens()


@pytest.fixture(scope="module")
def client():
    """TestClient instance for API integration testing."""
    return TestClient(app)


def create_test_jwt(
    user_id: str,
    email: str = "test@example.com",
    expires_in: int = 3600,
    secret: str = SECRET_KEY,
) -> str:
    """Creates a signed test JWT token."""
    payload = {
        "sub": user_id,
        "id": user_id,
        "email": email,
        "role": "authenticated",
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


# ==============================================================================
# 1. Authentication and Token Validation
# ==============================================================================

class TestAuthenticationAndTokenValidation:
    def test_valid_token_authenticated_profile(self, client):
        """A valid non-expired token grants access to authenticated profile."""
        uid = f"user_{uuid.uuid4().hex[:8]}"
        token = create_test_jwt(user_id=uid, email="scholar@neurolab.edu")
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["id"] == uid

    def test_invalid_signature_rejected_with_401(self, client):
        """Tokens with forged signatures are rejected with 401 Unauthorized."""
        tampered_token = create_test_jwt(user_id="spoofed_user", secret="wrong-forged-secret-key-at-least-32-chars-long")
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        assert res.status_code == 401
        assert "detail" in res.json()

    def test_expired_token_rejected_with_401(self, client):
        """Tokens with past expiration time are rejected with 401 Unauthorized."""
        uid = f"user_{uuid.uuid4().hex[:8]}"
        expired_token = create_test_jwt(user_id=uid, expires_in=-100)
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert res.status_code == 401
        assert "detail" in res.json()

    def test_revoked_token_rejected_with_401(self, client):
        """A logged-out / revoked token is immediately rejected with 401 Unauthorized."""
        uid = f"user_{uuid.uuid4().hex[:8]}"
        token = create_test_jwt(user_id=uid, expires_in=1800)
        
        # Verify valid before revocation
        res1 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res1.status_code == 200

        # Revoke token
        revoke_token(token, user_id=uid, expires_at=int(time.time()) + 1800)

        # Verify rejected after revocation
        res2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res2.status_code == 401
        assert "revoked" in str(res2.json()["detail"]).lower()


# ==============================================================================
# 2. Strict Tenant Isolation and Authorization
# ==============================================================================

class TestTenantIsolationAndAuthorization:
    def test_cannot_save_experiment_for_another_user(self, client):
        """A user cannot forge another user's user_id in an experiment save payload."""
        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        token_a = create_test_jwt(user_id=user_a)

        payload = {
            "user_id": user_b,
            "type": "pendulum",
            "name": "Spoofed Pendulum Run",
            "parameters": {"length": 2.0, "gravity": 9.81},
        }
        res = client.post(
            "/api/experiments/save",
            json=payload,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 403
        assert "Forbidden" in res.json()["detail"]

    def test_cannot_read_another_users_experiment_by_id(self, client):
        """User B cannot fetch an experiment created and owned by User A."""
        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        token_a = create_test_jwt(user_id=user_a)
        token_b = create_test_jwt(user_id=user_b)

        # User A saves an experiment
        save_res = client.post(
            "/api/experiments/save",
            json={"type": "pendulum", "name": "User A Pendulum", "parameters": {"length": 1.5}},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert save_res.status_code == 200
        exp_id = save_res.json()["experiment"]["id"]

        # User B attempts to read User A's experiment
        read_res = client.get(
            f"/api/experiments/experiment/{exp_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert read_res.status_code == 403
        assert "Forbidden" in read_res.json()["detail"]

    def test_cannot_delete_another_users_experiment(self, client):
        """User B cannot delete an experiment owned by User A."""
        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        token_a = create_test_jwt(user_id=user_a)
        token_b = create_test_jwt(user_id=user_b)

        save_res = client.post(
            "/api/experiments/save",
            json={"type": "free_fall", "name": "User A Drop", "parameters": {"height": 20.0}},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert save_res.status_code == 200
        exp_id = save_res.json()["experiment"]["id"]

        del_res = client.delete(
            f"/api/experiments/experiment/{exp_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_res.status_code == 403

    def test_cannot_access_another_users_task_results(self, client):
        """User B cannot inspect task outputs dispatched by User A."""
        user_a = f"user_a_{uuid.uuid4().hex[:6]}"
        user_b = f"user_b_{uuid.uuid4().hex[:6]}"
        token_a = create_test_jwt(user_id=user_a)
        token_b = create_test_jwt(user_id=user_b)

        # User A dispatches a task
        dispatch_res = client.post(
            "/api/tasks/tutor/generate-async",
            json={"prompt": "Explain Newton's third law of motion"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert dispatch_res.status_code == 200
        task_id = dispatch_res.json()["task_id"]

        # User B attempts to read User A's task
        task_res = client.get(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert task_res.status_code == 403


# ==============================================================================
# 3. Database Probes and System Readiness
# ==============================================================================

class TestDatabaseProbesAndReadiness:
    def test_liveness_probe_returns_alive(self, client):
        """Liveness check returns responsive in-process state without querying DB."""
        res = client.get("/live")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "alive"
        assert "uptime_seconds" in data
        assert "pid" in data

    def test_readiness_probe_structure_and_telemetry(self, client):
        """Readiness check inspects essential dependencies and reports telemetry."""
        res = client.get("/ready")
        assert res.status_code in (200, 503)
        data = res.json()
        assert "status" in data
        assert "dependencies" in data
        assert "database" in data["dependencies"]
        assert "model_provider" in data["dependencies"]
        assert "task_broker" in data["dependencies"]

    def test_database_metrics_endpoint(self, client):
        """Operational DB metrics endpoint reports connection and error counters."""
        res = client.get("/metrics/database")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "metrics" in data


# ==============================================================================
# 4. Scientific Report Generation & Path Traversal Defense
# ==============================================================================

class TestReportGenerationAndSecurity:
    def test_generate_and_download_report(self, client):
        """Generates a verified scientific report and downloads it via the returned URL."""
        payload = {
            "experiment_name": "Simple Pendulum Kinematics",
            "student_name": "Marie Curie",
            "metrics": {
                "period": "2.006 s",
                "length": "1.00 m",
                "gravity": "9.81 m/s²",
                "percentage_error": "0.15%",
            },
            "ai_summary": "The experimental period closely tracks the small-angle theoretical prediction T = 2π√(L/g).",
            "format": "html",
        }
        res = client.post("/api/experiments/generate-report", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "download_url" in data
        assert "filename" in data

        # Download the report
        dl_res = client.get(data["download_url"])
        assert dl_res.status_code == 200
        assert "text/html" in dl_res.headers.get("content-type", "")
        assert "Marie Curie" in dl_res.text
        assert "Simple Pendulum Kinematics" in dl_res.text

    def test_path_traversal_attack_blocked(self, client):
        """Filename path traversal attempts are rejected with 400 Bad Request."""
        res = client.get("/api/experiments/reports/..%2F..%2Fetc%2Fpasswd")
        assert res.status_code in (400, 404)

        res2 = client.get("/api/experiments/reports/../../../Windows/win.ini")
        assert res2.status_code in (400, 404)


# ==============================================================================
# 5. Celery Asynchronous Report Task Execution and Idempotency
# ==============================================================================

class TestCeleryReportTaskExecution:
    def test_compile_experiment_report_task_executes(self):
        """The compile_experiment_report Celery task compiles and returns a download URL."""
        task_payload = {
            "experiment_name": "Projectile Motion Ballistics",
            "student_name": "Isaac Newton",
            "metrics": {"range": "45.2 m", "max_height": "11.3 m"},
            "ai_summary": "Kinematic conservation of momentum and energy holds.",
            "format": "html",
            "idempotency_key": f"idem_rep_{uuid.uuid4().hex[:8]}",
        }
        result = compile_experiment_report(task_payload)
        assert result["status"] == "compiled"
        assert "filename" in result
        assert "download_url" in result
        assert os.path.exists(os.path.join(REPORTS_DIR, result["filename"]))

    def test_report_task_idempotency_deduplication(self):
        """Repeated tasks with identical idempotency key return cached result without duplicate compilation."""
        idem_key = f"idem_dup_{uuid.uuid4().hex[:8]}"
        task_payload = {
            "experiment_name": "Collision Momentum Test",
            "student_name": "Richard Feynman",
            "metrics": {"initial_momentum": "10.0 kg·m/s", "final_momentum": "10.0 kg·m/s"},
            "ai_summary": "1D elastic collision confirmed.",
            "idempotency_key": idem_key,
            "format": "html",
        }
        res1 = compile_experiment_report(task_payload)
        res2 = compile_experiment_report(task_payload)
        assert res1["filename"] == res2["filename"]
        assert res1["download_url"] == res2["download_url"]


# ==============================================================================
# 6. ML Model Lifecycle Metadata and Device Observability
# ==============================================================================

class TestMLModelLifecycleObservability:
    def test_cv_readiness_reports_model_lifecycle(self, client):
        """GET /api/cv/readiness returns model version, device, active detector, and memory."""
        res = client.get("/api/cv/readiness")
        assert res.status_code == 200
        data = res.json()
        assert "ready" in data
        assert "active_model" in data
        assert "active_detector" in data
        assert "model_version" in data
        assert "device" in data
        assert data["device"] in ("cpu", "cuda", "cuda:0")
        assert "memory_usage_mb" in data
        assert isinstance(data["memory_usage_mb"], (int, float))
        assert "model_metadata" in data
        assert "supported_methods" in data


# ==============================================================================
# 7. Standardized Exception Handling and Request-ID Propagation
# ==============================================================================

class TestExceptionHandlingAndObservability:
    def test_validation_error_returns_structured_422_with_request_id(self, client):
        """Malformed requests return structured 422 with validation errors and X-Request-ID."""
        res = client.post(
            "/api/experiments/calculate/pendulum",
            json={"parameters": {"length": -5.0}},  # Invalid length <= 0
        )
        assert res.status_code == 422
        data = res.json()
        assert "detail" in data
        assert "X-Request-ID" in res.headers
        assert res.headers["X-Request-ID"].startswith("req_")

    def test_x_request_id_and_trace_id_propagated_on_all_responses(self, client):
        """Every response returns X-Request-ID and X-Trace-ID headers for distributed tracing."""
        res = client.get("/")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        assert "X-Trace-ID" in res.headers


# ==============================================================================
# 8. Security Headers and CORS Protection
# ==============================================================================

class TestSecurityHeadersAndCORS:
    def test_security_headers_present(self, client):
        """Browser defensive security headers are attached to API responses."""
        res = client.get("/")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=(self)" in res.headers.get("Permissions-Policy", "")
        assert "Content-Security-Policy" in res.headers

    def test_cors_preflight_allowed_for_anna_and_vercel(self, client):
        """CORS OPTIONS preflight and cross-origin GET succeed for authorized Anna Partners domain."""
        # 1. Preflight OPTIONS check
        res_opts = client.options(
            "/api/experiments/metadata",
            headers={
                "Origin": "https://anna.partners",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res_opts.status_code == 200
        assert res_opts.headers.get("Access-Control-Allow-Origin") == "https://anna.partners"

        # 2. Simple GET check with exposed headers
        res_get = client.get(
            "/api/experiments/metadata",
            headers={"Origin": "https://anna.partners"},
        )
        assert res_get.status_code == 200
        assert res_get.headers.get("Access-Control-Allow-Origin") == "https://anna.partners"
        assert "X-Request-ID" in res_get.headers.get("Access-Control-Expose-Headers", "")
