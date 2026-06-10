from fastapi import APIRouter
from app.core_backend.models.schema import ExperimentData
from app.core_backend.database.supabase_db import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.post("/analyze/{exp_type}")
def analyze_experiment(exp_type: str, data: ExperimentData):
    db.save_experiment(data.model_dump())
    return {"status": "analyzed", "type": exp_type, "results": data.metrics}

@router.get("/history")
def get_history():
    return {"history": db.get_experiments()}
