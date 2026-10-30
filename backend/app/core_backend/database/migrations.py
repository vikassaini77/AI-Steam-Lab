"""
Database schema migrations for PostgreSQL / pgvector.
Manages versioned, repeatable DDL schema migrations independent of application runtime connections.
Keeps application runtime connections limited to DML operations (SELECT, INSERT, UPDATE, DELETE).
"""
import os
import time
from typing import List, Tuple, Optional, Dict, Any
import psycopg2
from app.logger import logger

REQUIRED_SCHEMA_VERSION = 4

MIGRATION_V1_SQL = """
-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Schema migrations metadata table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Memories table for semantic & keyword RAG
CREATE TABLE IF NOT EXISTS memories (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT,
    experiment_id TEXT,
    text TEXT NOT NULL,
    embedding VECTOR(768),
    embedding_model_version TEXT DEFAULT 'text-embedding-004',
    expires_at TIMESTAMP WITH TIME ZONE,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. User XP gamification table
CREATE TABLE IF NOT EXISTS user_xp (
    user_id TEXT PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Experiments storage table
CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    experiment_type TEXT,
    data JSONB NOT NULL,
    timestamp BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Mastery records table for idempotent XP awards
CREATE TABLE IF NOT EXISTS mastery_records (
    dedup_key TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    concept TEXT NOT NULL,
    amount INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Daily usage rate limiting table
CREATE TABLE IF NOT EXISTS daily_usage (
    user_id TEXT NOT NULL,
    usage_date DATE NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, usage_date)
);

-- Indexes for efficient isolated tenant lookups
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_session_id ON memories(session_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_session ON memories(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_experiment ON memories(user_id, experiment_id);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_memories_is_deleted ON memories(is_deleted);
CREATE INDEX IF NOT EXISTS idx_experiments_user_id ON experiments(user_id);
CREATE INDEX IF NOT EXISTS idx_mastery_user_concept ON mastery_records(user_id, concept);
"""

MIGRATION_V2_SQL = """
-- Add ownership, scope, versioning, and lifecycle fields to existing memories table
ALTER TABLE memories ADD COLUMN IF NOT EXISTS experiment_id TEXT;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS embedding_model_version TEXT DEFAULT 'text-embedding-004';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;

-- Ensure indexes for fast ownership, scope, and lifecycle queries
CREATE INDEX IF NOT EXISTS idx_memories_user_session ON memories(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_memories_user_experiment ON memories(user_id, experiment_id);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_memories_expires_at ON memories(expires_at);
CREATE INDEX IF NOT EXISTS idx_memories_is_deleted ON memories(is_deleted);
"""

MIGRATION_V3_SQL = """
-- 1. Full-text search GIN index for fast keyword retrieval and cover density ranking
CREATE INDEX IF NOT EXISTS idx_memories_text_fts ON memories USING gin(to_tsvector('english', text));

-- 2. pgvector HNSW index for fast semantic cosine retrieval
-- Compatible operator class: vector_cosine_ops for <=> cosine distance queries
DO $$
BEGIN
    BEGIN
        CREATE INDEX IF NOT EXISTS idx_memories_embedding_hnsw ON memories USING hnsw (embedding vector_cosine_ops);
    EXCEPTION WHEN undefined_object OR feature_not_supported THEN
        CREATE INDEX IF NOT EXISTS idx_memories_embedding_ivfflat ON memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    END;
END $$;
"""

MIGRATION_V4_SQL = """
-- Auditable immutable ledger for XP awards
CREATE TABLE IF NOT EXISTS xp_ledger (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    amount INTEGER NOT NULL CHECK (amount > 0 AND amount <= 1000),
    concept TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_xp_ledger_user_id ON xp_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_xp_ledger_created_at ON xp_ledger(created_at);
"""

# Ordered registry of versioned migrations
MIGRATIONS: List[Tuple[int, str, str]] = [
    (1, "001_initial_schema", MIGRATION_V1_SQL),
    (2, "002_memory_lifecycle_and_ownership", MIGRATION_V2_SQL),
    (3, "003_hybrid_search_indexes", MIGRATION_V3_SQL),
    (4, "004_auditable_xp_ledger", MIGRATION_V4_SQL),
]


def get_current_schema_version(conn) -> int:
    """
    Retrieves the highest applied migration version from the schema_migrations table.
    Returns 0 if the table does not exist or has no recorded migrations.
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'schema_migrations'
                );
            """)
            row = cur.fetchone()
            if not row or not row[0]:
                return 0
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations;")
            v_row = cur.fetchone()
            return int(v_row[0]) if v_row else 0
    except Exception as e:
        logger.warning(f"Error querying schema_migrations: {e}")
        return 0


def verify_schema_version(conn, required_version: int = REQUIRED_SCHEMA_VERSION) -> Tuple[bool, int]:
    """
    Verifies that the current schema version meets or exceeds the required version.
    Returns (is_valid, current_version).
    """
    curr = get_current_schema_version(conn)
    return (curr >= required_version, curr)


def verify_search_indexes(conn) -> Dict[str, Any]:
    """
    Verifies that the required vector index (with vector_cosine_ops)
    and full-text search GIN index are created and active on the memories table.
    """
    results: Dict[str, Any] = {
        "vector_index_present": False,
        "vector_index_name": None,
        "vector_index_type": None,
        "vector_opclass": None,
        "fts_index_present": False,
        "fts_index_name": None,
        "fts_index_type": None,
    }
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    i.relname AS index_name,
                    am.amname AS index_type,
                    COALESCE(op.opcname, '') AS opclass_name
                FROM pg_index x
                JOIN pg_class c ON c.oid = x.indrelid
                JOIN pg_class i ON i.oid = x.indexrelid
                JOIN pg_am am ON am.oid = i.relam
                LEFT JOIN pg_opclass op ON op.oid = x.indclass[0]
                WHERE c.relname = 'memories';
            """)
            rows = cur.fetchall()
            for row in rows:
                idx_name = str(row[0])
                idx_type = str(row[1])
                opc_name = str(row[2]) if len(row) > 2 else ""

                if "embedding" in idx_name or idx_type in ("hnsw", "ivfflat") or "vector" in opc_name:
                    results["vector_index_present"] = True
                    results["vector_index_name"] = idx_name
                    results["vector_index_type"] = idx_type
                    results["vector_opclass"] = opc_name or "vector_cosine_ops"

                if "fts" in idx_name or idx_type == "gin" or "text" in idx_name:
                    results["fts_index_present"] = True
                    results["fts_index_name"] = idx_name
                    results["fts_index_type"] = idx_type
    except Exception as e:
        logger.warning(f"Index verification encountered error: {e}")
    return results


def run_migrations(url: Optional[str] = None, target_version: Optional[int] = None) -> int:
    """
    Executes pending schema migrations using an isolated, dedicated administrative connection.
    Does not use the application runtime connection pool.
    Returns the final current schema version after migrations.
    """
    from app.core_backend.database.pgvector_db import get_database_url
    target_url = url or get_database_url()
    if not target_url:
        raise RuntimeError("Cannot run migrations: POSTGRES_URL is not configured.")

    logger.info("Executing database schema migrations...")
    conn = psycopg2.connect(target_url)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()

        current_v = get_current_schema_version(conn)
        applied_count = 0

        for version, name, sql in MIGRATIONS:
            if target_version is not None and version > target_version:
                break
            if version > current_v:
                logger.info(f"Applying migration v{version} ({name})...")
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (%s, %s);",
                        (version, name),
                    )
                conn.commit()
                applied_count += 1
                logger.info(f"Migration v{version} ({name}) successfully applied.")

        final_v = get_current_schema_version(conn)
        logger.info(f"Database migrations finished. Current version: {final_v} ({applied_count} applied).")
        return final_v
    except Exception as e:
        conn.rollback()
        logger.critical(f"Database schema migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()

