"""
Unit and Integration Tests for Problems 38, 39, and 40:
CI Pipeline Enforcement, Mandatory Testing, Strict Linting, and Reproducible Dependencies.

Verifies:
- Problem 38: Backend tests are mandatory; missing tests directory or files fails CI;
  coverage reporting is configured; tests run without production secrets; isolated service containers used.
- Problem 39: Critical Ruff rules are enforced without --exit-zero; TypeScript type checking is blocking;
  frontend linter runs without suppressing exit status.
- Problem 40: Dependency versions in requirements.txt and package.json are pinned (no open-ended >= or ^);
  lockfiles exist; CI strictly uses npm ci without falling back to npm install.
"""
import re
import yaml
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
CI_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"

from app.core_backend.core.test_suite_verifier import (
    verify_test_suite_presence,
    REQUIRED_CATEGORIES,
    MIN_TEST_FILES,
)


def load_ci_workflow() -> dict:
    assert CI_WORKFLOW_PATH.exists(), f"ci.yml not found at {CI_WORKFLOW_PATH}"
    return yaml.safe_load(CI_WORKFLOW_PATH.read_text(encoding="utf-8"))


def load_ci_workflow_raw() -> str:
    return CI_WORKFLOW_PATH.read_text(encoding="utf-8")


class TestProblem38BackendTestsMandatory:
    """Verifies backend tests cannot be skipped, service containers exist, and coverage is tracked."""

    def test_ci_does_not_contain_skip_fallback_echo(self):
        """Workflow must not skip tests when tests folder is missing."""
        raw_wf = load_ci_workflow_raw()
        assert "No tests folder found, skipping." not in raw_wf
        assert "else echo" not in raw_wf

    def test_ci_contains_mandatory_test_verifier_step(self):
        """Workflow must run test_suite_verifier with --verify-all before pytest."""
        raw_wf = load_ci_workflow_raw()
        assert "test_suite_verifier" in raw_wf
        assert "--verify-all" in raw_wf

    def test_verifier_passes_on_current_test_suite(self):
        """Verifier passes on the current repository test suite."""
        valid, errors = verify_test_suite_presence(BACKEND_DIR / "tests")
        assert valid is True
        assert len(errors) == 0

    def test_verifier_fails_when_tests_directory_missing(self):
        """Removing or renaming tests directory must fail verification."""
        with TemporaryDirectory() as tmp_dir:
            missing_tests_path = Path(tmp_dir) / "nonexistent_tests"
            valid, errors = verify_test_suite_presence(missing_tests_path)
            assert valid is False
            assert any("does not exist" in err for err in errors)

    def test_verifier_fails_when_required_category_missing(self):
        """Renaming or removing required test categories (e.g. auth security) fails verification."""
        with TemporaryDirectory() as tmp_dir:
            tmp_tests = Path(tmp_dir) / "tests"
            tmp_tests.mkdir()
            
            # Create dummy tests for unit and integration, but omit api_authorization
            for category in ["unit", "integration"]:
                for filename in REQUIRED_CATEGORIES[category]:
                    (tmp_tests / filename).write_text("def test_dummy(): pass", encoding="utf-8")
            
            # Pad with extra tests to meet count threshold
            for i in range(15):
                (tmp_tests / f"test_extra_{i}.py").write_text("def test_dummy(): pass", encoding="utf-8")

            valid, errors = verify_test_suite_presence(tmp_tests)
            assert valid is False
            assert any("Missing required api_authorization test files" in err for err in errors)

    def test_ci_runs_without_production_credentials(self):
        """Backend test step runs with mock/test credentials and no dependency on live secrets."""
        wf = load_ci_workflow()
        backend_job = wf["jobs"]["backend-tests"]
        test_step = next(s for s in backend_job["steps"] if "pytest tests/" in s.get("run", ""))
        step_env = test_step.get("env", {})
        
        # Must not require secrets.GEMINI_API_KEY or secrets.SUPABASE_URL
        for key, val in step_env.items():
            val_str = str(val)
            assert "secrets." not in val_str, f"Test environment variable {key} must not depend on live secrets"

        assert step_env.get("ENVIRONMENT") == "test"
        assert step_env.get("TESTING") == "true"
        assert "test-mock" in step_env.get("GEMINI_API_KEY", "")

    def test_ci_uses_dedicated_isolated_service_containers(self):
        """Backend test job configures isolated PostgreSQL (pgvector) and Redis service containers."""
        wf = load_ci_workflow()
        services = wf["jobs"]["backend-tests"].get("services", {})
        assert "postgres" in services
        assert "redis" in services
        assert "pgvector" in services["postgres"]["image"]
        assert "redis:7-alpine" in services["redis"]["image"]

    def test_ci_tracks_coverage_and_uploads_artifact(self):
        """Backend test step measures coverage and uploads coverage.xml artifact."""
        raw_wf = load_ci_workflow_raw()
        assert "--cov=app" in raw_wf
        assert "--cov-report=xml:coverage.xml" in raw_wf
        assert "backend-test-coverage" in raw_wf
        assert "coverage.xml" in raw_wf


class TestProblem39StrictLintingAndQualityGates:
    """Verifies Ruff and ESLint checks are blocking without --exit-zero or --if-present."""

    def test_ruff_does_not_use_exit_zero_on_blocking_check(self):
        """The blocking Ruff lint check step must not use --exit-zero."""
        wf = load_ci_workflow()
        backend_steps = wf["jobs"]["backend-tests"]["steps"]
        blocking_step = next(s for s in backend_steps if "Enforce critical Ruff" in s.get("name", ""))
        run_cmd = blocking_step.get("run", "")
        executable_lines = [l for l in run_cmd.splitlines() if not l.strip().startswith("#")]
        assert not any("--exit-zero" in l for l in executable_lines)
        assert any("--select=" in l for l in executable_lines)
        assert any("E9" in l for l in executable_lines)
        assert any("F821" in l for l in executable_lines)

    def test_frontend_runs_typescript_typecheck(self):
        """Frontend job must execute npm run typecheck."""
        wf = load_ci_workflow()
        frontend_steps = wf["jobs"]["frontend-build"]["steps"]
        typecheck_step = next((s for s in frontend_steps if "typecheck" in s.get("run", "")), None)
        assert typecheck_step is not None, "frontend-build must include 'npm run typecheck'"

    def test_frontend_linter_does_not_suppress_errors(self):
        """Frontend linter must run without --if-present or suppressing exit code."""
        wf = load_ci_workflow()
        frontend_steps = wf["jobs"]["frontend-build"]["steps"]
        lint_step = next((s for s in frontend_steps if "npm run lint" in s.get("run", "")), None)
        assert lint_step is not None, "frontend-build must include 'npm run lint'"
        assert "--if-present" not in lint_step.get("run", "")
        assert "|| true" not in lint_step.get("run", "")


class TestProblem40DeterministicDependencyVersions:
    """Verifies dependencies are pinned and reproducible across backend and frontend."""

    def test_backend_requirements_pinned_without_loose_wildcards(self):
        """backend/requirements.txt must not contain open-ended >= versions for dependencies."""
        req_path = BACKEND_DIR / "requirements.txt"
        assert req_path.exists()
        lines = [line.strip() for line in req_path.read_text(encoding="utf-8").splitlines()]
        
        dep_lines = [l for l in lines if l and not l.startswith("#")]
        assert len(dep_lines) >= 20
        
        for dep in dep_lines:
            assert ">=" not in dep, f"Dependency '{dep}' has open-ended '>=' minimum version instead of locked pin"
            assert "==" in dep, f"Dependency '{dep}' must use exact '==' version pin"

    def test_backend_requirements_lock_exists(self):
        """backend/requirements.lock must exist and contain exact pins."""
        lock_path = BACKEND_DIR / "requirements.lock"
        assert lock_path.exists()
        lock_lines = [l.strip() for l in lock_path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        assert len(lock_lines) >= 25
        for line in lock_lines:
            assert "==" in line

    def test_frontend_package_json_dependencies_are_pinned(self):
        """frontend/package.json must pin exact versions for dependencies without loose ^ wildcards."""
        import json
        pkg_path = FRONTEND_DIR / "package.json"
        assert pkg_path.exists()
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        deps = pkg_data.get("dependencies", {})
        
        assert len(deps) >= 15
        for name, version in deps.items():
            assert not version.startswith("^"), f"Dependency '{name}': '{version}' has loose '^' range"
            assert not version.startswith("~"), f"Dependency '{name}': '{version}' has loose '~' range"
            assert not version.startswith(">="), f"Dependency '{name}': '{version}' has loose '>=' range"

    def test_ci_uses_npm_ci_without_fallback(self):
        """frontend-build step must use strict 'npm ci' and never fall back to 'npm install'."""
        raw_wf = load_ci_workflow_raw()
        assert "npm ci || npm install" not in raw_wf
        assert "npm ci" in raw_wf


class TestProblem41FullDeploymentIntegrationJob:
    """Verifies that CI defines an end-to-end integration test job for the complete Compose stack."""

    def test_ci_contains_compose_deployment_integration_job(self):
        """Workflow must contain compose-deployment-integration job."""
        wf = load_ci_workflow()
        assert "compose-deployment-integration" in wf.get("jobs", {})

    def test_job_builds_frontend_and_backend_images(self):
        """Job builds both frontend and backend images via docker compose build."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        build_step = next((s for s in job["steps"] if "docker compose build" in s.get("run", "")), None)
        assert build_step is not None

    def test_job_applies_database_migrations_before_api(self):
        """Job runs database migrations as an explicit pre-start step."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        migration_step = next((s for s in job["steps"] if "run --rm migration" in s.get("run", "")), None)
        assert migration_step is not None

    def test_job_starts_api_worker_and_proxy(self):
        """Job starts backend, celery_worker, frontend, and proxy services."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        start_step = next((s for s in job["steps"] if "up -d backend" in s.get("run", "")), None)
        assert start_step is not None
        assert "celery_worker" in start_step["run"]
        assert "proxy" in start_step["run"]

    def test_job_polls_readiness_through_proxy(self):
        """Job waits for readiness at http://localhost:8080/ready through the proxy."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        readiness_step = next((s for s in job["steps"] if "wait_for_stack_readiness.py" in s.get("run", "")), None)
        assert readiness_step is not None
        assert "http://localhost:8080/ready" in readiness_step["run"]

    def test_job_executes_e2e_integration_tests(self):
        """Job runs the full end-to-end test suite (test_e2e_compose_deployment.py)."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        test_step = next((s for s in job["steps"] if "test_e2e_compose_deployment.py" in s.get("run", "")), None)
        assert test_step is not None

    def test_job_shuts_down_stack_and_uploads_logs_on_completion(self):
        """Job dumps logs, uploads artifact, and runs docker compose down -v with if: always()."""
        wf = load_ci_workflow()
        job = wf["jobs"]["compose-deployment-integration"]
        down_step = next((s for s in job["steps"] if "docker compose down" in s.get("run", "")), None)
        assert down_step is not None
        assert down_step.get("if") == "always()"
        assert "-v" in down_step["run"]

        upload_step = next((s for s in job["steps"] if "upload-artifact" in s.get("uses", "")), None)
        assert upload_step is not None
        assert upload_step.get("if") == "always()"
        assert upload_step["with"]["name"] == "compose-deployment-logs"
