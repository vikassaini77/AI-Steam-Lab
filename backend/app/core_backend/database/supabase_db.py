import os
import json
import numpy as np
import threading

db_lock = threading.Lock()

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
        with db_lock:
            db = self._read_local()
            db["experiments"].append(data)
            self._write_local(db)

    def get_experiments(self):
        print(f"Supabase get_experiments failed: [Errno 11001] getaddrinfo failed")
        with db_lock:
            return self._read_local()["experiments"]

    def add_xp(self, user_id, amount):
        with db_lock:
            db = self._read_local()
            if user_id not in db["xp"]:
                db["xp"][user_id] = 0
            db["xp"][user_id] += amount
            self._write_local(db)

    def save_memory(self, session_id, text, embedding):
        with db_lock:
            db = self._read_local()
            db["memories"].append({"session_id": session_id, "text": text, "embedding": embedding})
            self._write_local(db)

    def search_memories(self, query_embedding, top_k=3):
        with db_lock:
            db = self._read_local()
        memories = db["memories"]
        if not memories:
            return []
        
        def cosine_similarity(a, b):
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return np.dot(a, b) / (norm_a * norm_b)
            
        results = []
        for mem in memories:
            sim = cosine_similarity(query_embedding, mem["embedding"])
            results.append((sim, mem["text"]))
            
        results.sort(reverse=True, key=lambda x: x[0])
        return [r[1] for r in results[:top_k]]
