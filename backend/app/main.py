from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, Depends, APIRouter
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
load_dotenv()
import sentry_sdk
from prometheus_fastapi_instrumentator import Instrumentator

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.logger import logger
from app.core_backend.core.limiter import limiter
from app.core_backend.core.metrics_auth import verify_metrics_access
from app.core_backend.core.security_headers import SecurityHeadersMiddleware

from app.core_backend.routes.tutor import router as tutor_router
from app.core_backend.routes.cv_tracker import router as cv_tracker_router
from app.core_backend.routes.experiments import router as experiments_router
from app.core_backend.routes.gamification import router as gamification_router
from app.core_backend.routes.auth import router as auth_router

from app.core_backend.database.pgvector_db import (
    init_database_pool,
    close_database_pool,
    check_database_readiness,
)
from app.core_backend.core.dependencies import get_database_manager
from app.ai_agent.tutor_service import (
    AITutorService,
    get_tutor_executor,
    shutdown_tutor_executor,
)

# Initialize Sentry for APM and Error Tracking
# Policy: Optional for core functionality, but failures should be observable
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_STATUS: dict = {"configured": bool(SENTRY_DSN), "initialized": False, "error": None}
if SENTRY_DSN:
    try:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
        SENTRY_STATUS["initialized"] = True
        logger.info("Sentry APM initialized successfully")
    except Exception as sentry_err:
        SENTRY_STATUS["error"] = str(sentry_err)
        logger.warning(
            f"Sentry APM initialization failed ({type(sentry_err).__name__}): {sentry_err}. "
            "Continuing application startup without Sentry APM (safe degradation)."
        )

def validate_production_configuration():
    """
    Validates required production environment configuration on application startup.
    Fails fast in production if required secrets, origins, or database configurations are missing/insecure.
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        # 1. Database Configuration
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        postgres_url = os.getenv("POSTGRES_URL")

        if not (supabase_url and supabase_key) and not postgres_url:
            raise RuntimeError(
                "Production Startup Failure: Database configuration missing. "
                "Either SUPABASE_URL and SUPABASE_KEY or POSTGRES_URL must be configured."
            )

        if postgres_url:
            if "postgres:postgres@" in postgres_url:
                raise RuntimeError(
                    "Production Startup Failure: Insecure default credentials ('postgres:postgres') detected in POSTGRES_URL."
                )
            if ("@localhost:" in postgres_url or "@127.0.0.1:" in postgres_url) and os.getenv("IS_CONTAINER", "").lower() in ("true", "1"):
                raise RuntimeError(
                    "Production Startup Failure: POSTGRES_URL points to 'localhost' inside a container. Use the Compose service hostname 'db:5432' instead."
                )

        # 2. Check CORS origins
        if "*" in ALLOWED_ORIGINS:
            raise RuntimeError(
                "Production Startup Failure: Wildcard '*' in ALLOWED_ORIGINS is prohibited when allow_credentials=True."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_configuration()

    # 1. Initialize PostgreSQL connection pool during application lifespan startup
    postgres_url = os.getenv("POSTGRES_URL")
    if postgres_url:
        try:
            init_database_pool(url=postgres_url)
            logger.info("Database connection pool successfully initialized during lifespan startup.")
        except Exception as e:
            logger.warning(f"Database connection pool initialization deferred/warning: {e}")

    # 2. Initialize shared thread-safe database manager and attach to app.state
    db = get_database_manager()
    app.state.db = db

    # 3. Initialize thread pool executor and attach to app.state
    tutor_executor = get_tutor_executor()
    app.state.tutor_executor = tutor_executor

    # 4. Initialize AITutorService sharing thread-safe DB and executor, attach to app.state
    tutor_service = AITutorService(db=db, executor=tutor_executor)
    app.state.tutor_service = tutor_service
    logger.info("Shared services (db, tutor_service, tutor_executor) initialized during lifespan startup.")

    yield

    # Gracefully close resources during shutdown
    try:
        close_database_pool()
        logger.info("Database connection pool closed during lifespan shutdown.")
    except Exception as e:
        logger.warning(f"Error closing database connection pool during shutdown: {e}")

    try:
        shutdown_tutor_executor(wait=False)
        logger.info("Tutor thread pool executor closed during lifespan shutdown.")
    except Exception as e:
        logger.warning(f"Error shutting down tutor executor during shutdown: {e}")

    # Clean up app.state
    if hasattr(app.state, "db"):
        delattr(app.state, "db")
    if hasattr(app.state, "tutor_service"):
        delattr(app.state, "tutor_service")
    if hasattr(app.state, "tutor_executor"):
        delattr(app.state, "tutor_executor")


app = FastAPI(title="NeuroLab AI API", version="1.0.0", lifespan=lifespan)

# Instrument Prometheus Metrics with authentication and access control
Instrumentator().instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
    tags=["Monitoring"],
    dependencies=[Depends(verify_metrics_access)],
)
logger.info("Prometheus metrics instrumented at /metrics (access protected)")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply comprehensive browser and network security headers
app.add_middleware(SecurityHeadersMiddleware)

# Strict CORS configuration
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:80,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Unversioned API routes (backward-compatible legacy surface)
app.include_router(tutor_router, prefix="/api/tutor", tags=["Tutor"])
app.include_router(cv_tracker_router, prefix="/api/cv", tags=["Computer Vision"])
app.include_router(experiments_router, prefix="/api/experiments", tags=["Experiments"])
app.include_router(gamification_router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

# Versioned v1 API routes (explicit version contract surface)
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(tutor_router, prefix="/tutor", tags=["Tutor (v1)"])
v1_router.include_router(cv_tracker_router, prefix="/cv", tags=["Computer Vision (v1)"])
v1_router.include_router(experiments_router, prefix="/experiments", tags=["Experiments (v1)"])
v1_router.include_router(gamification_router, prefix="/gamification", tags=["Gamification (v1)"])
v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication (v1)"])
app.include_router(v1_router)

@app.get("/")
@limiter.limit("10/minute")
def health_check(request: Request):
    return {"status": "ok", "message": "NeuroLab AI is securely running."}

@app.get("/ready")
@limiter.limit("30/minute")
def readiness_check(request: Request, response: Response):
    """
    Readiness probe validating real database connectivity.
    Returns 200 when database is healthy/ready, 503 if unreachable in production.
    """
    from app.core_backend.database.pgvector_db import check_database_readiness
    readiness = check_database_readiness()
    if readiness.get("status") == "unhealthy":
        response.status_code = 503
    return readiness

@app.get("/metrics/database")
@app.get("/api/monitoring/db-metrics")
@limiter.limit("60/minute")
def get_db_metrics(request: Request):
    """
    Exposes operational database failure, connection, and retry telemetry metrics.
    """
    from app.core_backend.database.pgvector_db import get_database_metrics
    return {"status": "ok", "metrics": get_database_metrics()}

@app.get("/api/dependencies")
@app.get("/api/system/dependencies")
@limiter.limit("60/minute")
async def get_dependency_status(request: Request):
    """
    Exposes explicit dependency criticality policies, failure behaviors, and live health status.
    Problem 30: Clearly separates essential services from optional dependencies.
    """
    from app.core_backend.core.dependency_policies import get_system_dependency_health
    return await get_system_dependency_health()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
