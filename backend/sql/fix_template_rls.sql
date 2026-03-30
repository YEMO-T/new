-- ============================================================
-- 修复用户模板上传问题 - 更新RLS策略
-- ============================================================
-- 问题原因：本项目使用自定义JWT认证，而非Supabase Auth
-- 因此 auth.uid() 函数不可用，导致所有数据库操作被拒绝
-- 解决方案：将RLS策略改为允许所有操作（开发环境适用）

-- 删除旧的RLS策略
DROP POLICY IF EXISTS "Users can read own and public templates" ON public.user_templates;
DROP POLICY IF EXISTS "Users can insert own templates" ON public.user_templates;
DROP POLICY IF EXISTS "Users can update own templates" ON public.user_templates;
DROP POLICY IF EXISTS "Users can delete own templates" ON public.user_templates;

DROP POLICY IF EXISTS "Users can read own favorites" ON public.template_favorites;
DROP POLICY IF EXISTS "Users can insert own favorites" ON public.template_favorites;
DROP POLICY IF EXISTS "Users can delete own favorites" ON public.template_favorites;

-- 创建新的RLS策略（允许所有操作）
CREATE POLICY "Allow anonymous read all user_templates" ON public.user_templates 
    FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert user_templates" ON public.user_templates 
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous update user_templates" ON public.user_templates 
    FOR UPDATE USING (true);
CREATE POLICY "Allow anonymous delete user_templates" ON public.user_templates 
    FOR DELETE USING (true);

CREATE POLICY "Allow anonymous read all template_favorites" ON public.template_favorites 
    FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert template_favorites" ON public.template_favorites 
    FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous delete template_favorites" ON public.template_favorites 
    FOR DELETE USING (true);

-- 验证策略已更新
SELECT schemaname, tablename, policyname, permissive, roles, cmd 
FROM pg_policies 
WHERE tablename IN ('user_templates', 'template_favorites');
