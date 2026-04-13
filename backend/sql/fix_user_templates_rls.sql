-- ============================================================
-- user_templates 表 RLS 行级安全策略
-- 个人模板仅本人可见，公共模板全员可查看
-- 在 Supabase SQL Editor 中执行此脚本
-- ============================================================

-- 1. 确保 RLS 已启用
ALTER TABLE public.user_templates ENABLE ROW LEVEL SECURITY;

-- 2. 删除旧策略（如果存在）
DROP POLICY IF EXISTS "Allow all user_templates" ON public.user_templates;
DROP POLICY IF EXISTS "users_can_view_own_and_public_templates" ON public.user_templates;
DROP POLICY IF EXISTS "users_can_update_own_templates" ON public.user_templates;
DROP POLICY IF EXISTS "users_can_delete_own_templates" ON public.user_templates;
DROP POLICY IF EXISTS "users_can_insert_templates" ON public.user_templates;

-- 3. SELECT 策略：用户可以查看自己的模板 + 所有公共模板
CREATE POLICY "users_can_view_own_and_public_templates"
ON public.user_templates FOR SELECT
USING (
    auth.uid() = user_id
    OR visibility = 'public'
);

-- 4. INSERT 策略：认证用户可以插入模板（自动设置 user_id）
CREATE POLICY "users_can_insert_templates"
ON public.user_templates FOR INSERT
WITH CHECK (auth.uid() IS NOT NULL);

-- 5. UPDATE 策略：仅所有者可以更新自己的模板
CREATE POLICY "users_can_update_own_templates"
ON public.user_templates FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- 6. DELETE 策略：仅所有者可以删除自己的模板
CREATE POLICY "users_can_delete_own_templates"
ON public.user_templates FOR DELETE
USING (auth.uid() = user_id);
