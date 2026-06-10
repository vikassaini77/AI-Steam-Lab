import os
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
import json

class PGVectorManager:
    def __init__(self):
        self.url = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/stemlab")
        self._init_db()

    def _get_conn(self):
        return psycopg2.connect(self.url)

    def _init_db(self):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # Enable pgvector
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    # Create memories table with vector column
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS memories (
                            id SERIAL PRIMARY KEY,
                            session_id TEXT,
                            text TEXT,
                            embedding VECTOR(768)
                        );
                    """)
                    # Create local db fallback table just in case
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_xp (
                            user_id TEXT PRIMARY KEY,
                            xp INTEGER
                        );
                    """)
                conn.commit()
            print("pgvector database initialized successfully.")
        except Exception as e:
            print(f"Failed to connect to postgres: {e}. Falling back to in-memory mode for hackathon.")
            self.fallback_memories = []
            self.fallback_xp = {}

    def save_memory(self, session_id, text, embedding):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO memories (session_id, text, embedding) VALUES (%s, %s, %s)",
                        (session_id, text, embedding)
                    )
                conn.commit()
        except Exception as e:
            print(f"PG Save error: {e}")
            if hasattr(self, 'fallback_memories'):
                self.fallback_memories.append({"session_id": session_id, "text": text, "embedding": embedding})

    def search_memories(self, query_embedding, query_text="", top_k=3):
        """
        Hybrid search using RRF (Reciprocal Rank Fusion).
        Combines pgvector cosine similarity with Postgres Full Text Search (BM25-like).
        """
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    # Convert embedding to string format for Postgres
                    emb_str = '[' + ','.join(map(str, query_embedding)) + ']'
                    
                    # We will use RRF in a single query by fetching top K for both and combining
                    query = """
                    WITH semantic_search AS (
                        SELECT id, text, embedding <=> %s::vector AS distance,
                               row_number() OVER (ORDER BY embedding <=> %s::vector) AS rank
                        FROM memories
                        ORDER BY distance LIMIT 20
                    ),
                    keyword_search AS (
                        SELECT id, text,
                               ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) AS bm25_score,
                               row_number() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), plainto_tsquery('english', %s)) DESC) AS rank
                        FROM memories
                        WHERE to_tsvector('english', text) @@ plainto_tsquery('english', %s)
                        ORDER BY bm25_score DESC LIMIT 20
                    )
                    SELECT COALESCE(s.text, k.text) as text,
                           COALESCE(1.0 / (60 + s.rank), 0.0) + COALESCE(1.0 / (60 + k.rank), 0.0) AS rrf_score,
                           s.distance
                    FROM semantic_search s
                    FULL OUTER JOIN keyword_search k ON s.id = k.id
                    ORDER BY rrf_score DESC
                    LIMIT %s;
                    """
                    
                    # Since we don't always have query_text passed in the current API,
                    # we will fallback to pure semantic if query_text is empty
                    if not query_text:
                        cur.execute("""
                            SELECT text, 1 - (embedding <=> %s::vector) AS cosine_sim
                            FROM memories
                            ORDER BY embedding <=> %s::vector
                            LIMIT %s;
                        """, (emb_str, emb_str, top_k))
                        
                        results = cur.fetchall()
                        # Threshold Check
                        valid_results = []
                        for row in results:
                            text, sim = row
                            if sim >= 0.72: # Confidence threshold
                                valid_results.append(text)
                        
                        if not valid_results and results:
                            return ["System: [LOW_CONFIDENCE] Let me think about this differently..."]
                        return valid_results
                        
                    cur.execute(query, (emb_str, emb_str, query_text, query_text, query_text, top_k))
                    results = cur.fetchall()
                    
                    return [row[0] for row in results]
                    
        except Exception as e:
            print(f"PG Search error: {e}")
            # Fallback
            if hasattr(self, 'fallback_memories') and self.fallback_memories:
                def cosine_similarity(a, b):
                    norm_a = np.linalg.norm(a)
                    norm_b = np.linalg.norm(b)
                    if norm_a == 0 or norm_b == 0:
                        return 0.0
                    return np.dot(a, b) / (norm_a * norm_b)
                results = []
                for mem in self.fallback_memories:
                    sim = cosine_similarity(query_embedding, mem["embedding"])
                    results.append((sim, mem["text"]))
                results.sort(reverse=True, key=lambda x: x[0])
                
                # Confidence check
                if results and results[0][0] < 0.72:
                    return ["System: [LOW_CONFIDENCE] Let me think about this differently..."]
                    
                return [r[1] for r in results[:top_k]]
            return []

    def add_xp(self, user_id, amount):
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_xp (user_id, xp)
                        VALUES (%s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET xp = user_xp.xp + EXCLUDED.xp;
                    """, (user_id, amount))
                conn.commit()
        except Exception as e:
            print(f"PG XP error: {e}")
            if hasattr(self, 'fallback_xp'):
                self.fallback_xp[user_id] = self.fallback_xp.get(user_id, 0) + amount
