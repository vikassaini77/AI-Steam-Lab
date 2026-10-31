"""
NeuroLab AI: Application & Service Configuration Contract
Centralized Pydantic Settings formalizing configuration parameters, defaults, and startup safety validation.
Problem 32: Defines a single configuration contract for every service and validates required settings at startup.
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Formal single configuration contract for NeuroLab AI backend and worker services.
    Enforces required configuration, defaults, and startup safety validation.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="NeuroLab AI", description="Application service name")
    environment: str = Field(
        default="development",
        description="Deployment environment: development, test, staging, production",
    )
    is_container: bool = Field(
        default=False,
        description="Flag indicating if the service is running inside a Docker container",
    )
    port: int = Field(default=8000, description="Service listening port")
    host: str = Field(default="0.0.0.0", description="Service listening host")

    # Database & Storage Configuration Contract
    postgres_url: Optional[str] = Field(
        default=None,
        description="Canonical PostgreSQL connection string",
    )
    postgres_user: Optional[str] = Field(
        default="stemlab_app",
        description="PostgreSQL database user",
    )
    postgres_password: Optional[str] = Field(
        default=None,
        description="PostgreSQL database password",
    )
    postgres_db: Optional[str] = Field(
        default="stemlab",
        description="PostgreSQL database name",
    )

    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase API endpoint URL",
    )
    supabase_key: Optional[str] = Field(
        default=None,
        description="Supabase service/anon key",
    )

    # Cache & Task Broker Configuration Contract
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL for caching and asynchronous Celery tasks",
    )

    # AI & Model Service Configuration Contract
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="API key for Google Gemini generative AI models",
    )

    # Security & Networking Configuration Contract
    allowed_origins: str = Field(
        default="http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-delimited list of permitted CORS frontend origins",
    )
    metrics_token: Optional[str] = Field(
        default=None,
        description="Bearer token protecting Prometheus metrics scraper access",
    )
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry APM Data Source Name for telemetry",
    )
    enable_hsts: bool = Field(
        default=False,
        description="Whether to enforce HSTS headers over HTTPS",
    )

    @property
    def parsed_allowed_origins(self) -> List[str]:
        """Returns clean list of CORS origins without trailing slashes or empty items."""
        return [
            origin.strip().rstrip("/")
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]

    def validate_startup(self) -> None:
        """
        Validates the configuration contract at service startup.
        Fails fast if critical settings are missing, malformed, or violate security policies.
        """
        env = os.environ.get("ENVIRONMENT", self.environment).lower()
        is_container_flag = (
            os.environ.get("IS_CONTAINER", "").lower() in ("true", "1")
            or self.is_container
        )
        pg_url = os.environ.get("POSTGRES_URL")
        redis_conn = os.environ.get("REDIS_URL", self.redis_url)
        sb_url = os.environ.get("SUPABASE_URL")
        sb_key = os.environ.get("SUPABASE_KEY")
        raw_origins = os.environ.get("ALLOWED_ORIGINS", self.allowed_origins)

        # 1. Validate REDIS_URL
        if redis_conn:
            if not (redis_conn.startswith("redis://") or redis_conn.startswith("rediss://")):
                raise ValueError(
                    f"Configuration Error: Invalid REDIS_URL format '{redis_conn}'. "
                    "Must start with 'redis://' or 'rediss://'."
                )

        # 2. Validate Container POSTGRES_URL
        if is_container_flag and pg_url:
            if "@localhost:" in pg_url or "@127.0.0.1:" in pg_url:
                raise RuntimeError(
                    "Production Startup Failure: POSTGRES_URL points to 'localhost' inside a container. "
                    "Use the Compose service hostname 'db:5432' instead."
                )

        # 3. Validate Production Security Policies
        if env == "production":
            # Database presence
            has_supabase = bool(sb_url and sb_key)
            has_postgres = bool(pg_url)
            if not has_supabase and not has_postgres:
                raise RuntimeError(
                    "Production Startup Failure: Database configuration missing. "
                    "Either SUPABASE_URL and SUPABASE_KEY or POSTGRES_URL must be configured."
                )

            # Insecure default credentials check
            if pg_url and "postgres:postgres@" in pg_url:
                raise RuntimeError(
                    "Production Startup Failure: Insecure default credentials ('postgres:postgres') "
                    "detected in POSTGRES_URL."
                )

            # Wildcard CORS origins check with credentials
            origins_list = [o.strip() for o in raw_origins.split(",") if o.strip()]
            if "*" in origins_list:
                raise RuntimeError(
                    "Production Startup Failure: Wildcard '*' in ALLOWED_ORIGINS is prohibited "
                    "when allow_credentials=True."
                )


def get_settings() -> Settings:
    """Returns singleton Settings instance loaded from environment / .env."""
    global _global_settings
    if _global_settings is None:
        _global_settings = Settings()
    return _global_settings


_global_settings: Optional[Settings] = None
settings = Settings()
