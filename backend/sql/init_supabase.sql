-- ============================================================
-- 豆沙包教师助手 - 数据库初始化脚本
-- ============================================================
-- 面向高中和大学教学的RAG知识库系统
-- ============================================================

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- 1. 用户表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'teacher',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 2. 聊天记录表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    type TEXT DEFAULT 'text',
    file_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.messages(user_id);

-- ============================================================
-- 3. 课件表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.coursewares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    slides JSONB NOT NULL,
    lesson_plan JSONB,
    interaction JSONB,
    template_id UUID,
    template_info JSONB,
    file_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_coursewares_user_id ON public.coursewares(user_id);

-- ============================================================
-- 4. 系统模板表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    author TEXT,
    category TEXT,
    usage_count INTEGER DEFAULT 0,
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- 5. 导出记录表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    format TEXT NOT NULL,
    size TEXT,
    file_url TEXT,
    template_used UUID,
    source_type TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exports_user_id ON public.exports(user_id);

-- ============================================================
-- 6. 用户自定义模板表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.user_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    source_type TEXT NOT NULL,
    visibility TEXT DEFAULT 'private' CHECK (visibility IN ('private', 'public')),
    template_data JSONB NOT NULL,
    slides_structure JSONB,
    theme_colors JSONB,
    fonts JSONB,
    placeholders JSONB,
    thumbnail_url TEXT,
    original_file_name TEXT,
    original_file_size TEXT,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS file_path TEXT;
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS file_bucket TEXT;
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS thumbnail_path TEXT;
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS has_original_file BOOLEAN DEFAULT FALSE;
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS applicable_scenarios TEXT;

CREATE INDEX IF NOT EXISTS idx_user_templates_user_id ON public.user_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_user_templates_visibility ON public.user_templates(visibility);
CREATE INDEX IF NOT EXISTS idx_user_templates_category ON public.user_templates(category);

-- ============================================================
-- 7. 模板收藏表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.template_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES public.user_templates(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, template_id)
);

CREATE INDEX IF NOT EXISTS idx_template_favorites_user_id ON public.template_favorites(user_id);

-- ============================================================
-- 8. RAG知识库主表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.knowledge_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'txt',
    size TEXT,
    tags JSONB,
    content TEXT,
    status TEXT DEFAULT 'completed',
    file_url TEXT,
    file_original_name TEXT,
    
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'public')),
    grade_level TEXT,
    subject TEXT,
    description TEXT,
    
    education_level TEXT CHECK (education_level IN ('senior_high', 'university', 'junior_high', 'primary', 'exam', 'vocational', 'general')),
    semester TEXT,
    chapter TEXT,
    resource_type TEXT CHECK (resource_type IN ('textbook', 'curriculum', 'question_bank', 'notes', 'exam_paper', 'other')),
    source TEXT,
    knowledge_points JSONB,
    difficulty TEXT CHECK (difficulty IN ('basic', 'intermediate', 'advanced', 'exam')),
    
    vector_status TEXT DEFAULT 'pending' CHECK (vector_status IN ('pending', 'processing', 'completed', 'failed')),
    chunk_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS grade_level TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS education_level TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS semester TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS chapter TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS resource_type TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS knowledge_points JSONB;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS difficulty TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS vector_status TEXT DEFAULT 'pending';
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0;

ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS file_path TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS file_bucket TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS file_mime_type TEXT;
ALTER TABLE public.knowledge_items ADD COLUMN IF NOT EXISTS has_original_file BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_knowledge_items_user ON public.knowledge_items(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_visibility ON public.knowledge_items(visibility);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_vector_status ON public.knowledge_items(vector_status);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_grade_subject ON public.knowledge_items(grade_level, subject);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_education ON public.knowledge_items(education_level);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_resource_type ON public.knowledge_items(resource_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_full_classify ON public.knowledge_items(education_level, grade_level, subject);

-- ============================================================
-- 9. 知识向量表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.knowledge_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_item_id UUID REFERENCES public.knowledge_items(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    vector_embedding vector(384),
    source_resource TEXT,
    page_number INTEGER,
    confidence_score FLOAT DEFAULT 1.0,
    education_level TEXT,
    subject TEXT,
    grade_level TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.knowledge_vectors ADD COLUMN IF NOT EXISTS education_level TEXT;
ALTER TABLE public.knowledge_vectors ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE public.knowledge_vectors ADD COLUMN IF NOT EXISTS grade_level TEXT;

CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_embedding 
    ON public.knowledge_vectors USING ivfflat (vector_embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_item ON public.knowledge_vectors(knowledge_item_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_classify ON public.knowledge_vectors(education_level, subject, grade_level);

-- ============================================================
-- 10. 向量化日志表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.vectorization_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_item_id UUID REFERENCES public.knowledge_items(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    chunk_count INTEGER,
    error_message TEXT,
    processing_time_ms INTEGER,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vectorization_logs_item ON public.vectorization_logs(knowledge_item_id);

-- ============================================================
-- 11. 搜索历史表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    grade TEXT,
    subject TEXT,
    results_count INTEGER DEFAULT 0,
    top_confidence_score FLOAT,
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_history_user ON public.search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_search_history_time ON public.search_history(searched_at DESC);

-- ============================================================
-- 12. RAG对话表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.rag_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_conversations_user ON public.rag_conversations(user_id);

CREATE TABLE IF NOT EXISTS public.rag_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES public.rag_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_messages_conversation ON public.rag_messages(conversation_id);

-- ============================================================
-- 13. 教学资源表
-- ============================================================

CREATE TABLE IF NOT EXISTS public.teaching_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_name TEXT NOT NULL,
    grade_level TEXT NOT NULL,
    subject TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    storage_path TEXT,
    download_url TEXT,
    is_public BOOLEAN DEFAULT true,
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preview_url TEXT,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_teaching_resources_grade_subject ON public.teaching_resources(grade_level, subject);
CREATE INDEX IF NOT EXISTS idx_teaching_resources_type ON public.teaching_resources(resource_type);

-- ============================================================
-- 14. 视图
-- ============================================================

CREATE OR REPLACE VIEW public.preset_knowledge_view AS
SELECT 
    id, name, education_level, grade_level, subject, semester, chapter,
    resource_type, source, difficulty, tags, knowledge_points,
    content, chunk_count, vector_status, created_at
FROM public.knowledge_items
WHERE visibility = 'public' AND user_id IS NULL;

CREATE OR REPLACE VIEW public.knowledge_stats_view AS
SELECT 
    education_level, grade_level, subject, resource_type,
    COUNT(*) as total_items,
    SUM(chunk_count) as total_chunks,
    COUNT(CASE WHEN vector_status = 'completed' THEN 1 END) as vectorized_items
FROM public.knowledge_items
WHERE visibility = 'public'
GROUP BY education_level, grade_level, subject, resource_type
ORDER BY education_level, grade_level, subject;

-- ============================================================
-- 15. 触发器：自动更新 updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_user_templates_updated_at ON public.user_templates;
CREATE TRIGGER update_user_templates_updated_at
    BEFORE UPDATE ON public.user_templates
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_knowledge_items_updated_at ON public.knowledge_items;
CREATE TRIGGER update_knowledge_items_updated_at
    BEFORE UPDATE ON public.knowledge_items
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_rag_conversations_updated_at ON public.rag_conversations;
CREATE TRIGGER update_rag_conversations_updated_at
    BEFORE UPDATE ON public.rag_conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- 16. RLS 行级安全策略
-- ============================================================

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coursewares ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exports ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.template_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.knowledge_vectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vectorization_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rag_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teaching_resources ENABLE ROW LEVEL SECURITY;

-- users
DROP POLICY IF EXISTS "Allow all users" ON public.users;
CREATE POLICY "Allow all users" ON public.users FOR ALL USING (true);

-- messages
DROP POLICY IF EXISTS "Allow all messages" ON public.messages;
CREATE POLICY "Allow all messages" ON public.messages FOR ALL USING (true);

-- coursewares
DROP POLICY IF EXISTS "Allow all coursewares" ON public.coursewares;
CREATE POLICY "Allow all coursewares" ON public.coursewares FOR ALL USING (true);

-- templates
DROP POLICY IF EXISTS "Allow read templates" ON public.templates;
CREATE POLICY "Allow read templates" ON public.templates FOR SELECT USING (true);

-- exports
DROP POLICY IF EXISTS "Allow all exports" ON public.exports;
CREATE POLICY "Allow all exports" ON public.exports FOR ALL USING (true);

-- user_templates
DROP POLICY IF EXISTS "Allow all user_templates" ON public.user_templates;
CREATE POLICY "Allow all user_templates" ON public.user_templates FOR ALL USING (true);

-- template_favorites
DROP POLICY IF EXISTS "Allow all template_favorites" ON public.template_favorites;
CREATE POLICY "Allow all template_favorites" ON public.template_favorites FOR ALL USING (true);

-- knowledge_items
DROP POLICY IF EXISTS "Allow all knowledge" ON public.knowledge_items;
CREATE POLICY "Allow all knowledge" ON public.knowledge_items FOR ALL USING (true);

-- knowledge_vectors
DROP POLICY IF EXISTS "Allow read vectors" ON public.knowledge_vectors;
CREATE POLICY "Allow read vectors" ON public.knowledge_vectors FOR SELECT USING (true);

-- vectorization_logs
DROP POLICY IF EXISTS "Allow read logs" ON public.vectorization_logs;
CREATE POLICY "Allow read logs" ON public.vectorization_logs FOR SELECT USING (true);

-- search_history
DROP POLICY IF EXISTS "Allow all search_history" ON public.search_history;
CREATE POLICY "Allow all search_history" ON public.search_history FOR ALL USING (true);

-- rag_conversations
DROP POLICY IF EXISTS "Allow all rag_conversations" ON public.rag_conversations;
CREATE POLICY "Allow all rag_conversations" ON public.rag_conversations FOR ALL USING (true);

-- rag_messages
DROP POLICY IF EXISTS "Allow all rag_messages" ON public.rag_messages;
CREATE POLICY "Allow all rag_messages" ON public.rag_messages FOR ALL USING (true);

-- teaching_resources
DROP POLICY IF EXISTS "Allow public resources" ON public.teaching_resources;
CREATE POLICY "Allow public resources" ON public.teaching_resources FOR SELECT USING (is_public = true);

-- ============================================================
-- 17. 系统用户（用于预设知识库）
-- ============================================================

INSERT INTO public.users (id, email, username, hashed_password, role)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'system@preset-knowledge.local',
    '系统预设知识库',
    'system_preset_user',
    'admin'
) ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 完成
-- ============================================================

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '数据库初始化完成!';
    RAISE NOTICE '表总数: %', table_count;
    RAISE NOTICE '========================================';
END $$;
