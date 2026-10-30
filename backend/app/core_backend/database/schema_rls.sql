-- ==============================================================================
-- NeuroLab AI: PostgreSQL Row-Level Security (RLS) Policies
-- Enforces database-level multi-tenant user isolation on Supabase / PostgreSQL.
-- ==============================================================================

-- 1. Experiments Table
CREATE TABLE IF NOT EXISTS public.experiments (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    type TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS on experiments
ALTER TABLE public.experiments ENABLE ROW LEVEL SECURITY;

-- Experiment Policies: Each user can only view, insert, update, or delete their own experiments
CREATE POLICY "Users can only select their own experiments"
    ON public.experiments
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can only insert their own experiments"
    ON public.experiments
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can only update their own experiments"
    ON public.experiments
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can only delete their own experiments"
    ON public.experiments
    FOR DELETE
    USING (auth.uid() = user_id);


-- 2. User XP and Gamification Table
CREATE TABLE IF NOT EXISTS public.user_xp (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    xp INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS on user_xp
ALTER TABLE public.user_xp ENABLE ROW LEVEL SECURITY;

-- XP Policies: Users can view their own XP
CREATE POLICY "Users can view their own XP"
    ON public.user_xp
    FOR SELECT
    USING (auth.uid() = user_id);

-- System service role can award/update XP for gamification triggers
CREATE POLICY "Users can update their own XP"
    ON public.user_xp
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);


-- 3. AI Tutor Vector Memories Table (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.memories (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    session_id TEXT,
    text TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable RLS on memories
ALTER TABLE public.memories ENABLE ROW LEVEL SECURITY;

-- Memory Policies: Users can only query and insert into their own memory space
CREATE POLICY "Users can only access their own vector memories"
    ON public.memories
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

