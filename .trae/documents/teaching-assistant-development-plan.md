# 教学备课智能体（冲奖版）完整开发方案

## 一、项目现状分析

### 已有功能
- ✅ 用户认证系统（JWT）
- ✅ 基础知识库管理（上传、编辑、删除）
- ✅ PPT模板库（上传、预览、选择）
- ✅ AI对话生成课件（Moonshot/Kimi大模型）
- ✅ PPT/教案导出功能
- ✅ RAG向量检索基础架构（Supabase + pgvector）
- ✅ 前后端分离架构（React + FastAPI）

### 待开发功能（冲奖核心）
- ❌ 云端权威教学资源库（官方教材、课标、题库）
- ❌ 课标自动对齐检测
- ❌ 知识点溯源标注
- ❌ 智能模板匹配
- ❌ 一页式备课大纲同步生成
- ❌ 高频考点/易错点智能标记
- ❌ 云端资源权限管理（公共/私人）
- ❌ 分层习题生成（基础/拔高）

---

## 二、分阶段开发计划

### 阶段1：云端权威知识库搭建（核心基础）

#### 1.1 数据库表结构优化
- [ ] 扩展 `teaching_resources` 表，添加资源分类字段
- [ ] 创建 `curriculum_standards` 课标库表
- [ ] 创建 `exam_questions` 题库表（含难度分级）
- [ ] 创建 `resource_categories` 资源分类表

#### 1.2 Supabase Storage 配置
- [ ] 创建 `teaching-resources` 存储桶
- [ ] 配置目录结构：`公共资源/年级/学科/资源类型`
- [ ] 配置目录结构：`私人资源/用户ID/年级/学科`
- [ ] 设置存储桶权限策略

#### 1.3 云端资源管理API
- [ ] `GET /api/resources` - 按条件搜索云端资源
- [ ] `POST /api/resources/upload` - 上传资源到云端
- [ ] `GET /api/resources/{id}/download` - 下载资源
- [ ] `DELETE /api/resources/{id}` - 删除私人资源
- [ ] `GET /api/resources/categories` - 获取资源分类

#### 1.4 向量化处理服务
- [ ] 集成 sentence-transformers 模型
- [ ] 实现文档自动切块（512字符/块）
- [ ] 实现向量化存储到 pgvector
- [ ] 实现相似度检索接口

---

### 阶段2：课标对齐与溯源功能

#### 2.1 课标数据库建设
- [ ] 导入义务教育课程标准数据
- [ ] 按年级、学科、知识点分类存储
- [ ] 课标内容向量化处理

#### 2.2 课标对齐检测API
- [ ] `POST /api/curriculum/check` - 课标对齐检测
- [ ] `GET /api/curriculum/{grade}/{subject}` - 获取课标列表
- [ ] 返回合规性报告（匹配度、缺失项、建议）

#### 2.3 知识点溯源标注
- [ ] 在PPT生成时自动标注内容来源
- [ ] 页脚显示：来源资源名称 + 页码
- [ ] 支持点击溯源跳转到原始资源

---

### 阶段3：智能内容生成增强

#### 3.1 分层习题生成
- [ ] 扩展AI Prompt模板，生成分层习题
- [ ] 基础题：知识点直接应用
- [ ] 拔高题：知识点综合运用
- [ ] 习题自动嵌入PPT末尾

#### 3.2 一页式备课大纲
- [ ] 设计备课大纲模板
- [ ] 包含：教学目标、重难点、时间分配、板书设计
- [ ] 与PPT同步生成，支持独立导出

#### 3.3 高频考点/易错点标记
- [ ] 从题库提取考点频率数据
- [ ] PPT重点内容自动高亮标注
- [ ] 易错点提示气泡

#### 3.4 智能模板匹配
- [ ] 根据学科自动推荐模板风格
- [ ] 理科：简洁、数据可视化
- [ ] 文科：文艺、图文并茂
- [ ] 公开课：正式、结构清晰

---

### 阶段4：前端界面优化

#### 4.1 云端资源库页面
- [ ] 资源搜索界面（关键词、年级、学科筛选）
- [ ] 资源列表展示（缩略图、名称、类型、大小）
- [ ] 资源预览功能
- [ ] 一键下载功能

#### 4.2 私人知识库管理
- [ ] 上传进度显示
- [ ] 文件分类管理
- [ ] 公共/私人资源分区展示

#### 4.3 课标对齐报告展示
- [ ] 可视化合规性报告
- [ ] 缺失项高亮提示
- [ ] 一键补充建议

#### 4.4 交互体验优化
- [ ] 生成进度条
- [ ] 错误提示优化
- [ ] 加载状态动画

---

### 阶段5：系统联调与优化

#### 5.1 全流程测试
- [ ] 云端资源上传/搜索/下载
- [ ] RAG检索准确性测试
- [ ] AI生成内容质量测试
- [ ] PPT渲染完整性测试

#### 5.2 性能优化
- [ ] 向量检索响应时间优化
- [ ] 大文件上传分片处理
- [ ] 前端懒加载优化

#### 5.3 文档整理
- [ ] API接口文档
- [ ] 部署教程
- [ ] 用户使用手册

---

## 三、技术架构

### 后端技术栈
- **框架**: FastAPI
- **数据库**: Supabase (PostgreSQL + pgvector)
- **存储**: Supabase Storage
- **大模型**: Moonshot/Kimi API
- **向量化**: sentence-transformers (all-MiniLM-L6-v2)

### 前端技术栈
- **框架**: React 19 + TypeScript
- **构建**: Vite
- **样式**: Tailwind CSS
- **动画**: Motion
- **Markdown**: react-markdown + remark-gfm

### 数据库表设计

```sql
-- 教学资源表（扩展）
CREATE TABLE teaching_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_name TEXT NOT NULL,
    grade_level TEXT NOT NULL,
    subject TEXT NOT NULL,
    resource_type TEXT NOT NULL,  -- 教材/课标/课件/题库/PPT模板
    storage_path TEXT,
    download_url TEXT,
    is_public BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    preview_url TEXT,
    description TEXT,
    file_size INTEGER,
    download_count INTEGER DEFAULT 0
);

-- 课标表
CREATE TABLE curriculum_standards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grade TEXT NOT NULL,
    subject TEXT NOT NULL,
    standard_code TEXT NOT NULL,
    standard_content TEXT NOT NULL,
    key_points JSONB,
    vector_embedding vector(384)
);

-- 题库表
CREATE TABLE exam_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    grade_level TEXT NOT NULL,
    subject TEXT NOT NULL,
    knowledge_point TEXT,
    difficulty TEXT NOT NULL,  -- 基础/中等/拔高
    question_content TEXT NOT NULL,
    answer TEXT,
    source TEXT,
    frequency INTEGER DEFAULT 0,  -- 考察频率
    vector_embedding vector(384)
);
```

---

## 四、开发优先级

### P0（必须完成）
1. 云端资源库基础功能
2. 课标对齐检测
3. 知识点溯源标注
4. 分层习题生成

### P1（重要功能）
1. 一页式备课大纲
2. 高频考点标记
3. 智能模板匹配

### P2（优化功能）
1. 资源预览优化
2. 性能优化
3. 交互体验优化

---

## 五、预期成果

### 功能亮点
1. **内容权威零幻觉**: 基于云端官方资源，RAG精准检索
2. **课标自动对齐**: 生成内容自动检测合规性
3. **知识点可溯源**: 每页PPT标注内容来源
4. **分层习题一键生成**: 基础题+拔高题自动嵌入
5. **云端资源库**: 官方教材、课标、题库一键下载

### 冲奖优势
1. 落地性强：教师可直接用于教学
2. 合规安全：内容贴合课标，无教学风险
3. 创新性高：集资源库+智能备课+课标检测于一体
4. 技术先进：RAG+向量检索+大模型融合

---

## 六、开发时间规划

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 阶段1 | 云端知识库搭建 | 3天 |
| 阶段2 | 课标对齐与溯源 | 2天 |
| 阶段3 | 智能内容生成增强 | 3天 |
| 阶段4 | 前端界面优化 | 2天 |
| 阶段5 | 系统联调与优化 | 2天 |
| **总计** | | **12天** |
