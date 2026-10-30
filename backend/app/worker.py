"""
Celery Worker and Asynchronous Task Broker
Problem 30: Redis task broker is REQUIRED when asynchronous tasks are enabled.
Fail task dispatch with TaskBrokerUnavailableError (HTTP 503) if broker is offline.
"""
import os
from typing import Dict, Any, Optional
from celery import Celery
from app.logger import logger

# Configure Celery using the Redis URL from the environment
REDIS_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "neurolab_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.worker.process_heavy_cv_frame": {"queue": "cv_tasks"},
        "app.worker.generate_ai_tutor_response": {"queue": "ai_tasks"},
    },
)


class TaskBrokerUnavailableError(RuntimeError):
    """Raised when an asynchronous task cannot be dispatched because the broker is unreachable."""
    pass


def check_broker_health() -> Dict[str, Any]:
    """
    Inspects Redis task broker connectivity.
    Policy: Required when asynchronous tasks are enabled.
    """
    async_enabled = os.getenv("ASYNC_TASKS_ENABLED", "false").lower() in ("true", "1", "yes")
    import redis
    broker_url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        r = redis.from_url(broker_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        pong = r.ping()
        return {
            "status": "healthy" if pong else "unhealthy",
            "connected": bool(pong),
            "criticality": "required_when_async_tasks_enabled",
            "async_tasks_enabled": async_enabled,
        }
    except Exception as e:
        status_str = "unhealthy" if async_enabled else "disabled"
        return {
            "status": status_str,
            "connected": False,
            "criticality": "required_when_async_tasks_enabled",
            "async_tasks_enabled": async_enabled,
            "error": str(e),
        }


def dispatch_async_task(task, *args, **kwargs):
    """
    Dispatches a task with explicit broker dependency enforcement:
    - If ASYNC_TASKS_ENABLED=true: The task broker is REQUIRED. If unreachable, raises TaskBrokerUnavailableError.
    - If ASYNC_TASKS_ENABLED=false: Runs synchronously inline.
    """
    async_enabled = os.getenv("ASYNC_TASKS_ENABLED", "false").lower() in ("true", "1", "yes")
    if not async_enabled:
        # Run synchronously inline without requiring broker
        return task(*args, **kwargs)

    # When async tasks are enabled, verify broker health before dispatching
    health = check_broker_health()
    if not health.get("connected"):
        logger.error(f"Task broker unavailable: cannot dispatch async task {getattr(task, 'name', str(task))}: {health.get('error')}")
        raise TaskBrokerUnavailableError(
            f"Redis task broker is required when asynchronous tasks are enabled, but is unreachable: {health.get('error')}"
        )
    return task.delay(*args, **kwargs)


@celery_app.task(bind=True, max_retries=3)
def process_heavy_cv_frame(self, frame_data: dict):
    """
    Offloads heavy YOLOv8 frame processing.
    """
    return {"status": "processed", "bounding_boxes": []}


@celery_app.task(bind=True, max_retries=3)
def generate_ai_tutor_response(self, prompt: str):
    """
    Offloads Gemini LLM generation.
    """
    return {"status": "generated", "response": "AI response generated in background."}


@celery_app.task(bind=True)
def check_worker_db_connectivity(self):
    """
    Verifies that the Celery worker can connect to the canonical PostgreSQL database service.
    """
    from app.core_backend.database.pgvector_db import PGVectorManager
    manager = PGVectorManager()
    return manager.check_readiness()
