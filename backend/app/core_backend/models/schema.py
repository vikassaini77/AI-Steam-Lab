from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ChatRequest(BaseModel):
    session_id: str
    message: str
    context: Optional[Dict[str, Any]] = None

class ExperimentData(BaseModel):
    user_id: str
    type: str
    metrics: Dict[str, Any]

class GamificationXP(BaseModel):
    user_id: str
    action: str
    amount: int
