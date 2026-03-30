-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 存储聊天记录及历史会话
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    type TEXT DEFAULT 'text', -- 'text', 'file', 'plan'
    file_info JSONB, -- 存储上传的文件信息如 name, size, type 等
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 存储生成的课件及教案设计
CREATE TABLE public.coursewares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    slides JSONB NOT NULL, -- 存储课件的内容数组
    lesson_plan JSONB, -- 存储教案结构
    interaction JSONB, -- 存储设定的互动环节
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 存储上传到知识库的教学材料信息
CREATE TABLE public.knowledge_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- 'pdf', 'docx'
    size TEXT NOT NULL,
    tags JSONB,
    status TEXT DEFAULT 'completed', -- 'completed', 'syncing'
    file_url TEXT, -- 如果存储在 Supabase Storage 中的引用
    content TEXT, -- 存储提取出的文本内容用于 RAG
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 开启 RLS 策略 (Row Level Security)。本应用为演示目的允许所有公开读写。
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all messages" ON public.messages FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert messages" ON public.messages FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous delete messages" ON public.messages FOR DELETE USING (true);

ALTER TABLE public.coursewares ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all coursewares" ON public.coursewares FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert coursewares" ON public.coursewares FOR INSERT WITH CHECK (true);

ALTER TABLE public.knowledge_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all knowledge" ON public.knowledge_items FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert knowledge" ON public.knowledge_items FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous delete knowledge" ON public.knowledge_items FOR DELETE USING (true);
CREATE POLICY "Allow anonymous update knowledge" ON public.knowledge_items FOR UPDATE USING (true);

-- 存储用户信息
CREATE TABLE public.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT DEFAULT 'teacher', -- 'teacher', 'admin'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 开启 RLS 策略。允许所有公开读写以便开发环境下进行认证逻辑测试。
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all users" ON public.users FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert users" ON public.users FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous update users" ON public.users FOR UPDATE USING (true);

-- 存储教学模板
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

-- 存储导出记录
CREATE TABLE IF NOT EXISTS public.exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.users(id),
    title TEXT NOT NULL,
    format TEXT NOT NULL, -- 'PPTX', 'DOCX', 'PDF'
    size TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 为新表开启 RLS
ALTER TABLE public.templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read templates" ON public.templates FOR SELECT USING (true);

ALTER TABLE public.exports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all exports" ON public.exports FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert exports" ON public.exports FOR INSERT WITH CHECK (true);

-- 插入一些初始模板数据
INSERT INTO public.templates (title, description, author, category, usage_count, image_url) VALUES
('基础几何学互动讲义', '涵盖平面几何核心概念，包含交互式练习。', '李老师', '数学', 1200, 'https://picsum.photos/seed/math/400/300'),
('植物的光合作用百科', '生动的生物学课件，包含动画演示。', '张老师', '生物', 856, 'https://picsum.photos/seed/bio/400/300'),
('诗词赏析与创作练习', '优美的语文课件，激发学生创作灵感。', '陈老师', '语文', 2300, 'https://picsum.photos/seed/poem/400/300'),
('未来信息技术发展史', '科技感十足的课件，探索IT前沿。', '王老师', '信息', 540, 'https://picsum.photos/seed/tech/400/300');

-- 用户自定义PPT模板库
CREATE TABLE IF NOT EXISTS public.user_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- 学术、趣味互动、简约白板、科学探究、艺术创作等
    source_type TEXT NOT NULL,  -- 'upload' (上传PPT), 'saved_courseware' (课件保存)
    visibility TEXT DEFAULT 'private',  -- 'private' (个人专用), 'public' (公共模板)
    
    -- 模板内容和样式
    template_data JSONB NOT NULL,  -- 完整PPT结构和样式信息
    slides_structure JSONB,  -- 幻灯片版式信息
    theme_colors JSONB,  -- 配色方案
    fonts JSONB,  -- 字体配置
    placeholders JSONB,  -- 占位符定义
    
    -- 元数据
    thumbnail_url TEXT,  -- 缩略图 URL
    original_file_name TEXT,  -- 原始文件名
    original_file_size TEXT,  -- 原始文件大小
    usage_count INTEGER DEFAULT 0,  -- 使用次数
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_templates_user_id ON public.user_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_user_templates_visibility ON public.user_templates(visibility);
CREATE INDEX IF NOT EXISTS idx_user_templates_category ON public.user_templates(category);

-- 模板收藏记录
CREATE TABLE IF NOT EXISTS public.template_favorites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    template_id UUID NOT NULL REFERENCES public.user_templates(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, template_id)
);

CREATE INDEX IF NOT EXISTS idx_template_favorites_user_id ON public.template_favorites(user_id);

-- 为新表开启 RLS
-- 注意：由于本项目使用自定义JWT认证而非Supabase Auth，auth.uid()不可用
-- 因此这里采用允许所有操作的策略（开发环境）
ALTER TABLE public.user_templates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all user_templates" ON public.user_templates 
    FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert user_templates" ON public.user_templates 
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous update user_templates" ON public.user_templates 
    FOR UPDATE USING (true);
CREATE POLICY "Allow anonymous delete user_templates" ON public.user_templates 
    FOR DELETE USING (true);

ALTER TABLE public.template_favorites ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous read all template_favorites" ON public.template_favorites 
    FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert template_favorites" ON public.template_favorites 
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous delete template_favorites" ON public.template_favorites 
    FOR DELETE USING (true);

-- 修改coursewares表，添加模板关联
ALTER TABLE public.coursewares ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.users(id);
ALTER TABLE public.coursewares ADD COLUMN IF NOT EXISTS template_id UUID REFERENCES public.user_templates(id);
ALTER TABLE public.coursewares ADD COLUMN IF NOT EXISTS template_info JSONB;

-- 修改exports表，添加模板信息
ALTER TABLE public.exports ADD COLUMN IF NOT EXISTS template_used UUID REFERENCES public.user_templates(id);
ALTER TABLE public.exports ADD COLUMN IF NOT EXISTS source_type TEXT;  -- 'template_applied', 'default', 'ai_generated'

CREATE INDEX IF NOT EXISTS idx_coursewares_user_id ON public.coursewares(user_id);
CREATE INDEX IF NOT EXISTS idx_coursewares_template_id ON public.coursewares(template_id);
