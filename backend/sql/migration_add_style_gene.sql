-- ============================================================
-- 模板样式基因字段扩展 - 数据库迁移脚本
-- 
-- 功能：为 user_templates 表添加样式基因相关字段
-- 运行方式：在 Supabase SQL Editor 中执行此脚本
-- ============================================================

-- 1. 添加样式基因主字段（JSONB 格式存储完整样式信息）
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS style_gene JSONB;

-- 2. 添加样式提取状态标志
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS style_extracted BOOLEAN DEFAULT FALSE;

-- 3. 添加样式提取时间戳
ALTER TABLE public.user_templates ADD COLUMN IF NOT EXISTS style_extracted_at TIMESTAMP WITH TIME ZONE;

-- 4. 创建索引：加速按样式状态查询
CREATE INDEX IF NOT EXISTS idx_user_templates_style_extracted 
    ON public.user_templates(style_extracted) 
    WHERE style_extracted = TRUE;

-- 5. 创建索引：加速按版式数量筛选
CREATE INDEX IF NOT EXISTS idx_user_templates_layout_count 
    ON public.user_templates USING GIN (style_gene);

-- 6. 验证字段是否创建成功
DO $$
DECLARE
    column_exists BOOLEAN;
BEGIN
    SELECT COUNT(*) > 0 INTO column_exists
    FROM information_schema.columns
    WHERE table_name = 'user_templates' 
      AND column_name = 'style_gene';
    
    IF column_exists THEN
        RAISE NOTICE '✓ 字段 style_gene 已成功添加';
    ELSE
        RAISE NOTICE '✗ 字段 style_gene 添加失败';
    END IF;
    
    SELECT COUNT(*) > 0 INTO column_exists
    FROM information_schema.columns
    WHERE table_name = 'user_templates' 
      AND column_name = 'style_extracted';
    
    IF column_exists THEN
        RAISE NOTICE '✓ 字段 style_extracted 已成功添加';
    ELSE
        RAISE NOTICE '✗ 字段 style_extracted 添加失败';
    END IF;
    
    SELECT COUNT(*) > 0 INTO column_exists
    FROM information_schema.columns
    WHERE table_name = 'user_templates' 
      AND column_name = 'style_extracted_at';
    
    IF column_exists THEN
        RAISE NOTICE '✓ 字段 style_extracted_at 已成功添加';
    ELSE
        RAISE NOTICE '✗ 字段 style_extracted_at 添加失败';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '迁移完成! 新增字段:';
    RAISE NOTICE '  - style_gene: JSONB (样式基因数据)';
    RAISE NOTICE '  - style_extracted: BOOLEAN (提取状态)';
    RAISE NOTICE '  - style_extracted_at: TIMESTAMP (提取时间)';
    RAISE NOTICE '========================================';
END $$;
