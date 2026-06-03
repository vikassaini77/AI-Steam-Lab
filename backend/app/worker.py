import os
from celery import Celery

# Configure Celery using the Redis URL from the environment (defaulting to localhost for local dev)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "neurolab_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
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
    }
)

@celery_app.task(bind=True, max_retries=3)
def process_heavy_cv_frame(self, frame_data: dict):
    """
    Stub for offloading YOLOv8 frame processing.
    In production, this would deserialize the frame and run YOLO inference
    asynchronously so the FastAPI thread doesn't block.
    """
    return {"status": "processed", "bounding_boxes": []}

@celery_app.task(bind=True, max_retries=3)
def generate_ai_tutor_response(self, prompt: str):
    """
    Stub for offloading Gemini LLM generation.
    Returns the response to a webhook or stores it in Redis for the client to poll.
    """
    return {"status": "generated", "response": "AI response generated in background."}
