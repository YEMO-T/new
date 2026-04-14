# 智能模板库 v2.0 - 完整部署与使用指南

## 📋 目录

1. [功能概述](#功能概述)
2. [新架构设计](#新架构设计)
3. [文件清单](#文件清单)
4. [快速开始](#快速开始)
5. [API 使用说明](#api-使用说明)
6. [数据库配置](#数据库配置)
7. [前端集成](#前端集成)
8. [故障排查](#故障排查)

---

## 功能概述

### ✅ 核心能力

#### 1️⃣ **智能样式提取**
- 用户上传 PPTX 模板后，系统自动提取纯样式信息
- 提取内容：颜色方案、字体规则、版式结构、占位符信息
- **关键改进**：数据库只存储"风格基因"，不存储原始示例文字

#### 2️⃣ **样式化模板浏览**
- 用户浏览模板时看到的是"风格画像"
- 显示：主字体、主色调、版式数量、幻灯片比例
- 不展示原始 PPT 内容（保护隐私/版权）

#### 3️⃣ **直接生成最终 PPT**
- 使用 UltimateRenderer 一步到位
- 无预览步骤，直接输出最终可用的 PPTX
- 100% 继承模板视觉风格
- 零残留（无模板原始内容）

#### 4️⃣ **完整导出记录管理**
- 每次生成都自动保存记录
- 支持列表查看、详情、下载、删除
- 文件同时保存到 Storage 和本地
- 完整的追踪历史

### 🎯 解决的问题

| 旧方案 (v1) | 新方案 (v2) |
|------------|------------|
| ❌ 上传后存储原始文件 | ✅ 自动提取并存储样式基因 |
| ❌ 浏览时显示原PPT内容 | ✅ 只展示风格画像 |
| ❌ 可能有预览渲染步骤 | ✅ 直接生成最终版本 |
| ❌ 导出记录不完善 | ✅ 完整的导出管理系统 |

---

## 新架构设计

### 系统流程图

```
用户上传 PPTX
    ↓
[StyleExtractor] 提取样式基因
    ↓
┌─────────────────────────────┐
│  存储到数据库 (user_templates) │
│  - style_gene (JSON)         │
│  - color_scheme              │
│  - font_scheme               │
│  - layouts                   │
└─────────────────────────────┘
    ↓
用户浏览模板 → 返回样式画像摘要
    ↓
用户请求生成 PPT
    ↓
[UltimateRenderer] 加载样式 + 填充内容
    ↓
┌──────────────────────────────┐
│  输出: 最终版 PPTX            │
│  - 继承所有样式              │
│  - 只有用户的内容            │
│  - 可直接使用                │
└──────────────────────────────┘
    ↓
[ExportManager] 保存到:
  - Supabase Storage
  - 本地文件系统
  - 数据库记录 (ppt_exports)
```

### 数据模型

#### user_templates 表（新增字段）

```sql
-- 样式基因数据 (JSONB)
style_gene JSONB DEFAULT '{}'
-- 示例值:
{
  "template_id": "uuid",
  "template_name": "商务蓝",
  "color_scheme": {
    "accent1": "0070C0",      -- 主色调
    "accent2": "FF0000",
    ...
  },
  "font_scheme": {
    "major_latin": "Arial",
    "major_east_asian": "微软雅黑",
    ...
  },
  "layouts": [...],
  "total_layouts": 11,
  "summary": {
    "aspect_ratio": "16:9",
    ...
  }
}

-- 元数据字段
style_extracted BOOLEAN DEFAULT FALSE
style_extracted_at TIMESTAMPTZ
```

#### ppt_exports 表（新建）

```sql
CREATE TABLE ppt_exports (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    template_id UUID,           -- 使用的模板ID
    template_name VARCHAR(255), -- 模板名称
    title VARCHAR(255),         -- 导出的标题
    file_name VARCHAR(500),     -- 文件名
    file_size BIGINT,           -- 文件大小(bytes)
    format VARCHAR(20),         -- 格式 (pptx/pdf)
    storage_bucket VARCHAR(100),-- Storage桶名
    storage_path TEXT,          -- Storage路径
    local_path TEXT,            -- 本地路径
    download_url TEXT,          -- 下载URL
    slide_count INTEGER,        -- 幻灯片数
    status VARCHAR(50),         -- 状态 (completed/error)
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);
```

---

## 文件清单

### 🆕 新建文件

| 文件路径 | 说明 | 行数 |
|---------|------|------|
| `backend/utils/style_extractor.py` | PPT样式智能提取器 | ~450行 |
| `backend/api/ppt_templates_v2.py` | V2 API接口 | ~650行 |
| `backend/migrate_ppt_exports.py` | 数据库迁移脚本 | ~200行 |
| `backend/test_v2_system.py` | 端到端测试 | ~400行 |

### ✏️ 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `backend/main.py` | 注册 V2 路由 (+2行) |

### 🔗 依赖的现有模块

| 模块 | 用途 |
|-----|------|
| `utils/ultimate_renderer.py` | 终极渲染器（PPT生成） |
| `utils/ppt_template_style_cloner.py` | 样式克隆器（底层支持） |
| `service/storage_service.py` | Storage操作（上传/删除） |
| `repository/supabase_client.py` | 数据库客户端 |

---

## 快速开始

### Step 1: 运行数据库迁移

```bash
cd backend

# 执行迁移脚本
python migrate_ppt_exports.py
```

**如果表不存在**，脚本会提示你在 Supabase Dashboard 中执行 SQL：

```sql
-- 在 Supabase SQL Editor 中执行:

CREATE TABLE IF NOT EXISTS public.ppt_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    template_id UUID,
    title VARCHAR(255) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_size BIGINT DEFAULT 0,
    format VARCHAR(20) DEFAULT 'pptx',
    storage_bucket VARCHAR(100),
    storage_path TEXT,
    local_path TEXT,
    download_url TEXT,
    slide_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'completed',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ppt_exports_user_id ON public.ppt_exports(user_id);
CREATE INDEX idx_ppt_exports_template_id ON public.ppt_exports(template_id);

ALTER TABLE public.ppt_exports ENABLE ROW LEVEL SECURITY;
```

### Step 2: 更新 user_templates 表（可选）

如果需要添加样式字段：

```sql
-- 在 Supabase SQL Editor 中执行:

ALTER TABLE public.user_templates
ADD COLUMN IF NOT EXISTS style_gene JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS style_extracted BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS style_extracted_at TIMESTAMPTZ;
```

### Step 3: 重启后端服务

```bash
cd backend

# 停止现有服务 (Ctrl+C)

# 启动新服务
python -m uvicorn main:app --reload --port 8000
```

**预期日志**：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
[STARTUP] 应用启动完成
[v2/Router] 智能模板库路由已注册（如果有此日志）
```

### Step 4: 验证 API 可用

访问以下端点确认服务正常：

```bash
# 健康检查
curl http://localhost:8000/api/health

# 预期响应: {"status":"ok"}
```

---

## API 使用说明

### 所有端点一览

```
POST   /api/ppt-templates/v2/upload              上传模板+提取样式
GET    /api/ppt-templates/v2                      获取模板列表(含样式)
GET    /api/ppt-templates/v2/{id}/style           获取完整样式数据
POST   /api/ppt-templates/v2/{id}/generate        生成最终PPT
GET    /api/ppt-templates/v2/exports               获取导出记录列表
GET    /api/ppt-templates/v2/exports/{id}          获取导出详情
GET    /api/ppt-templates/v2/exports/{id}/download 下载导出的PPT
DELETE /api/ppt-templates/v2/exports/{id}          删除导出记录
DELETE /api/ppt-templates/v2/{id}                 删除模板(级联清理)
```

### 1️⃣ 上传模板（自动提取样式）

**端点**: `POST /api/ppt-templates/v2/upload`

**请求**:
```http
Content-Type: multipart/form-data

file: <PPTX文件>
title: 商务蓝模板 (可选)
visibility: private 或 public (默认 private)
Authorization: Bearer <token>
```

**成功响应 (201)**:
```json
{
  "success": true,
  "message": "模板上传成功，样式已自动提取",
  "template_id": "uuid-here",
  "style_summary": {
    "total_layouts": 11,
    "main_font": "Arial",
    "primary_color": "0070C0",
    "aspect_ratio": "16:9"
  },
  "title": "商务蓝模板",
  "created_at": "2026-04-13T..."
}
```

**特点**:
- ✅ 自动调用 StyleExtractor 提取样式
- ✅ 样式存入 `style_gene` 字段（JSON格式）
- ✅ 原始文件上传到 Storage
- ✅ 返回轻量级样式摘要

### 2️⃣ 获取模板列表（含样式画像）

**端点**: `GET /api/ppt-templates/v2`

**参数**:
- `template_type`: `personal` (个人) 或 `public` (公共)
- `page`: 页码 (默认 1)
- `page_size`: 每页数量 (默认 20)

**响应**:
```json
{
  "success": true,
  "total": 15,
  "page": 1,
  "page_size": 20,
  "templates": [
    {
      "id": "uuid",
      "title": "商务蓝模板",
      "created_at": "...",
      "usage_count": 5,

      "style_preview": {           ← 样式画像！
        "total_layouts": 11,
        "main_font": "Arial",
        "primary_color": "0070C0",
        "aspect_ratio": "16:9",
        "has_style": true
      },

      "thumbnail_url": "..."       ← 缩略图(如果有)
    }
  ]
}
```

**与 v1 的区别**:
- ❌ v1: 返回原始文件信息
- ✅ v2: 返回**风格特征**（字体/颜色/版式数）

### 3️⃣ 获取完整样式数据

**端点**: `GET /api/ppt-templates/v2/{template_id}/style`

**响应**:
```json
{
  "success": true,
  "template_id": "uuid",
  "style_data": {
    "color_scheme": {
      "accent1": "0070C0",
      "accent2": "FF0000",
      ...
    },
    "font_scheme": {
      "major_latin": "Arial",
      "minor_latin": "Times New Roman",
      "major_east_asian": "微软雅黑",
      ...
    },
    "layouts": [
      {
        "index": 0,
        "name": "Title Slide",
        "type": "title_content",
        "has_title": true,
        "has_body": false,
        "placeholders": [...]
      },
      ...
    ],
    "summary": {
      "aspect_ratio": "16:9",
      "slide_width_inches": 13.333,
      "slide_height_inches": 7.5,
      ...
    }
  }
}
```

**用途**:
- 编辑器中加载样式配置
- 高级用户查看详细信息
- 调试和分析

### 4️⃣ 生成最终 PPT（核心功能！）

**端点**: `POST /api/ppt-templates/v2/{template_id}/generate`

**请求体**:
```json
{
  "title": "我的演示文稿",
  "auto_export": true,
  "slides": [
    {
      "title": "封面标题",
      "subtitle": "副标题文字",
      "content": [],
      "page_type": "cover"
    },
    {
      "title": "核心内容",
      "subtitle": "",
      "content": [
        "要点一：重要信息",
        "要点二：详细说明",
        "要点三：总结归纳"
      ],
      "page_type": "content"
    },
    {
      "title": "目录",
      "content": ["第一章", "第二章", "第三章"],
      "page_type": "toc"
    },
    {
      "title": "感谢观看",
      "content": [],
      "page_type": "ending"
    }
  ]
}
```

**成功响应 (200)**:
```json
{
  "success": true,
  "export_id": "uuid-export-id",
  "download_url": "https://...storage.../exports/user/file.pptx",
  "file_name": "我的演示文稿_20260413_120000.pptx",
  "slide_count": 4,
  "generated_at": "2026-04-13T12:00:00"
}
```

**特点**:
- ✅ **直接使用 UltimateRenderer**（终极渲染器）
- ✅ **一步到位**：无需预览步骤
- ✅ **零残留**：只有你的内容
- ✅ **完整继承**：字体/颜色/版式全部保留
- ✅ **自动保存**：创建导出记录（如果 auto_export=true）

### 5️⃣ 导出记录管理

#### 列表查询

**端点**: `GET /api/ppt-templates/v2/exports`

**参数**:
- `page`, `page_size`

**响应**:
```json
{
  "success": true,
  "total": 10,
  "exports": [
    {
      "id": "uuid",
      "template_id": "uuid-template",
      "template_name": "商务蓝",
      "title": "季度报告",
      "file_name": "季度报告_20260413.pptx",
      "file_size": 1234567,
      "format": "pptx",
      "slide_count": 15,
      "status": "completed",
      "created_at": "2026-04-13T...",
      "download_url": "https://..."
    }
  ]
}
```

#### 下载文件

**端点**: `GET /api/ppt-templates/v2/exports/{export_id}/download`

**行为**:
- 如果有公开 URL → 307 重定向
- 如果有本地文件 → 直接返回文件流
- 如果有 Storage 路径 → 生成签名 URL 并重定向

**响应**: 文件流 (`application/vnd.openxmlformats-officedocument.presentationml.presentation`)

#### 删除记录

**端点**: `DELETE /api/ppt-templates/v2/exports/{export_id}`

**执行的操作**:
1. 删除本地文件（如果存在）
2. 删除 Storage 文件（如果存在）
3. 删除数据库记录

**响应**:
```json
{
  "success": true,
  "message": "导出记录已删除"
}
```

### 6️⃣ 删除模板（级联清理）

**端点**: `DELETE /api/ppt-templates/v2/{template_id}`

**执行的操作**:
1. ✅ 删除本地模板文件
2. ✅ 删除 Storage 中的模板文件
3. ✅ 清理关联的所有导出记录和文件
4. ✅ 删除数据库记录（包括 style_gene）

**响应**:
```json
{
  "success": true,
  "message": "模板已完全删除（5/5 项）",
  "operations": [
    "本地文件: ✓",
    "Storage文件: ✓",
    "导出记录: ✓ (3个)",
    "数据库记录: ✓ (含样式)"
  ]
}
```

---

## 数据库配置

### 必要的表

#### 1. ppt_exports 表（必须新建）

运行 `migrate_ppt_exports.py` 或手动在 Supabase SQL Editor 执行。

#### 2. user_templates 表（需要更新）

添加以下字段（如果没有的话）：

```sql
ALTER TABLE user_templates ADD COLUMN style_gene JSONB DEFAULT '{}';
ALTER TABLE user_templates ADD COLUMN style_extracted BOOLEAN DEFAULT FALSE;
ALTER TABLE user_templates ADD COLUMN style_extracted_at TIMESTAMPTZ;
```

### RLS (行级安全) 配置

确保 `ppt_exports` 表启用了 RLS：

```sql
-- 启用 RLS
ALTER TABLE ppt_exports ENABLE ROW LEVEL SECURITY;

-- 创建策略
CREATE POLICY "Users can view own exports"
  ON ppt_exports FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own exports"
  ON ppt_exports FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own exports"
  ON ppt_exports FOR DELETE
  USING (auth.uid() = user_id);
```

---

## 前端集成

### 必须更新的 API 调用

如果你使用前端框架（React/Vue/Angular），需要更新以下 API 调用：

#### 1. 模板上传

```javascript
// 旧 API (v1)
const response = await fetch('/api/ppt-templates/upload', {...})

// 新 API (v2) ✓
const response = await fetch('/api/ppt-templates/v2/upload', {
  method: 'POST',
  body: formData,
  headers: {'Authorization': `Bearer ${token}`}
})

// 响应中包含 style_summary
const { template_id, style_summary } = await response.json()
console.log(`主字体: ${style_summary.main_font}`)
```

#### 2. 模板列表

```javascript
// 旧 API (v1)
const response = await fetch(`/api/ppt-templates?type=personal`)

// 新 API (v2) ✓
const response = await fetch('/api/ppt-templates/v2?template_type=personal')

// 响应中每个模板都有 style_preview
const { templates } = await response.json()
templates.forEach(t => {
  console.log(`${t.title}: 主色调=${t.style_preview.primary_color}`)
})
```

#### 3. PPT 生成

```javascript
// 旧 API (v1)
const response = await fetch(`/api/ppt-templates/${id}/generate`, {...})

// 新 API (v2) ✓
const response = await fetch(`/api/ppt-templates/v2/${id}/generate`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    title: '我的演示',
    slides: [...],
    auto_export: true  // 自动保存到导出记录
  })
})

// 直接获取下载链接
const { export_id, download_url } = await response.json()
window.open(download_url)  // 下载或预览
```

#### 4. 导出记录页面

```javascript
// 新增：获取导出列表
const response = await fetch('/api/ppt-templates/v2/exports', {
  headers: {'Authorization': `Bearer ${token}`}
})

const { exports } = await response.json()

// 渲染导出列表
exports.forEach(exp => {
  console.log(`${exp.title} (${exp.file_size / 1024} KB)`)
})
```

### UI 改进建议

1. **模板卡片**：
   - 显示颜色圆点（主色调）
   - 显示字体名称
   - 显示版式数量
   - 显示比例标签（16:9 / 4:3）

2. **导出列表页**：
   - 文件大小、格式图标
   - 生成时间
   - 下载按钮
   - 删除按钮

3. **生成成功弹窗**：
   - 显示 export_id
   - 直接提供下载按钮
   - "查看导出记录"链接

---

## 故障排查

### 问题1: 样式提取失败

**症状**:
```json
{
  "style_summary": {
    "total_layouts": 0,
    "error": "样式提取失败: ..."
  }
}
```

**原因**:
- PPTX 文件损坏或不标准
- python-pptx 版本兼容性问题

**解决方案**:
1. 检查文件是否可以用 PowerPoint 打开
2. 更新 python-pptx: `pip install --upgrade python-pptx`
3. 查看后端日志获取详细错误

### 问题2: 导出记录表不存在

**症状**:
```
500 Internal Server Error: relation "ppt_exports" does not exist
```

**解决方案**:
1. 运行迁移脚本: `python migrate_ppt_exports.py`
2. 在 Supabase Dashboard 手动创建表
3. 参考[数据库配置](#数据库配置)章节

### 问题3: UltimateRenderer 失败

**症状**:
```json
{
  "detail": "生成失败: 所有渲染器均失败"
}
```

**原因**:
- 模板文件损坏
- 内存不足（大文件）
- 权限问题

**解决方案**:
1. 查看后端日志中的详细堆栈
2. 尝试使用较小的模板
3. 检查临时目录权限

### 问题4: 下载链接无效

**症状**:
点击下载后 404 或签名过期

**解决方案**:
1. 检查 Storage 文件是否还存在
2. 重新生成签名 URL（有效期通常1小时）
3. 使用本地下载作为备选

### 问题5: 编码错误（中文乱码）

**症状**:
```
SyntaxError: Non-UTF-8 code starting with '\xef' on line X
```

**原因**:
- PowerShell/CMD 的文本命令破坏了 UTF-8 编码

**解决方案**:
1. **永远不要**用 PowerShell 的 `-replace` 修改 Python 文件
2. 使用 IDE 的搜索替换功能
3. 从 Git 恢复: `git checkout HEAD -- backend/api/ppt_templates_v2.py`

---

## 性能优化建议

### 1. 样式提取缓存

对于频繁使用的模板，可以缓存提取结果：

```python
# 在 Redis/Memory 中缓存
cache_key = f"style:{template_id}"
cached = redis.get(cache_key)
if cached:
    return json.loads(cached)

# 否则提取并缓存
style = extractor.extract(template_path)
redis.setex(cache_key, 3600, json.dumps(style.to_dict()))
```

### 2. 异步处理大文件

对于 >10MB 的模板，可以使用后台任务队列：

```python
from celery import shared_task

@shared_task
def async_extract_style(template_id):
    # 后台异步提取
    extractor = PPTStyleExtractor()
    profile = extractor.extract(get_template_path(template_id))
    save_to_db(profile)
```

### 3. 分页优化

导出记录列表使用游标分页（而非偏移分页）：

```sql
-- 使用 ID 游标（性能更好）
SELECT * FROM ppt_exports
WHERE user_id = $1 AND id > $cursor
ORDER BY id ASC
LIMIT 20;
```

---

## 监控和日志

### 关键指标监控

1. **样式提取成功率**:
   ```
   [StyleExtractor] 提取成功/失败次数
   ```

2. **PPT 生成耗时**:
   ```
   [v2/Generate] 耗时: 1.23秒 (8页)
   ```

3. **Storage 使用量**:
   ```sql
   SELECT SUM(file_size) FROM ppt_exports WHERE created_at > NOW() - INTERVAL '7 days';
   ```

4. **导出频率**:
   ```sql
   SELECT DATE(created_at), COUNT(*)
   FROM ppt_exports
   GROUP BY DATE(created_at)
   ORDER BY DATE(created_at) DESC
   LIMIT 30;
   ```

### 日志级别设置

```python
# 开发环境
logging.getLogger('StyleExtractor').setLevel(logging.DEBUG)

# 生产环境
logging.getLogger('StyleExtractor').setLevel(logging.INFO)
logging.getLogger('UltimateRenderer').setLevel(logging.WARNING)
```

---

## 更新历史

### v2.0.0 (2026-04-13)

**新功能**:
- ✅ PPT样式智能提取引擎 (StyleExtractor)
- ✅ 自动样式提取（上传时触发）
- ✅ 样式画像浏览（模板列表API）
- ✅ 直接生成最终PPT（UltimateRenderer集成）
- ✅ 完整导出记录管理系统
- ✅ 级联删除（模板+导出+文件）

**技术改进**:
- 样式与内容分离架构
- 三级降级机制保持不变
- 完整的类型注解和文档
- 全面的错误处理和日志

**新增文件**:
- `utils/style_extractor.py` (~450行)
- `api/ppt_templates_v2.py` (~650行)
- `migrate_ppt_exports.py` (~200行)
- `test_v2_system.py` (~400行)

**修改文件**:
- `main.py` (+2行路由注册)

---

## 相关资源

- **终极渲染器文档**: `DEPLOYMENT_GUIDE.md`
- **样式克隆器源码**: `utils/ppt_template_style_cloner.py`
- **Supabase 文档**: https://supabase.com/docs
- **python-pptx 文档**: https://python-pptx.readthedocs.io/

---

## 技术支持

如遇到问题：

1. 查看[故障排查](#故障排查)章节
2. 检查后端日志（终端输出）
3. 运行测试脚本: `python test_v2_system.py`
4. 查看生成的报告: `data/v2_deployment_report.json`

---

**🎉 祝你使用愉快！**

**最后更新**: 2026-04-13 12:30
