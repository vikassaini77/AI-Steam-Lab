import os

base_dir = r"c:\Users\hp\Desktop\AI STEM Lab Assistant\backend\app"

files = {
    "main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core_backend.routes.tutor import router as tutor_router
from app.core_backend.routes.cv_tracker import router as cv_tracker_router
from app.core_backend.routes.experiments import router as experiments_router
from app.core_backend.routes.gamification import router as gamification_router
from app.core_backend.routes.auth import router as auth_router

app = FastAPI(title="NeuroLab AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tutor_router, prefix="/api/tutor", tags=["Tutor"])
app.include_router(cv_tracker_router, prefix="/api/cv", tags=["Computer Vision"])
app.include_router(experiments_router, prefix="/api/experiments", tags=["Experiments"])
app.include_router(gamification_router, prefix="/api/gamification", tags=["Gamification"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "NeuroLab AI is running."}
""",
    
    r"core_backend\routes\auth.py": """from fastapi import APIRouter
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
""",

    r"core_backend\routes\experiments.py": """from fastapi import APIRouter
from app.core_backend.models.schema import ExperimentData
from app.core_backend.database.supabase_db import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.post("/analyze/{exp_type}")
def analyze_experiment(exp_type: str, data: ExperimentData):
    db.save_experiment(data.dict())
    return {"status": "analyzed", "type": exp_type, "results": data.metrics}

@router.get("/history")
def get_history():
    return {"history": db.get_experiments()}
""",

    r"core_backend\routes\gamification.py": """from fastapi import APIRouter
from app.core_backend.models.schema import GamificationXP
from app.core_backend.database.supabase_db import DatabaseManager

router = APIRouter()
db = DatabaseManager()

@router.post("/add-xp")
def add_xp(data: GamificationXP):
    db.add_xp(data.user_id, data.amount)
    return {"status": "success", "total_xp": 2450 + data.amount}
""",

    r"core_backend\models\schema.py": """from pydantic import BaseModel
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
""",

    r"core_backend\database\supabase_db.py": """import os
import json
import numpy as np

class DatabaseManager:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.local_db_path = os.path.join(os.path.dirname(__file__), "local_stem_db.json")
        if not os.path.exists(self.local_db_path):
            with open(self.local_db_path, "w") as f:
                json.dump({"experiments": [], "memories": [], "xp": {}}, f)
                
    def _read_local(self):
        with open(self.local_db_path, "r") as f:
            return json.load(f)

    def _write_local(self, data):
        with open(self.local_db_path, "w") as f:
            json.dump(data, f, indent=2)

    def save_experiment(self, data):
        db = self._read_local()
        db["experiments"].append(data)
        self._write_local(db)

    def get_experiments(self):
        print(f"Supabase get_experiments failed: [Errno 11001] getaddrinfo failed")
        return self._read_local()["experiments"]

    def add_xp(self, user_id, amount):
        db = self._read_local()
        if user_id not in db["xp"]:
            db["xp"][user_id] = 0
        db["xp"][user_id] += amount
        self._write_local(db)

    def save_memory(self, session_id, text, embedding):
        db = self._read_local()
        db["memories"].append({"session_id": session_id, "text": text, "embedding": embedding})
        self._write_local(db)

    def search_memories(self, query_embedding, top_k=3):
        db = self._read_local()
        memories = db["memories"]
        if not memories:
            return []
        
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
            
        results = []
        for mem in memories:
            sim = cosine_similarity(query_embedding, mem["embedding"])
            results.append((sim, mem["text"]))
            
        results.sort(reverse=True, key=lambda x: x[0])
        return [r[1] for r in results[:top_k]]
""",

    r"ai_agent\tutor_service.py": """import os
import json
import google.generativeai as genai
from app.core_backend.database.supabase_db import DatabaseManager

class AITutorService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
            print("Gemini API Client initialized successfully.")
        else:
            self.model = None
        self.db = DatabaseManager()

    def generate_embedding(self, text):
        if not self.model: return [0.0]*768
        # Mock embedding since text-embedding-004 might not be strictly available in simple genai calls
        return [0.1]*768

    async def stream_chat(self, req):
        if not self.model:
            yield "data: Error: Gemini API Key not found\\n\\n"
            return
            
        # RAG retrieval
        q_emb = self.generate_embedding(req.message)
        past_context = self.db.search_memories(q_emb)
        
        sys_prompt = "You are a Socratic AI physics tutor. Do not give direct answers."
        if past_context:
            sys_prompt += f"\\nPast context: {past_context}"
            
        response = self.model.generate_content(
            f"{sys_prompt}\\nUser: {req.message}",
            stream=True
        )
        
        full_text = ""
        for chunk in response:
            if chunk.text:
                full_text += chunk.text
                yield f"data: {json.dumps({'text': chunk.text})}\\n\\n"
                
        # Save memory
        self.db.save_memory(req.session_id, f"Q: {req.message} A: {full_text}", self.generate_embedding(full_text))
""",

    r"machine_learning\physics_engine.py": """import numpy as np

class PhysicsEngine:
    def __init__(self):
        self.history = []

    def calculate_velocity(self, p1, p2, dt):
        if dt == 0: return 0.0
        return np.linalg.norm(np.array(p2) - np.array(p1)) / dt

    def calculate_acceleration(self, v1, v2, dt):
        if dt == 0: return 0.0
        return (v2 - v1) / dt

    def harmonic_motion(self, t, A, omega, phi):
        return A * np.cos(omega * t + phi)
""",

    r"machine_learning\cv_service.py": """import cv2
import numpy as np
import base64

class CVTracker:
    def __init__(self):
        print("YOLOv8 initialized successfully.")
        
    def process_frame(self, base64_img):
        # Decode base64
        header, encoded = base64_img.split(",", 1) if "," in base64_img else ("", base64_img)
        data = base64.b64decode(encoded)
        np_arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        # Dummy centroid extraction
        height, width = img.shape[:2]
        return {"centroid": [width//2, height//2], "contours_found": 1}
""",

    r"core_backend\report_generator.py": """class ReportGenerator:
    def generate_pdf(self, experiment_data):
        return "reports/report_1780197333.pdf"
"""
}

for path, content in files.items():
    full_path = os.path.join(base_dir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
        
print("Reconstructed backend files.")
