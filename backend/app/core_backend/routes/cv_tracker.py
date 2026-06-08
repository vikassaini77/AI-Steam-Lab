from fastapi import APIRouter, Request
from pydantic import BaseModel
import json

router = APIRouter()

class EngagementEvent(BaseModel):
    user_id: str
    state: str # 'focused', 'confused', 'leaning_forward', 'disengaged'
    confidence: float

@router.get("/")
def get_cv_tracker_status():
    return {"status": "CV Tracker endpoint is active."}

@router.post("/process-frame")
async def process_frame(request: Request):
    data = await request.json()
    # Placeholder for actual OpenCV frame processing logic
    return {"message": "Frame processed successfully", "objects_detected": []}

@router.post("/engagement")
async def log_engagement(event: EngagementEvent):
    # Logs CV engagement state (e.g. leaning_forward) to the database or broadcast via WebSocket
    print(f"Engagement Event Logged: {event.state} with confidence {event.confidence}")
    return {"status": "success", "event": event.state}
