from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
def login(req: LoginRequest):
    return {"token": "dummy_token_123", "user": {"email": req.email, "name": "Student"}}

@router.post("/register")
def register(req: LoginRequest):
    return {"status": "registered", "user": req.email}
