import os
import re
import yaml
import pytest
from app.core_backend.core.config import Settings


def test_docker_compose_environment_contract_defined():
    """
    Problem 32 Verification:
    docker-compose.yml must define a single configuration contract for services,
    and explicitly pass POSTGRES_URL, REDIS_URL, and ALLOWED_ORIGINS.
    """
    compose_path = "docker-compose.yml"
    assert os.path.exists(compose_path), "docker-compose.yml not found"

    with open(compose_path, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    # 1. Configuration contract defined
    assert "x-service-config-contract" in compose_cfg, (
        "docker-compose.yml must define 'x-service-config-contract' configuration contract"
    )

    services = compose_cfg.get("services", {})
    assert "backend" in services, "Missing backend service in docker-compose.yml"
    assert "celery_worker" in services, "Missing celery_worker service in docker-compose.yml"

    # 2. backend service environment assertions
    backend_env = services["backend"].get("environment", [])
    backend_env_str = " ".join(backend_env)

    # POSTGRES_URL passed to backend
    assert any(e.startswith("POSTGRES_URL=") for e in backend_env), (
        "backend service must receive POSTGRES_URL"
    )
    assert "@db:5432/" in backend_env_str, "backend POSTGRES_URL must point to db:5432"

    # REDIS_URL set for Compose
    redis_env = next((e for e in backend_env if e.startswith("REDIS_URL=")), None)
    assert redis_env is not None, "backend service must receive REDIS_URL"
    assert "redis://redis:6379/0" in redis_env, "backend REDIS_URL must target redis://redis:6379/0"

    # ALLOWED_ORIGINS set to actual frontend origins
    origins_env = next((e for e in backend_env if e.startswith("ALLOWED_ORIGINS=")), None)
    assert origins_env is not None, "backend service must receive ALLOWED_ORIGINS"
    assert "localhost:8080" in origins_env, "ALLOWED_ORIGINS must include proxy port 8080"
    assert "localhost:5173" in origins_env, "ALLOWED_ORIGINS must include Vite dev server port 5173"
    assert "127.0.0.1:8080" in origins_env
    assert "127.0.0.1:5173" in origins_env

    # 3. celery_worker service environment assertions
    worker_env = services["celery_worker"].get("environment", [])
    worker_env_str = " ".join(worker_env)

    # POSTGRES_URL passed to workers
    assert any(e.startswith("POSTGRES_URL=") for e in worker_env), (
        "celery_worker service must receive POSTGRES_URL"
    )
    assert "@db:5432/" in worker_env_str, "celery_worker POSTGRES_URL must point to db:5432"

    # REDIS_URL passed to workers
    worker_redis = next((e for e in worker_env if e.startswith("REDIS_URL=")), None)
    assert worker_redis is not None, "celery_worker service must receive REDIS_URL"
    assert "redis://redis:6379/0" in worker_redis, "celery_worker REDIS_URL must target redis://redis:6379/0"


def test_env_example_files_have_no_real_credentials():
    """
    Problem 32 Verification:
    .env.example in root and backend must contain placeholders only, without real credentials.
    """
    for env_path in [".env.example", os.path.join("backend", ".env.example")]:
        assert os.path.exists(env_path), f"{env_path} not found"
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check required variables are present
        assert "POSTGRES_URL" in content, f"{env_path} missing POSTGRES_URL"
        assert "REDIS_URL" in content, f"{env_path} missing REDIS_URL"
        assert "ALLOWED_ORIGINS" in content, f"{env_path} missing ALLOWED_ORIGINS"
        assert "redis://redis:6379/0" in content, f"{env_path} missing default REDIS_URL"

        # Check that actual secrets are not leaked
        assert "generate_a_strong_database_password_here" in content or "your_" in content
        assert "AIzaSy" not in content, f"{env_path} contains potential real Google API key"
        assert "postgres:postgres@" not in content, f"{env_path} contains insecure default credentials"


def test_settings_startup_validation_validates_redis_url(monkeypatch):
    """
    Problem 32 Verification:
    Startup validation fails fast on malformed REDIS_URL.
    """
    monkeypatch.setenv("REDIS_URL", "http://not-a-redis-url:6379")
    settings = Settings()
    with pytest.raises(ValueError) as exc_info:
        settings.validate_startup()
    assert "REDIS_URL" in str(exc_info.value)
    assert "redis://" in str(exc_info.value)


def test_settings_startup_validation_rejects_container_localhost(monkeypatch):
    """
    Problem 32 Verification:
    Startup validation rejects localhost inside container mode.
    """
    monkeypatch.setenv("IS_CONTAINER", "true")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:pass@localhost:5432/stemlab")
    settings = Settings()
    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_startup()
    assert "localhost" in str(exc_info.value)
    assert "db:5432" in str(exc_info.value)


def test_settings_startup_validation_production_security(monkeypatch):
    """
    Problem 32 Verification:
    Startup validation rejects missing database, insecure credentials, and wildcards in production.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    settings = Settings()
    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_startup()
    assert "Database configuration missing" in str(exc_info.value)

    # Insecure credentials
    monkeypatch.setenv("POSTGRES_URL", "postgresql://postgres:postgres@db:5432/stemlab")
    with pytest.raises(RuntimeError) as exc_info2:
        settings.validate_startup()
    assert "postgres:postgres" in str(exc_info2.value)

    # Wildcard origin with credentials
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app:strong_pass@db:5432/stemlab")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*,http://localhost:8080")
    with pytest.raises(RuntimeError) as exc_info3:
        settings.validate_startup()
    assert "Wildcard '*'" in str(exc_info3.value)


def test_settings_parsed_allowed_origins():
    """
    Problem 32 Verification:
    parsed_allowed_origins properly strips whitespace and trailing slashes.
    """
    settings = Settings(
        allowed_origins=" http://localhost:8080/ , http://127.0.0.1:8080/ , https://neurolab.ai "
    )
    origins = settings.parsed_allowed_origins
    assert origins == [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://neurolab.ai",
    ]

