-- ============================================================
-- RAG知识库表结构 - 阶段1完整实现
-- ============================================================

-- 启用pgvector扩展（如果未启用）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- 1. 官方教学资源库表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.teaching_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_name TEXT NOT NULL,
    grade_level TEXT NOT NULL,  -- 小学一年级、初中二年级、高中一年级等
    subject TEXT NOT NULL,  -- 数学、语文、英语、物理、化学等
    resource_type TEXT NOT NULL,  -- 教材、课标、课件、题库、PPT模板
    storage_path TEXT,  -- Supabase Storage路径
    download_url TEXT,  -- 公开下载链接
    is_public BOOLEAN DEFAULT true,  -- 公共资源标志
    created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preview_url TEXT,  -- 预览图URL
    description TEXT  -- 资源描述
);

-- 为teaching_resources创建索引
CREATE INDEX IF NOT EXISTS idx_teaching_resources_grade_subject
    ON public.teaching_resources(grade_level, subject);
CREATE INDEX IF NOT EXISTS idx_teaching_resources_type
    ON public.teaching_resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_teaching_resources_is_public
    ON public.teaching_resources(is_public);

-- ============================================================
-- 2. 课标库表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.curriculum_standards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grade TEXT NOT NULL,  -- 年级
    subject TEXT NOT NULL,  -- 学科
    standard_code TEXT NOT NULL,  -- 课标代码（如：3.1.1）
    standard_content TEXT NOT NULL,  -- 课标具体内容
    key_points JSONB,  -- 关键知识点数组
    vector_embedding vector(384),  -- 向量嵌入（384维）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为curriculum_standards创建索引
CREATE INDEX IF NOT EXISTS idx_curriculum_standards_grade_subject
    ON public.curriculum_standards(grade, subject);
CREATE INDEX IF NOT EXISTS idx_curriculum_standards_code
    ON public.curriculum_standards(standard_code);

-- ============================================================
-- 3. 知识点向量库表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.knowledge_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_item_id UUID REFERENCES public.knowledge_items(id) ON DELETE CASCADE,
    chunk_index INTEGER,  -- 文本块序号
    chunk_text TEXT NOT NULL,  -- 切块后的文本（512字符）
    vector_embedding vector(384),  -- 向量嵌入（384维）
    source_resource TEXT,  -- 来源资源名称
    page_number INTEGER,  -- 页码
    confidence_score FLOAT DEFAULT 0.0,  -- 置信度
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为knowledge_vectors创建向量索引（用于相似度搜索）
CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_embedding
    ON public.knowledge_vectors USING ivfflat (vector_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_knowledge_vectors_knowledge_item
    ON public.knowledge_vectors(knowledge_item_id);

-- ============================================================
-- 4. 修改knowledge_items表，添加向量化相关字段
-- ============================================================
ALTER TABLE public.knowledge_items
    ADD COLUMN IF NOT EXISTS vector_status TEXT DEFAULT 'pending';  -- pending, processing, completed, failed
ALTER TABLE public.knowledge_items
    ADD COLUMN IF NOT EXISTS chunk_count INTEGER DEFAULT 0;
ALTER TABLE public.knowledge_items
    ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false;
ALTER TABLE public.knowledge_items
    ADD COLUMN IF NOT EXISTS grade_level TEXT;  -- 年级
ALTER TABLE public.knowledge_items
    ADD COLUMN IF NOT EXISTS subject TEXT;  -- 学科

-- ============================================================
-- 5. 启用RLS策略
-- ============================================================

-- teaching_resources RLS
ALTER TABLE public.teaching_resources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public resources readable by all" ON public.teaching_resources;
CREATE POLICY "Public resources readable by all"
    ON public.teaching_resources FOR SELECT
    TO PUBLIC
    USING (is_public = true);

DROP POLICY IF EXISTS "Users can read own resources" ON public.teaching_resources;
CREATE POLICY "Users can read own resources"
    ON public.teaching_resources FOR SELECT
    TO authenticated
    USING (created_by = auth.uid() OR is_public = true);

DROP POLICY IF EXISTS "Users can insert own resources" ON public.teaching_resources;
CREATE POLICY "Users can insert own resources"
    ON public.teaching_resources FOR INSERT
    TO authenticated
    WITH CHECK (created_by = auth.uid());

DROP POLICY IF EXISTS "Users can update own resources" ON public.teaching_resources;
CREATE POLICY "Users can update own resources"
    ON public.teaching_resources FOR UPDATE
    TO authenticated
    USING (created_by = auth.uid())
    WITH CHECK (created_by = auth.uid());

DROP POLICY IF EXISTS "Users can delete own resources" ON public.teaching_resources;
CREATE POLICY "Users can delete own resources"
    ON public.teaching_resources FOR DELETE
    TO authenticated
    USING (created_by = auth.uid());

-- curriculum_standards RLS
ALTER TABLE public.curriculum_standards ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Curriculum standards readable by all" ON public.curriculum_standards;
CREATE POLICY "Curriculum standards readable by all"
    ON public.curriculum_standards FOR SELECT
    TO PUBLIC
    USING (true);

-- knowledge_vectors RLS
ALTER TABLE public.knowledge_vectors ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Knowledge vectors readable by all" ON public.knowledge_vectors;
CREATE POLICY "Knowledge vectors readable by all"
    ON public.knowledge_vectors FOR SELECT
    TO PUBLIC
    USING (true);

-- ============================================================
-- 6. 创建向量化处理日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.vectorization_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_item_id UUID REFERENCES public.knowledge_items(id) ON DELETE CASCADE,
    status TEXT NOT NULL,  -- success, failed
    chunk_count INTEGER,
    error_message TEXT,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vectorization_logs_item
    ON public.vectorization_logs(knowledge_item_id);

-- ============================================================
-- 7. 创建搜索历史表（用于优化和分析）
-- ============================================================
CREATE TABLE IF NOT EXISTS public.search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
    query TEXT NOT NULL,
    grade TEXT,
    subject TEXT,
    results_count INTEGER,
    top_confidence_score FLOAT,
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_search_history_user
    ON public.search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_search_history_grade_subject
    ON public.search_history(grade, subject);

-- ============================================================
-- 完成标记
-- ============================================================
-- 所有表创建完成，可以开始使用RAG功能
