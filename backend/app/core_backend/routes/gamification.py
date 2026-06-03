from fastapi import APIRouter
from app.core_backend.models.schema import GamificationXP
from app.core_backend.database.supabase_db import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.post("/add-xp")
def add_xp(data: GamificationXP):
    db.add_xp(data.user_id, data.amount)
    return {"status": "success", "total_xp": 2450 + data.amount}
