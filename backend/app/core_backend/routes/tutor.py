import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.ai_agent.tutor_service import AITutorService

router = APIRouter()
tutor_service = AITutorService()

from typing import List, Optional, Dict, Any

class ChatRequest(BaseModel):
    prompt: str
    history: Optional[List[Dict[str, Any]]] = None
    experiment_state: Optional[Dict[str, Any]] = None

@router.get("/")
def get_tutor_status():
    return {"status": "Tutor endpoint is active."}

@router.post("/chat/stream")
async def chat_with_tutor(req: ChatRequest):
    return StreamingResponse(tutor_service.stream_chat(req), media_type="text/event-stream")

