from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os
from dotenv import load_dotenv
load_dotenv()
import sentry_sdk
from prometheus_fastapi_instrumentator import Instrumentator

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.logger import logger

from app.core_backend.routes.tutor import router as tutor_router
from app.core_backend.routes.cv_tracker import router as cv_tracker_router
from app.core_backend.routes.experiments import router as experiments_router
from app.core_backend.routes.gamification import router as gamification_router
from app.core_backend.routes.auth import router as auth_router

# Initialize Sentry for APM and Error Tracking
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("Sentry APM initialized")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="NeuroLab AI API", version="1.0.0")

# Instrument Prometheus Metrics
Instrumentator().instrument(app).expose(app)
logger.info("Prometheus metrics instrumented at /metrics")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Strict CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:80,http://127.0.0.1:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(tutor_router, prefix="/api/tutor", tags=["Tutor"])
app.include_router(cv_tracker_router, prefix="/api/cv", tags=["Computer Vision"])
app.include_router(experiments_router, prefix="/api/experiments", tags=["Experiments"])
app.include_router(gamification_router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

@app.get("/")
@limiter.limit("10/minute")
def health_check(request: Request):
    return {"status": "ok", "message": "NeuroLab AI is securely running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
