from pydantic import BaseModel, Field
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
    user_id: Optional[str] = None
    action: str = Field(default="general_award", max_length=100)
    amount: int = Field(..., gt=0, le=500, description="XP award amount, strictly positive and capped at 500")
    event_id: Optional[str] = Field(None, max_length=128, description="Unique client or event idempotency key")
    idempotency_key: Optional[str] = Field(None, max_length=128, description="Alias for event_id")
    concept: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
