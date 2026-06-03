import os
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
            yield "data: Error: Gemini API Key not found\n\n"
            return
            
        # RAG retrieval
        q_emb = self.generate_embedding(req.message)
        past_context = self.db.search_memories(q_emb)
        
        sys_prompt = "You are a Socratic AI physics tutor. Do not give direct answers."
        if past_context:
            sys_prompt += f"\nPast context: {past_context}"
            
        response = self.model.generate_content(
            f"{sys_prompt}\nUser: {req.message}",
            stream=True
        )
        
        full_text = ""
        for chunk in response:
            if chunk.text:
                full_text += chunk.text
                yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                
        # Save memory
        self.db.save_memory(req.session_id, f"Q: {req.message} A: {full_text}", self.generate_embedding(full_text))
