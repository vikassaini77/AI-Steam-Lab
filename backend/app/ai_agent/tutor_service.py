import os
import json # trigger reload
import asyncio
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
        return [0.1]*768

    async def stream_chat(self, req):
        if not self.model:
            yield f"data: {json.dumps({'text': 'Error: GEMINI_API_KEY is missing in backend/.env'})}\n\n"
            return
            
        try:
            prompt_lower = req.prompt.lower()
            
            # --- PHASE 1 DEMO KILLER FEATURE LOGIC ---
            
            if "i don't understand newton's 3rd law" in prompt_lower or "i do not understand newton's 3rd law" in prompt_lower:
                # Step 1-3: Socratic Question
                demo_response = "I see you're having trouble with Newton's 3rd Law. Let's think about it together: If you push a wall, what do you feel pushing back?"
                for char in demo_response:
                    yield f"data: {json.dumps({'text': char})}\n\n"
                    await asyncio.sleep(0.01)
                return

            if "[system: engagement_spike]" in prompt_lower:
                # Step 5: Engagement Detected -> Visual Analogy + Micro-quiz
                demo_response = "Exactly! 🧱 The wall pushes back with the exact same force. Think of it like this: If a rocket pushes hot gas downwards 🚀, what happens to the rocket?"
                for char in demo_response:
                    yield f"data: {json.dumps({'text': char})}\n\n"
                    await asyncio.sleep(0.01)
                return

            if "it goes up" in prompt_lower or "goes up" in prompt_lower or "moves up" in prompt_lower:
                # Step 6: Correct Answer -> Advance Node
                demo_response = "Correct! 🚀 Concept Mastered. You've just unlocked a new node in your Knowledge Graph!"
                for char in demo_response:
                    yield f"data: {json.dumps({'text': char})}\n\n"
                    await asyncio.sleep(0.01)
                
                # Advance KG Node
                try:
                    self.db.add_xp("local_session", 100) # Give 100 XP
                except Exception as e:
                    print(f"Error adding XP: {e}")
                    
                yield f"data: {json.dumps({'kg_update': 'Newton\\'s 3rd Law Mastered'})}\n\n"
                return
            
            # --- NORMAL RAG FLOW ---

            try:
                q_emb = self.generate_embedding(req.prompt)
                past_context = self.db.search_memories(q_emb)
            except Exception as db_err:
                print(f"Supabase RAG Error: {db_err}")
                past_context = ""
            
            sys_prompt = "You are a Socratic AI physics tutor. Do not give direct answers. If the user is confused, ask a simple guiding question."
            if past_context:
                sys_prompt += f"\nPast context: {past_context}"
                
            response = self.model.generate_content(
                f"{sys_prompt}\nUser: {req.prompt}",
                stream=True
            )
            
            full_text = ""
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                    
            try:
                session_id = getattr(req, 'session_id', 'local_session')
                self.db.save_memory(session_id, f"Q: {req.prompt} A: {full_text}", self.generate_embedding(full_text))
            except Exception as save_err:
                print(f"Supabase Save Error: {save_err}")
                
        except Exception as e:
            yield f"data: {json.dumps({'text': f'**AI Error:** {str(e)}'})}\n\n"
