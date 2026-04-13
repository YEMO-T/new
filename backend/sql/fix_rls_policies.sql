-- ============================================================
-- 修复 RLS 行级安全策略
-- ============================================================
-- 解决问题：当前策略过于宽松，允许所有用户访问私有数据
-- ============================================================

-- ============================================================
-- 1. user_templates 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all user_templates" ON public.user_templates;

-- 用户可以查看自己的模板和所有公共模板
CREATE POLICY "users_can_view_own_and_public_templates" ON public.user_templates
    FOR SELECT USING (user_id = auth.uid() OR visibility = 'public');

-- 只有所有者可以更新自己的模板
CREATE POLICY "users_can_update_own_templates" ON public.user_templates
    FOR UPDATE USING (user_id = auth.uid());

-- 只有所有者可以删除自己的模板
CREATE POLICY "users_can_delete_own_templates" ON public.user_templates
    FOR DELETE USING (user_id = auth.uid());

-- 认证用户可以插入模板
CREATE POLICY "users_can_insert_templates" ON public.user_templates
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================================
-- 2. knowledge_items 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all knowledge" ON public.knowledge_items;

-- 用户可以查看自己的知识库和所有公共知识库
CREATE POLICY "users_can_view_own_and_public_knowledge" ON public.knowledge_items
    FOR SELECT USING (user_id = auth.uid() OR visibility = 'public' OR user_id IS NULL);

-- 只有所有者可以更新自己的知识库
CREATE POLICY "users_can_update_own_knowledge" ON public.knowledge_items
    FOR UPDATE USING (user_id = auth.uid());

-- 只有所有者可以删除自己的知识库
CREATE POLICY "users_can_delete_own_knowledge" ON public.knowledge_items
    FOR DELETE USING (user_id = auth.uid());

-- 认证用户可以插入知识库
CREATE POLICY "users_can_insert_knowledge" ON public.knowledge_items
    FOR INSERT WITH CHECK (auth.uid() IS NOT NULL);

-- ============================================================
-- 3. knowledge_vectors 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow read vectors" ON public.knowledge_vectors;

-- 用户可以查看自己知识库的向量和公共知识库的向量
CREATE POLICY "users_can_view_own_and_public_vectors" ON public.knowledge_vectors
    FOR SELECT USING (
        knowledge_item_id IN (
            SELECT id FROM public.knowledge_items 
            WHERE user_id = auth.uid() OR visibility = 'public' OR user_id IS NULL
        )
    );

-- ============================================================
-- 4. template_favorites 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all template_favorites" ON public.template_favorites;

-- 用户只能查看自己的收藏
CREATE POLICY "users_can_view_own_favorites" ON public.template_favorites
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的收藏
CREATE POLICY "users_can_manage_own_favorites" ON public.template_favorites
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 5. rag_conversations 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all rag_conversations" ON public.rag_conversations;

-- 用户只能查看自己的对话
CREATE POLICY "users_can_view_own_conversations" ON public.rag_conversations
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的对话
CREATE POLICY "users_can_manage_own_conversations" ON public.rag_conversations
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 6. rag_messages 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all rag_messages" ON public.rag_messages;

-- 用户只能查看自己对话的消息
CREATE POLICY "users_can_view_own_messages" ON public.rag_messages
    FOR SELECT USING (
        conversation_id IN (
            SELECT id FROM public.rag_conversations WHERE user_id = auth.uid()
        )
    );

-- 用户只能管理自己对话的消息
CREATE POLICY "users_can_manage_own_messages" ON public.rag_messages
    FOR ALL USING (
        conversation_id IN (
            SELECT id FROM public.rag_conversations WHERE user_id = auth.uid()
        )
    );

-- ============================================================
-- 7. messages 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all messages" ON public.messages;

-- 用户只能查看自己的消息
CREATE POLICY "users_can_view_own_messages_table" ON public.messages
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的消息
CREATE POLICY "users_can_manage_own_messages_table" ON public.messages
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 8. coursewares 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all coursewares" ON public.coursewares;

-- 用户只能查看自己的课件
CREATE POLICY "users_can_view_own_coursewares" ON public.coursewares
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的课件
CREATE POLICY "users_can_manage_own_coursewares" ON public.coursewares
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 9. exports 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all exports" ON public.exports;

-- 用户只能查看自己的导出记录
CREATE POLICY "users_can_view_own_exports" ON public.exports
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的导出记录
CREATE POLICY "users_can_manage_own_exports" ON public.exports
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 10. search_history 表权限策略
-- ============================================================

DROP POLICY IF EXISTS "Allow all search_history" ON public.search_history;

-- 用户只能查看自己的搜索历史
CREATE POLICY "users_can_view_own_search_history" ON public.search_history
    FOR SELECT USING (user_id = auth.uid());

-- 用户只能管理自己的搜索历史
CREATE POLICY "users_can_manage_own_search_history" ON public.search_history
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- 验证策略
-- ============================================================

DO $$
DECLARE
    policy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO policy_count 
    FROM pg_policies 
    WHERE schemaname = 'public';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'RLS 策略修复完成!';
    RAISE NOTICE '策略总数: %', policy_count;
    RAISE NOTICE '========================================';
END $$;
