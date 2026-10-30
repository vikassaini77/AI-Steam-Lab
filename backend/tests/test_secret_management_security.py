import os
import pytest
from app.core_backend.database.pgvector_db import (
    get_database_url,
    PGVectorManager,
    ConfigurationError,
)
from app.main import validate_production_configuration


def test_missing_postgres_url_raises_configuration_error(monkeypatch):
    """
    When POSTGRES_URL is missing, get_database_url() must raise a RuntimeError/ConfigurationError.
    """
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        get_database_url()
    assert "POSTGRES_URL must be configured" in str(exc_info.value)


def test_insecure_default_credentials_rejected(monkeypatch):
    """
    When POSTGRES_URL contains postgres:postgres, it must be rejected with a security violation.
    """
    monkeypatch.setenv(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/stemlab",
    )
    with pytest.raises(ConfigurationError) as exc_info:
        get_database_url()
    assert "postgres:postgres" in str(exc_info.value)
    assert "prohibited" in str(exc_info.value).lower() or "violation" in str(exc_info.value).lower()


def test_valid_postgres_url_accepted(monkeypatch):
    """
    When a non-default, valid connection string is provided, get_database_url() returns it.
    """
    valid_url = "postgresql://neurolab_app:StrongSecretPassword_2026!@db.internal:5432/neurolab"
    monkeypatch.setenv("POSTGRES_URL", valid_url)
    assert get_database_url() == valid_url


def test_pgvector_manager_production_fails_without_url(monkeypatch):
    """
    In production, PGVectorManager() must fail fast if POSTGRES_URL is missing.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    with pytest.raises(ConfigurationError):
        PGVectorManager()


def test_pgvector_manager_development_falls_back_safely(monkeypatch):
    """
    In development, missing POSTGRES_URL falls back to in-memory mode without touching postgres:postgres.
    """
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    manager = PGVectorManager()
    assert manager.url is None
    assert hasattr(manager, "fallback_memories")
    assert hasattr(manager, "fallback_xp")


def test_production_startup_validation_fails_when_all_databases_missing(monkeypatch):
    """
    Production startup fails fast if neither Supabase nor PostgreSQL is configured.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "Database configuration missing" in str(exc_info.value)


def test_production_startup_validation_fails_on_insecure_postgres_url(monkeypatch):
    """
    Production startup fails fast if POSTGRES_URL uses postgres:postgres.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/stemlab")

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "Insecure default credentials" in str(exc_info.value)


def test_production_startup_validation_succeeds_with_valid_credentials(monkeypatch):
    """
    Production startup passes when valid credentials are provided.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SUPABASE_URL", "https://valid-project.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "sb_publishable_valid_key_123")
    monkeypatch.setenv("POSTGRES_URL", "postgresql://app:StrongSecret@db:5432/app")
    # Should not raise any error
    validate_production_configuration()

