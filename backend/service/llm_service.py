import re
import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional
from collections import defaultdict
import time

from openai import AsyncOpenAI, APITimeoutError, APIConnectionError

from core.config import settings
from repository.supabase_client import get_knowledge_items
from service.template_service import TemplateService
from service.smart_rag_service import get_rag_context_for_chat, smart_rag_search
from schema.chat_schema import PPTGenerateRequest, PPTSlide
from utils.json_parser import clean_and_extract_json

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 60.0
LLM_DECOMPOSE_TIMEOUT = 45.0
LLM_SLIDE_TIMEOUT = 30.0

# 简单的速率限制器
class RateLimiter:
    def __init__(self, max_calls: int, time_frame: int):
        """
        初始化速率限制器
        max_calls: 时间框架内最大调用次数
        time_frame: 时间框架（秒）
        """
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = defaultdict(list)  # {user_id: [timestamp1, timestamp2, ...]}
    
    async def check_limit(self, user_id: str) -> bool:
        """
        检查用户是否超过速率限制
        返回 True 表示允许调用，False 表示超过限制
        """
        current_time = time.time()
        
        # 清理过期的调用记录
        self.calls[user_id] = [t for t in self.calls[user_id] if current_time - t < self.time_frame]
        
        # 检查是否超过限制
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        
        # 记录本次调用
        self.calls[user_id].append(current_time)
        return True

# 初始化速率限制器（每60秒最多30次调用）
rate_limiter = RateLimiter(max_calls=30, time_frame=60)

llm_client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_API_BASE,
    timeout=LLM_TIMEOUT
)

# NOTE: 引导式多轮对话系统提示
SYSTEM_INSTRUCTION_CHAT = """你是「豆沙包AI备课助手」—— 一位拥有20年一线教学经验的资深教师兼课程设计专家。

## 核心身份与能力矩阵

你不仅是一位知识传授者，更是一位**教学设计师**。你的能力覆盖：

| 维度 | 能力描述 |
|------|----------|
| 📚 学科专精 | 精通中小学全学科教材体系、课程标准、考试要求 |
| 🎯 教学设计 | 擅长布鲁姆目标分类、逆向教学设计、UBD理解导向设计 |
| 💡 认知科学 | 深谙认知负荷理论、双重编码理论、建构主义学习理论 |
| 📊 差异化教学 | 能根据学情调整内容难度、提供多层级学习路径 |
| 🔧 技术整合 | 善于将教学内容转化为PPT、互动活动、数字化资源 |

## 铁律级工作准则（最高优先级）

### 🔒 规则1：RAG知识库为唯一权威来源
```
✅ 允许：原文引用 → 教学化解读 → 通俗化转述 → 结构化重组
❌ 禁止：凭空编造 / 脱离教材拓展 / 主观臆断知识点
⚠️ 边界：若知识库无相关素材 → 明确告知"该主题暂无知识库资料"
```

### 🧠 规则2：遵循认知科学原理
- **认知负荷控制**：每页PPT聚焦1-2个核心概念，避免信息过载
- **双重编码**：文字+视觉化描述并重，便于大脑双通道加工
- **组块原理**：内容按"7±2"原则分组，每组不超过5-7个要点
- **前置激活**：每节新知前先建立与旧知的联系桥梁

### 📐 规则3：严格的教学结构规范

#### 标准PPT课件架构（智能自适应）
```
第1页：封面 —— 课程标题+学段学科+情感化副标题
第2页：学习目标 —— 三维目标（知识/能力/素养）用行为动词表述
第3页：情境导入 —— 真实情境/认知冲突/问题链激发
第4-N页：核心新知 —— 按"是什么→为什么→怎么做→怎么用"递进
倒数第2页：课堂小结 —— 知识图谱/思维导图式梳理
最后1页：结束页 —— 作业分层布置+下节预告+激励语
```

#### 单页内容质量标准
- **最低门槛**：每页≥5条有实质内容的要点
- **优质标准**：每条要点包含"核心观点+解释说明+举例/应用"
- **禁止行为**：一句话概括、空泛套话、"详见课本"式敷衍

### 🎨 规则4：语言风格适配矩阵

根据受众自动切换语言风格：

| 受众类型 | 语言特征 | 示例 |
|----------|----------|------|
| 小学低段(1-3) | 形象生动、多用比喻、短句为主 | "就像搭积木一样..." |
| 小学高段(4-6) | 适度抽象、引导思考、鼓励探究 | "你们觉得为什么会这样呢？" |
| 初中阶段 | 逻辑清晰、联系实际、培养方法 | "这个规律在生活中有哪些应用？" |
| 高中阶段 | 学术严谨、深度分析、批判思维 | "从多个角度审视这一结论的局限性..." |

### ⚙️ 规则5：智能化对话引导策略

#### 信息收集三要素（必须收集完整）
1. **学科领域** → 决定知识体系和专业术语
2. **学段年级** → 决定认知水平和表达方式  
3. **具体主题** → 决定内容范围和深度

#### 智能追问决策树
```
用户输入
    ↓
能否推断出学科？ ──否──→ "请问这是哪个学科的课件？"（优先问）
    │
   是
    ↓
能否推断出年级？ ──否──→ "针对哪个年级/学段设计？"（其次问）
    │
   是
    ↓
主题是否明确？ ──否──→ "您想讲哪一课或哪个知识点？"（最后问）
    │
   是
    ↓
✅ 三要素齐全 → 输出专业回复 + 末尾添加 [READY_TO_GENERATE]
```

#### 追问的艺术
- ✅ **一次只问一个关键问题**（降低用户认知负荷）
- ✅ **基于已有信息做合理推测**（"我理解您想准备一节关于XX的课，对吗？"）
- ✅ **提供选项引导**（"是侧重概念讲解还是习题训练？"）
- ❌ **避免连续轰炸式提问**
- ❌ **避免使用教育术语质问普通用户**

### 📊 规则6：内容生成的质量检核清单

每次生成内容前，内部自检：
- [ ] 是否严格来自RAG知识库？
- [ ] 是否符合目标学段的认知水平？
- [ ] 是否遵循"是什么→为什么→怎么做"的认知顺序？
- [ ] 每页是否有≥5条实质内容？
- [ ] 语言风格是否匹配目标学生？
- [ ] 是否标注了重点(⭐)、难点(⚠️)、易错点(💡)？
- [ ] 是否提供了具体例子或应用场景？

## 输出格式规范

### 对话模式
- 使用Markdown增强可读性（列表、加粗、分级标题）
- 关键术语首次出现时可适当解释
- 复杂概念可用类比或生活实例辅助说明

### 内容生成模式
当触发 `[READY_TO_GENERATE]` 后，后续输出需严格JSON格式：
- 纯JSON输出，无Markdown包裹
- 文本内用单引号替代双引号
- content数组每个元素必须是完整的讲解要点

## 异常处理策略

| 场景 | 处理方式 |
|------|----------|
| 用户需求模糊 | 先共情确认，再聚焦追问 |
| 知识库无素材 | 诚实告知，建议更换主题或上传资料 |
| 跨学科内容 | 明确主次，主学科深入+关联学科简述 |
| 时间紧迫需求 | 建议精简版方案，保证核心完整性 |
| 用户不满意 | 主动询问具体哪部分需要调整，针对性修改 |"""


def _extract_json(text: str) -> Any:
    """
    鲁棒性 JSON 提取包装器
    """
    result = clean_and_extract_json(text)
    if result:
        return result
    
    logger.error(f"JSON 最终提取失败 | 内容前 100 字: {text[:100]}")
    return _generate_default_courseware()

def _generate_default_courseware() -> Dict[str, Any]:
    """
    生成默认课件数据，作为 JSON 解析失败时的备选方案
    """
    return {
        "slides": [
            {
                "title": "课程规划中",
                "content": "正在生成课程内容，请稍候...",
                "type": "cover",
                "imagePrompt": "教学设计"
            }
        ],
        "lessonPlan": {
            "title": "课程标题",
            "objectives": ["课程正在构思中"],
            "process": [
                {
                    "stage": "规划阶段",
                    "content": "大模型正在为您设计详细的教学内容",
                    "duration": "进行中"
                }
            ],
            "homework": "将在生成完成后显示"
        },
        "interaction": {
            "type": "quiz",
            "title": "互动环节",
            "description": "正在规划互动教学方案"
        },
        "_error": "JSON 解析失败，已生成默认课件。请重试或简化您的描述。"
    }

def _generate_default_outline(page_count: int, topic: str) -> List[dict]:
    """
    生成默认教学大纲 — 确保页数稳定
    
    当LLM返回无效结果时，使用此默认大纲兜底，
    保证始终返回固定数量的任务。
    """
    default_pages = [
        {"page": 1, "topic": f"封面：{topic}", "layout_suggestion": "cover", "description": f"课程标题、学段学科信息、本节课核心主题概述", "content_type": "text"},
        {"page": 2, "topic": "学习目标", "layout_suggestion": "content", "description": "知识目标、能力目标、情感态度价值观目标", "content_type": "text"},
        {"page": 3, "topic": "课堂导入", "layout_suggestion": "content", "description": "情境引入或问题抛出，激发学生学习兴趣", "content_type": "text"},
        {"page": 4, "topic": "知识点讲解（一）", "layout_suggestion": "content", "description": "核心概念定义与内涵阐释", "content_type": "text"},
        {"page": 5, "topic": "知识点讲解（二）", "layout_suggestion": "content", "description": "原理推导或方法步骤详解", "content_type": "text"},
        {"page": 6, "topic": "重点与难点", "layout_suggestion": "content", "description": "⭐重点内容标注、⚠️难点分析、💡易错提醒", "content_type": "text"},
        {"page": 7, "topic": "典型例题", "layout_suggestion": "content", "description": "经典例题呈现、解题思路、完整步骤、方法总结", "content_type": "text"},
        {"page": 8, "topic": "课堂练习", "layout_suggestion": "content", "description": "基础巩固题、能力提升题", "content_type": "text"},
        {"page": 9, "topic": "课堂小结", "layout_suggestion": "content", "description": "本节课知识点回顾与梳理", "content_type": "text"},
        {"page": 10, "topic": "结束页", "layout_suggestion": "blank", "description": "感谢语或作业布置", "content_type": "text"},
    ]

    outline = []
    for i in range(page_count):
        if i < len(default_pages):
            task = dict(default_pages[i])
            task["page"] = i + 1
            outline.append(task)
        else:
            outline.append({
                "page": i + 1,
                "topic": f"内容页第{i+1}页",
                "layout_suggestion": "content",
                "description": f"{topic}相关教学内容第{i+1}部分",
                "content_type": "text"
            })

    logger.info(f"[默认大纲] 生成了{len(outline)}页默认大纲")
    return outline

def _validate_and_fix_task_count(tasks: List[dict], expected_count: int, topic: str) -> List[dict]:
    """
    校验并修复任务数量 — 确保输出稳定
    
    处理三种情况：
      1. 任务数 < 期望值 → 用默认大纲补全
      2. 任务数 > 期望值 → 裁剪到期望值
      3. 任务数 = 期望值 → 直接返回
    """
    if not isinstance(tasks, list):
        return _generate_default_outline(expected_count, topic)

    actual = len(tasks)

    for task in tasks:
        if not isinstance(task, dict):
            continue
        task.setdefault("page", tasks.index(task) + 1)
        task.setdefault("topic", f"第{tasks.index(task)+1}页")
        task.setdefault("layout_suggestion", "content")
        task.setdefault("description", f"{topic}教学内容")
        task.setdefault("content_type", "text")

    if actual == expected_count:
        logger.info(f"[页数校验] ✅ 刚好{actual}页，符合预期")
        return tasks

    if actual < expected_count:
        missing = expected_count - actual
        default = _generate_default_outline(expected_count, topic)
        extra = default[actual:]
        tasks.extend(extra)
        logger.warning(f"[页数校验] ⚠️ 补全{missing}页 (原{actual}→现{expected_count})")
        return tasks

    if actual > expected_count:
        trimmed = tasks[:expected_count]
        logger.warning(f"[页数校验] ✂️ 裁剪{actual-expected_count}页 (原{actual}→现{expected_count})")
        return trimmed

    return tasks

def _build_retrieval_query(prompt: str, history: list, max_user_turns: int = 3) -> str:
    """
    用多轮对话构造检索查询：取最近若干轮用户话术 + 当前追加需求。
    """
    user_texts = []
    for msg in history or []:
        role = getattr(msg, "role", None)
        if role == "user":
            content = getattr(msg, "content", "") or ""
            user_texts.append(content)
    recent_user_texts = user_texts[-max_user_turns:] if user_texts else []
    # 将当前prompt放在最前，让模型更贴近“本次生成目的”
    parts = [prompt] + recent_user_texts
    return "\n".join([p for p in parts if p.strip()])

def _extract_keywords_cn(text: str, max_keywords: int = 20) -> List[str]:
    """
    粗粒度中文关键词抽取（无第三方分词依赖）：
    - 连续2个以上中文字符
    - 连续2个以上英数字
    """
    if not text:
        return []
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}", text)
    seen = set()
    out = []
    for t in tokens:
        t = t.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_keywords:
            break
    return out

def _score_knowledge_doc(doc: dict, keywords: List[str]) -> int:
    """
    基于关键词命中次数的极简“检索”策略。
    """
    if not keywords:
        return 0

    name = (doc.get("name") or "")
    tags = doc.get("tags") or []
    if isinstance(tags, list):
        tags_str = " ".join([str(x) for x in tags if x is not None])
    else:
        tags_str = str(tags)
    content = (doc.get("content") or "")

    haystack = f"{name}\n{tags_str}\n{content}"
    score = 0
    for kw in keywords:
        if kw and kw in haystack:
            score += 1
    return score

def _retrieve_top_k_knowledge(knowledge_docs: list, query: str, k: int = 5) -> List[dict]:
    keywords = _extract_keywords_cn(query, max_keywords=20)
    scored = []
    for d in knowledge_docs or []:
        s = _score_knowledge_doc(d, keywords)
        if s > 0:
            scored.append((s, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:k]]

def _format_knowledge_context(docs: List[dict], max_chars_per_doc: int = 900, max_total_chars: int = 6000) -> str:
    lines = []
    total = 0
    for d in docs or []:
        name = d.get("name") or "未命名资料"
        content = (d.get("content") or "").strip()
        if not content:
            continue
        snippet = content[:max_chars_per_doc]
        block = f"- {name}: {snippet}"
        total += len(block)
        lines.append(block)
        if total >= max_total_chars:
            break
    return "\n".join(lines)

async def chat_with_llm_stream(prompt: str, history: list, user_id: str = "default_user") -> AsyncGenerator[str, None]:
    """
    Kimi 流式对话接口 - 集成 RAG 向量检索 + 对话历史管理
    增强功能：
    1. 自动从知识库检索相关内容
    2. 智能管理对话历史上下文
    3. 支持多轮对话连贯性
    """
    try:
        context_str = ""
        rag_sources = []
        
        try:
            retrieval_query = _build_retrieval_query(prompt, history, max_user_turns=5)
            
            rag_context = await get_rag_context_for_chat(
                query=retrieval_query,
                user_id=user_id,
                max_context_length=3000
            )
            
            if rag_context:
                context_str = f"\n\n{rag_context}\n\n请基于上述知识库资料回答问题，并在回答中标注引用来源。如果资料与问题不相关，请忽略并基于你的专业知识回答。"
                logger.info(f"[RAG] 检索到知识库上下文，长度: {len(rag_context)}")
                
                search_result = await smart_rag_search(
                    query=retrieval_query,
                    user_id=user_id,
                    top_k=5,
                    min_confidence=0.25
                )
                rag_sources = search_result.get("results", [])
                if rag_sources:
                    logger.info(f"[RAG] 检索到 {len(rag_sources)} 条相关资料，置信度: {search_result.get('confidence')}")
                    
                    if search_result.get('detected_context'):
                        detected = search_result['detected_context']
                        if detected.get('education_level') or detected.get('subject'):
                            logger.info(f"[RAG] 智能识别: 学段={detected.get('education_level')}, 学科={detected.get('subject')}")
        except Exception as e:
            logger.warning(f"[RAG] 知识库向量检索失败: {e}，继续进行对话")

        from service.smart_rag_service import build_conversation_summary
        
        conversation_summary = build_conversation_summary(history, max_tokens=1200) if history else ""
        
        trimmed_history = history[-40:] if len(history) > 40 else history
        
        system_content = SYSTEM_INSTRUCTION_CHAT
        if context_str:
            system_content += context_str
        if conversation_summary and len(trimmed_history) > 4:
            system_content += f"\n\n{conversation_summary}\n\n请参考以上对话历史，保持回答的连贯性和一致性。"
        
        messages = [{"role": "system", "content": system_content}]
        
        for msg in trimmed_history:
            messages.append({
                "role": "assistant" if msg.role == "assistant" else "user", 
                "content": msg.content
            })
        
        messages.append({"role": "user", "content": prompt})

        if not settings.LLM_API_KEY:
            yield "【系统提示】API Key 未配置，请在 .env 中填写有效密钥。"
            return

        # 检查速率限制
        if not await rate_limiter.check_limit(user_id):
            yield "【系统提示】请求过于频繁，请稍后再试。"
            return

        import random
        max_retries = 3
        base_delay = 1  # 基础延迟1秒
        
        for attempt in range(max_retries):
            try:
                stream = await llm_client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=4096,
                    stream=True
                )
                has_content = False
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        has_content = True
                        yield chunk.choices[0].delta.content
                
                if not has_content:
                    logger.warning("LLM 返回空内容")
                    yield "【系统提示】Kimi 返回了空响应，请稍后重试。"
                
                # 成功完成，退出循环
                break
                
            except Exception as e:
                logger.error(f"Kimi 流式对话失败 (尝试 {attempt+1}/{max_retries}): {e}")
                err_str = str(e)
                
                if "429" in err_str or "rate_limit" in err_str.lower():
                    if "quota" in err_str.lower() or "exceeded" in err_str.lower():
                        yield "【系统提示】Kimi API 配额已用尽（Token额度超限），请联系管理员充值或更换API Key。"
                        break
                    elif "engine_overloaded" in err_str.lower():
                        if attempt < max_retries - 1:
                            # 计算指数退避延迟，添加随机抖动
                            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                            logger.info(f"Kimi 引擎过载，{delay:.2f}秒后重试...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            yield "【系统提示】Kimi 引擎当前过载，请稍后再试。"
                    else:
                        if attempt < max_retries - 1:
                            # 计算指数退避延迟，添加随机抖动
                            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                            logger.info(f"请求频率超限，{delay:.2f}秒后重试...")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            yield "【系统提示】Kimi 请求频率超限，请稍等几秒后重试。"
                elif "Insufficient Balance" in err_str or "402" in err_str:
                    yield "【系统提示】Kimi 服务余额不足，请联系管理员充值。"
                    break
                elif "401" in err_str or "Unauthorized" in err_str or "invalid api key" in err_str.lower():
                    yield "【系统提示】Kimi API Key 无效，请检查 .env 中的 MOONSHOT_API_KEY 是否正确。"
                    break
                elif "Timeout" in err_str or "timeout" in err_str:
                    yield "【系统提示】Kimi 响应超时，请稍后重试。"
                    break
                else:
                    yield f"【系统提示】Kimi 对话异常：{err_str[:100]}"
                    break

    except Exception as e:
        logger.error(f"流式对话最外层异常: {e}")
        yield f"【系统提示】发生未预期的错误：{str(e)[:100]}"

async def chat_with_llm(prompt: str, history: list, user_id: str = "default_user") -> str:
    """
    非流式对话，支持多驱动
    """
    full_text = ""
    async for token in chat_with_llm_stream(prompt, history, user_id):
        if "【系统提示】" in token:
            return token
        full_text += token
    return full_text


async def get_llm_response(prompt: str) -> str:
    """
    简单的 LLM 响应接口，用于智能问答等场景
    """
    try:
        resp = await llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM 响应失败: {e}")
        raise


async def decompose_topic(prompt: str, grade: str, subject: str, template_id: Optional[str] = None) -> List[dict]:
    """
    将教学主题拆解为结构化的 PPT 页面任务列表
    支持建议使用表格或图表的页面
    """
    page_count = 10
    if template_id:
        try:
            template_info = await TemplateService.get_template_by_id(template_id)
            if isinstance(template_info, dict):
                page_count = template_info.get('page_count', 10)
        except Exception:
            pass
    
    decompose_prompt = f"""你是一位「课程架构设计师」，擅长将教学主题转化为结构清晰、逻辑严密、符合认知规律的教学大纲。

## 设计任务
请将以下教学主题拆解为 {page_count} 页 PPT 的结构化教学大纲。

**主题**：{prompt}
**学段**：{grade or '通用'}
**学科**：{subject or '通用'}

## 智能分页决策引擎

根据以下因素动态决定每页内容分配：

### 因素1：学段适配（自动调整）
```
小学(1-6) → 每页1个核心点，多用具象例子，总页数可适当增加
初中(7-9) → 每页1-2个关联知识点，开始引入抽象思维
高中(10-12) → 每页可包含2-3个相关概念，支持深度分析
```

### 因素2：学科特性（自动识别）
```
数学/物理/化学 → 公式推导独立成页+例题独立成页+应用独立成页
语文/英语/历史 → 背景介绍+文本分析+主题探究分层展开
生物/地理 → 概念定义+图解说明+案例分析的递进结构
```

### 因素3：内容复杂度（智能判断）
```
高复杂度概念 → 拆分为：是什么→为什么→证明/推导→性质→应用（占3-4页）
中等复杂度 → 拆分为：定义→要点→例题→练习（占2-3页）
低复杂度基础 → 可合并相关点，每页覆盖2-3个小知识点
```

## 大纲质量标准

### ✅ 优秀大纲特征
1. **逻辑链完整**：每一页都是上一页的自然延伸，形成知识链条
2. **认知坡度合理**：从易到难、从具体到抽象、从已知到未知
3. **重难点突出**：关键概念有专门页面深入讲解，而非一笔带过
4. **活动设计嵌入**：不只是知识罗列，还包含思考/讨论/练习环节

### ❌ 禁止出现的低质大纲
1. **标题空洞**：如"第一部分"、"内容一"、"知识点"等无信息量标题
2. **描述敷衍**：如"讲解本节内容"、"介绍相关知识"等万能套话
3. **逻辑跳跃**：前后页之间无衔接，知识断层明显
4. **主次不分**：核心概念与次要细节占用相同篇幅

## 标准PPT架构模板（智能适配）

```
【固定框架】（约占30%页数）
├─ 第1页: 封面 —— 课程标题+情感化副标题（引发学习兴趣）
├─ 第2页: 学习目标 —— 用行为动词表述的三维目标
└─ 第3页: 情境导入 —— 真实情境/认知冲突/问题链

【弹性主体】（约占50%页数，按需分配）
├─ 概念建立层：定义→内涵→外延→辨析（每个新概念1-2页）
├─ 深入理解层：原理推导/方法步骤/机制分析（重难点重点展开）
├─ 应用迁移层：典型例题→变式训练→实际应用（讲练结合）

【收尾框架】（约占20%页数）
├─ 倒数第2页: 课堂小结 —— 知识图谱/思维导图式梳理
└─ 最后1页: 结束页 —— 分层作业+激励语+下节预告
```

## description字段编写规范（最关键！）

description不是标题的解释，而是**该页的完整教学设计脚本**：

### 📝 正确示例
```json
{{
  "topic": "长方形周长的计算",
  "description": "本页教学设计：(1)回顾周长概念——封闭图形一周的长度；(2)引导学生观察长方形的四条边，发现对边相等的特点；(3)推导两种计算方法：方法一(长+宽)×2、方法二 长×2+宽×4；(4)通过具体数字例题演示两种方法的计算过程；(5)对比两种方法的适用场景；(6)⚠️强调单位统一的重要性"
}}
```

### 🚫 错误示例
```json
{{
  "topic": "长方形周长的计算", 
  "description": "讲解周长计算方法"
}}
```

### description必须包含的要素
- [ ] 本页要达成的具体学习目标
- [ ] 教学内容的呈现顺序（第一步做什么、第二步...）
- [ ] 需要标注的重点(⭐)、难点(⚠️)、易错点(💡)
- [ ] 适合的教学方法提示（讲授/演示/讨论/探究）
- [ ] 与前后页的衔接说明

## 输出格式要求

只输出纯JSON数组，严格遵守以下规则：
1. **禁止**任何解释文字、开场白、结束语
2. **禁止**Markdown格式（**、-、#等）
3. 文本内部**用单引号替代双引号**
4. 严格保持JSON结构：

[
  {{"page": 1, "topic": "封面标题", "layout_suggestion": "cover", "description": "详细教学设计...", "content_type": "text"}},
  ...
]

## content_type智能选择指南

| 类型 | 适用场景 | 示例 |
|------|----------|------|
| text | 大多数教学内容 | 概念讲解、原理分析 |
| table | 数据对比/步骤流程/属性列表 | 公式对比表、实验步骤 |
| chart | 趋势分析/占比分析/数据分布 | 成绩统计图、比例展示 |
| mixed | 需要多种形式配合 | 文字说明+数据表格 |

请现在生成大纲，确保每个description都足够详细，能够直接作为后续内容生成的输入。"""
    
    messages = [
        {"role": "system", "content": "你是资深一线授课教师，拥有20年教学经验。你擅长将教学主题拆解为结构化的PPT教学大纲。你严格遵循教学设计规范：封面→目标→导入→概念→核心知识→重难点→例题→练习→小结→结束。description字段必须详细到可以直接作为后续内容生成的输入。只输出JSON数组。"},
        {"role": "user", "content": decompose_prompt}
    ]
    
    try:
        logger.info(f"[decompose_topic] 开始调用 LLM，超时设置: {LLM_DECOMPOSE_TIMEOUT}秒")
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.1
            ),
            timeout=LLM_DECOMPOSE_TIMEOUT
        )
        result_text = resp.choices[0].message.content
        result = _extract_json(result_text)

        if not isinstance(result, list) or len(result) == 0:
            logger.warning(f"[decompose_topic] LLM返回无效结果，使用默认大纲")
            result = _generate_default_outline(page_count, prompt)

        result = _validate_and_fix_task_count(result, page_count, prompt)
        logger.info(f"[decompose_topic] LLM 返回成功，任务数: {len(result)}")
        return result
    except asyncio.TimeoutError:
        logger.error(f"[decompose_topic] LLM 调用超时（{LLM_DECOMPOSE_TIMEOUT}秒）")
        raise
    except (APITimeoutError, APIConnectionError) as e:
        logger.error(f"[decompose_topic] LLM 连接错误: {e}")
        raise
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower() or "exceeded" in err_str.lower():
            logger.error(f"[decompose_topic] API配额耗尽: {e}")
            raise
        logger.error(f"[decompose_topic] 拆解主题失败: {e}")
        raise

async def generate_single_slide(task: dict, context: str, user_id: str = "default_user", template_id: Optional[str] = None) -> dict:
    """
    根据特定任务生成单页 PPT 的详细内容
    支持生成图片、表格、图表数据
    """
    template_info = None
    if template_id:
        template_info = await TemplateService.get_template_by_id(template_id)
        
    prompt = f"""你是一位「精品课件内容工程师」，正在为第 {task.get('page')} 页幻灯片创作高质量教学内容。

## 本页任务卡片
```
📌 主题：{task.get('page')}
🎯 页面主题：{task.get('topic')}
📐 建议版式：{task.get('layout_suggestion')}
📝 大纲要求：{task.get('description')}
🔗 课程上下文：{context}
```

## 内容生成引擎（布鲁姆分类法驱动）

### 第一步：确定本页的认知层级
根据页面类型，匹配布鲁姆教育目标分类：

| 认知层级 | 对应页面类型 | 内容特征 |
|----------|-------------|----------|
| **记忆/理解** | 封面、导入、概念定义 | 复述、识别、解释、举例 |
| **应用** | 例题演示、方法步骤 | 运用、执行、计算 |
| **分析** | 重难点辨析、对比分析 | 比较、区分、组织 |
| **评价** | 易错点分析、方法选择 | 判断、批评、论证 |
| **创造** | 综合应用、拓展思考 | 设计、建构、假设 |

### 第二步：按认知层级设计内容结构

#### 🎯 层级1-2（记忆/理解）—— 适合：封面、导入、概念页
```
内容设计模式：
├─ 核心概念呈现（是什么）
├─ 直观例子/类比（像什么）
├─ 关键特征提取（有什么特点）
├─ 与已知概念联系（和XX有什么关系）
└─ 初步应用场景（在哪里会遇到）
```

#### 🔧 层级3（应用）—— 适合：例题页、方法讲解页
```
内容设计模式：
├─ 方法/公式陈述（标准形式）
├─ 分步拆解演示（第一步→第二步→...→完成）
├─ 完整例题示范（题目+过程+答案）
├─ 变式训练（改变条件会怎样）
└─ 常见错误警示（⚠️这里容易错）
```

#### 🔬 层级4（分析）—— 适合：重难点页、对比页
```
内容设计模式：
├─ 多角度审视（从不同侧面看）
├─ 异同对比（与相似概念的差异）
├─ 本质挖掘（为什么是这样）
├─ 边界界定（适用范围/不适用情况）
└─ 深度追问（还能怎么延伸）
```

#### 💡 层级5-6（评价/创造）—— 适合：小结页、拓展页
```
内容设计模式：
├─ 知识网络构建（思维导图式梳理）
├─ 批判性思考（这个方法的优缺点）
├─ 迁移创新（还能用在什么地方）
├─ 开放性问题（引发深度思考）
└─ 学习元认知（我们是怎么学会的）
```

## 内容质量黄金标准

### ✅ 每条content必须达到的质量
```
最低标准（及格线）：
- 一句完整的观点陈述 + 一句解释说明

优质标准（推荐）：
- 核心观点 → 解释说明 → 具体举例 → 应用提示

卓越标准（追求）：
- 引发思考的问题 → 核心知识 → 多维解读 → 生活连接 
  → 学法指导 → 预期误区提醒
```

### 📊 content数组数量要求
```
封面页: 3-5条（简洁有力，突出主题）
导入页: 4-6条（情境丰富，激发兴趣）
概念页: 6-8条（全面透彻，多角度阐释）
重难点页: 7-10条（深入浅出，层层递进）
例题页: 5-8条（步骤清晰，方法明确）
练习页: 4-6条（梯度合理，覆盖面广）
小结页: 5-8条（系统回顾，提炼升华）
结束页: 3-5条（温馨收尾，激励前行）
```

## 智能标注系统

请根据内容性质自动添加标注：

| 标注 | 含义 | 使用场景 |
|------|------|----------|
| ⭐ | 重点内容 | 必须掌握的核心知识 |
| ⚠️ | 难点/易错 | 学生容易出错的地方 |
| 💡 | 技巧/窍门 | 有助于理解的记忆方法 |
| 🔑 | 关键步骤 | 解题/操作的关键环节 |
| 📌 | 重要提示 | 需要特别注意的事项 |
| 💭 | 思考引导 | 引发学生主动思考的问题 |

## 多模态内容建议（智能判断何时使用）

### 适合添加 tables 的场景
- 数据对比（两种方法的优劣对比）
- 步骤流程（实验步骤、解题流程）
- 分类整理（知识点归类汇总）
- 公式集合（相关公式列表）

### 适合添加 charts 的场景
- 趋势变化（数据随时间的变化）
- 占比分布（各部分占整体的比例）
- 对比关系（多个项目的数值比较）
- 相关性展示（两个变量之间的关系）

### 适合纯文字的场景
- 概念阐述（需要详细文字解释）
- 推理过程（逻辑链条需要逐步展开）
- 情感表达（激励语、总结语）

## 差异化教学考量

在内容中自然融入不同层次的学习支持：
- **基础层**：核心知识的清晰表述（面向所有学生）
- **提升层**：深化理解和变式应用（面向大多数学生）
- **挑战层**：拓展思考和开放问题（面向学有余力的学生）

## 语言风格微调指南

根据页面功能自动调整语气：
- **封面/结束页**：温暖有感染力，富有情感共鸣
- **导入页**：悬念感、好奇心驱动
- **概念页**：严谨准确，但不失生动
- **重难点页**：耐心细致，循循善诱
- **例题页**：清晰利落，步骤分明
- **小结页**：提纲挈领，画龙点睛

## 输出格式规范

只返回一个JSON对象，严格遵守：
1. **禁止**任何解释文字
2. 文本内**用单引号替代双引号**
3. **禁止**Markdown格式
4. 必须包含字段：title, content, type
5. 可选字段：tables, charts, images

### JSON输出示例（参考内容的丰富度和质量）
{{
  "title": "长方形周长的计算方法",
  "content": [
    "⭐ 周长的本质：封闭图形一周的长度——想象一只蚂蚁沿着图形边缘爬一圈所走的路程",
    "观察长方形的四条边：两条长是'一对双胞胎'，两条宽也是'一对双胞胎'",
    "💡 计算思路一：先找一组邻边(一条长+一条宽)，因为对边相等，所以乘2 —— 公式：(长+宽)×2",
    "💡 计算思路二：分别计算两条长和两条宽，再相加 —— 公式：长×2 + 宽×2",
    "🔑 两种方法结果完全相同！选择哪种取决于数据特点：当长+宽是整数时用方法一更简便",
    "⚠️ 致命易错点：忘记乘2！只算一条长和一条宽得到的是半周长，不是周长",
    "⚠️ 单位陷阱：长3米、宽15厘米时，必须先统一单位再计算",
    "📌 实际应用：给长方形花坛围栅栏、给课本包书皮、计算操场跑道长度等"
  ],
  "type": "content",
  "tables": [
    {{
      "name": "两种计算方法对比",
      "headers": ["维度", "方法一 (长+宽)×2", "方法二 长×2+宽×2"],
      "rows": [
        ["计算步骤", "两步：求和→乘2", "三步：分别乘→相加"],
        ["适用场景", "长宽数值接近时", "需强调各自贡献时"],
        ["易错风险", "较低", "可能漏乘某一边"]
      ]
    }}
  ]
}}
"""
    
    knowledge_docs = get_knowledge_items(user_id)
    knowledge_context = _format_knowledge_context(knowledge_docs[:5])
    
    messages = [
        {"role": "system", "content": f"""你是「豆沙包AI备课助手」的内容创作核心引擎。

## 身份定位
你是一位拥有20年一线教学经验的「精品课件内容工程师」，同时深谙认知科学与教学设计原理。

## 核心专业能力
1. **知识转化**：从RAG知识库提取教材原文 → 教学化改写 → 课堂级呈现
2. **布鲁姆分层**：根据页面类型自动匹配认知层级（记忆→理解→应用→分析→评价→创造）
3. **质量把控**：每条内容必须达到"核心观点+解释说明+举例应用"的优质标准
4. **智能标注**：自动识别并标注重点(⭐)、难点(⚠️)、易错点(💡)、关键步骤(🔑)
5. **多模态设计**：智能判断何时使用纯文字、表格、图表增强表达效果

## 工作原则
- 内容严格基于RAG知识库，禁止凭空编造
- 每页content数组5-10条，每条2-3句完整讲解
- 语言风格随页面功能自适应（温暖/严谨/清晰/启发）
- 自然融入差异化教学（基础层+提升层+挑战层）

## 参考资料（RAG知识库）
{knowledge_context}"""},
        {"role": "user", "content": prompt}
    ]
    
    try:
        logger.info(f"[generate_single_slide] 开始生成第 {task.get('page')} 页，超时设置: {LLM_SLIDE_TIMEOUT}秒")
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.4
            ),
            timeout=LLM_SLIDE_TIMEOUT
        )
        result_text = resp.choices[0].message.content
        result = _extract_json(result_text)
        
        if 'variables' not in result:
            result['variables'] = {}
        if 'images' not in result:
            result['images'] = []
        if 'tables' not in result:
            result['tables'] = []
        if 'charts' not in result:
            result['charts'] = []
        
        logger.info(f"[generate_single_slide] 第 {task.get('page')} 页生成成功")
        return result
    except asyncio.TimeoutError:
        logger.error(f"[generate_single_slide] 第 {task.get('page')} 页生成超时（{LLM_SLIDE_TIMEOUT}秒）")
        return {
            "title": task.get('topic', '无标题'), 
            "content": ["内容生成超时，请重试"], 
            "type": task.get('layout_suggestion', 'content'),
            "variables": {},
            "images": [],
            "tables": [],
            "charts": [],
            "_error": "生成超时"
        }
    except (APITimeoutError, APIConnectionError) as e:
        logger.error(f"[generate_single_slide] 第 {task.get('page')} 页连接错误: {e}")
        return {
            "title": task.get('topic', '无标题'), 
            "content": ["网络连接错误，请重试"], 
            "type": task.get('layout_suggestion', 'content'),
            "variables": {},
            "images": [],
            "tables": [],
            "charts": [],
            "_error": str(e)
        }
    except Exception as e:
        err_str = str(e)
        logger.error(f"[generate_single_slide] 第 {task.get('page')} 页生成失败: {e}")

        if "429" in err_str or "quota" in err_str.lower() or "exceeded" in err_str.lower():
            error_msg = "AI配额已用尽，请充值后重试"
        elif "Timeout" in err_str or "timeout" in err_str.lower():
            error_msg = "AI响应超时，请重试"
        else:
            error_msg = f"生成失败: {err_str[:80]}"

        return {
            "title": task.get('topic', '无标题'),
            "content": [error_msg],
            "type": task.get('layout_suggestion', 'content'),
            "variables": {},
            "images": [],
            "tables": [],
            "charts": [],
            "_error": error_msg,
            "_error_code": "QUOTA_EXCEEDED" if "429" in err_str else "UNKNOWN"
        }
async def generate_ppt_structure_direct(req: PPTGenerateRequest, user_id: str = "default_user", template_id: Optional[str] = None) -> Dict[str, Any]:
    """
    智能 PPT 结构生成 (Direct Mode) — 支持表格、图表、模板渲染增强
    """
    
    template_context = ""
    template_page_count = req.page_count
    
    if template_id:
        try:
            from service.template_service import TemplateService
            template_info = await TemplateService.get_template_by_id(template_id)
            if template_info:
                template_data = template_info.get('template_data', {})
                slides_structure = template_info.get('slides_structure', [])
                theme_colors = template_info.get('theme_colors', {})
                fonts = template_info.get('fonts', {})
                
                actual_page_count = template_data.get('page_count', req.page_count) or len(slides_structure) or req.page_count
                if actual_page_count > 0:
                    template_page_count = actual_page_count
                
                layout_types = []
                for slide_struct in (slides_structure or [])[:10]:
                    layout_name = slide_struct.get('layout_name', '')
                    if layout_name:
                        layout_types.append(f"  - 第{len(layout_types)+1}页版式: {layout_name}")
                
                color_info = []
                if theme_colors:
                    for key, val in list(theme_colors.items())[:5]:
                        color_info.append(f"  {key}: {val}")
                
                font_info = ""
                if fonts:
                    default_font = fonts.get('default_font', '')
                    if default_font:
                        font_info = f"\n- 推荐字体: {default_font}"
                
                template_context = f"""
【模板约束信息】
- 模板页数建议: {template_page_count} 页
- 模板可用版式:
{chr(10).join(layout_types) if layout_types else '  - 标准封面/内容/结束版式'}
- 模板主题色:
{chr(10).join(color_info) if color_info else '  - 默认教学风格'}
{font_info}
- 重要：生成的幻灯片 page_type 和 type 字段必须匹配模板版式（cover/content/summary/ending）
"""
                
                logger.info(f"[PPT_GEN] 使用模板: {template_id}, 页数: {template_page_count}, 版式数: {len(layout_types)}")
        except Exception as e:
            logger.warning(f"[PPT_GEN] 获取模板信息失败: {e}，使用默认设置")
    
    prompt = f"""你是一位「教学PPT架构师」，擅长将教学主题转化为结构清晰、视觉层次分明的专业课件。

## 设计任务
请为以下课程设计完整的PPT结构方案：

**主题**：{req.theme}
**学段学科**：{req.grade} {req.subject}
**页数限制**：{template_page_count} 页左右
{template_context}

## 设计原则（教学设计驱动）

### 原则1：认知负荷友好
- 每页聚焦1个核心观点，避免信息过载
- 内容按"组块"组织，每组3-5个要点
- 使用视觉层级引导注意力（标题→重点→细节）

### 原则2：教学逻辑完整
```
标准流程：封面 → 目标 → 导入 → 新知(分层) → 练习 → 小结 → 结束
变通调整：根据内容复杂度可合并/拆分，但保持逻辑闭环
```

### 原则3：版式智能匹配
根据内容特性自动选择最佳呈现方式：
- **cover**: 封面页 —— 标题+副标题+情感化设计
- **content**: 内容页 —— 标题+多级要点列表
- **summary**: 总结页 —— 要点回顾+知识框架
- **ending**: 结束页 —— 作业+激励+预告

### 原则4：多模态增强
智能判断何时使用表格/图表增强表达：
- **数据对比** → tables（如方法对比、属性列表）
- **趋势变化** → charts line/column（如成绩变化、发展历程）
- **占比分布** → charts pie/doughnut（如成分分析、比例展示）
- **步骤流程** → tables（如实验步骤、操作指南）

## 输出质量标准

### ✅ 优秀结构特征
1. **标题有信息量**：避免"第一部分"、"内容一"，使用具体知识点名称
2. **内容有层次**：每页3-7条要点，按重要性排序
3. **逻辑有衔接**：前后页之间有明确的递进或并列关系
4. **重难点突出**：关键概念占用更多篇幅，次要内容适当精简
5. **活动设计合理**：不只是知识罗列，还包含思考/讨论/练习环节

### ❌ 避免的低质输出
1. 所有页面title都是空洞的"第X页"
2. content只有1-2条且没有实质内容
3. 页面之间无逻辑关系，顺序混乱
4. 完全不考虑学段和学科特点

## 强制输出格式

只输出纯JSON对象，严格遵守：
1. **禁止**Markdown标记、解释性文字
2. 文本内**用单引号替代双引号**
3. **禁止**Markdown符号（**、-、#等）
4. page_type/type 必须是：cover / content / summary / ending

### JSON结构模板
{{
  "title": "{req.theme}",
  "slides": [
    {{
      "title": "具体且有吸引力的页面标题",
      "content": ["实质性要点1", "实质性要点2", "..."],
      "page_type": "cover",
      "type": "cover",
      "layout_suggestion": "建议的布局方式",
      "variables": {{}},
      "images": [],
      "tables": [],
      "charts": []
    }}
  ]
}}

### 可选增强字段
当内容适合时，添加以下字段提升质量：

**tables示例**（适合数据对比）:
{{"name": "对比表名", "headers": ["维度A", "维度B"], "rows": [["值1", "值2"], ["值3", "值4"]]}}

**charts示例**（适合数据可视化）:
{{"name": "图表名", "chart_type": "column_clustered|bar_clustered|line|pie|doughnut", "categories": ["类别1", "类别2"], "series": [{{"name": "系列名", "values": [数值1, 数值2]}}]}}

## 特殊要求
- 确保首尾页（cover/ending）的设计有情感温度
- 中间内容页要保证每页都有足够的信息密度
- 如果主题涉及公式/定理，考虑用独立页面深入讲解
- 练习/应用类内容应包含不同难度层次的题目提示"""

    try:
        response = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional PowerPoint content structurer. Output VALID JSON ONLY with tables and charts support."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=False
            ),
            timeout=45.0
        )
        
        raw_content = response.choices[0].message.content
        logger.info(f"AI PPT 响应原始长度: {len(raw_content)}")
        
        structured_data = _extract_json(raw_content)
        
        if not structured_data or "slides" not in structured_data:
            logger.error("解析出的 JSON 结构不完整")
            raise ValueError("生成的 PPT 结构无效")
        
        for slide in structured_data.get("slides", []):
            if 'variables' not in slide:
                slide['variables'] = {}
            if 'images' not in slide:
                slide['images'] = []
            if 'tables' not in slide:
                slide['tables'] = []
            if 'charts' not in slide:
                slide['charts'] = []
            
            if 'type' not in slide and 'page_type' in slide:
                slide['type'] = slide['page_type']
            if 'page_type' not in slide and 'type' in slide:
                slide['page_type'] = slide['type']
            
            if 'content' in slide and isinstance(slide['content'], str):
                slide['content'] = [slide['content']]
            
            for chart in slide.get('charts', []):
                if 'series' in chart:
                    for series in chart['series']:
                        if 'values' in series:
                            series['values'] = [float(v) for v in series['values']]
            
            for table in slide.get('tables', []):
                if 'rows' in table:
                    table['rows'] = [[str(cell) for cell in row] for row in table['rows']]
        
        slides = structured_data.get("slides", [])
        
        if not slides or len(slides) < 3:
            logger.warning(f"[PPT_GEN] LLM返回页数不足({len(slides)}页)，启用智能补全")
            slides = _generate_education_quality_slides(req.theme, req.grade, req.subject, template_page_count)
            structured_data["slides"] = slides
        
        slides = _validate_slide_count_and_enrich(slides, template_page_count, req.theme, req.grade, req.subject)
        structured_data["slides"] = slides
        
        _log_generation_quality(structured_data)
        
        return structured_data
        
    except asyncio.TimeoutError:
        logger.error("AI 响应超时")
        return {"slides": _generate_education_quality_slides(req.theme, req.grade, req.subject, req.page_count), "title": req.theme, "_error": "TIMEOUT"}
    except Exception as e:
        logger.error(f"Generate Direct Structure Failed: {e}")
        return {"slides": _generate_education_quality_slides(req.theme, req.grade, req.subject, req.page_count), "title": req.theme, "_error": str(e)}


def _generate_education_quality_slides(topic: str, grade: str, subject: str, page_count: int = 10) -> List[Dict[str, Any]]:
    """
    生成教育级质量的默认PPT内容
    
    当LLM返回失败或内容质量不达标时，使用此函数生成高质量兜底内容。
    
    特点：
    - 符合教学设计规范（封面→目标→导入→概念→重难点→例题→练习→小结→结束）
    - 每页包含丰富的教育级内容（6-10条要点）
    - 包含教学设计元素（⭐重点、⚠️难点、💡易错点）
    - 根据学段学科自动调整内容深度
    """
    
    grade_adjust = ""
    if grade and "小学" in str(grade):
        grade_adjust = "（适合小学生认知特点，多用具象例子和生动比喻）"
    elif grade and ("初中" in str(grade) or "高中" in str(grade)):
        grade_adjust = "（适合中学生认知水平，注重逻辑推理和能力培养）"
    
    subject_prefix = f"{subject}·" if subject else ""
    
    slides = [
        {
            "title": f"{topic}",
            "subtitle": f"{subject_prefix}{grade or ''}精品课件 | 豆沙包AI智能生成",
            "content": [
                f"⭐ 课程主题：{topic}",
                f"📚 适用学段：{grade or '通用学段'}",
                f"🎯 学科领域：{subject or '综合课程'}",
                "✨ 课件特色：结构化设计 + 多维度展开 + 互动式呈现",
                "💡 教学理念：以学生为中心，注重知识建构与能力发展"
            ],
            "page_type": "cover",
            "type": "cover",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "学习目标",
            "content": [
                "📖 知识与技能目标",
                f"  • 理解并掌握{topic}的核心概念和基本原理",
                "  • 能够运用所学知识解决相关问题",
                "  • 建立系统的知识框架和思维模型",
                "",
                "🧠 过程与方法目标",
                "  • 通过观察、分析、归纳等方法探究知识本质",
                "  • 培养逻辑思维和批判性思维能力",
                "  • 学会自主学习和合作探究的方法",
                "",
                "❤️ 情感态度价值观目标",
                f"  • 激发对{subject or '本学科'}的学习兴趣和求知欲",
                "  • 培养科学态度和创新精神",
                "  • 树立正确的价值观和社会责任感"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "情境导入 · 激发兴趣",
            "content": [
                "🤔 思考引入",
                f"  • 你在生活中遇到过与{topic}相关的现象吗？",
                "  • 为什么我们需要学习这个知识点？",
                "  • 它能帮助我们解决什么实际问题？",
                "",
                "📊 真实情境（联系生活实际）",
                f"  • 展示{topic}在现实中的应用案例",
                "  • 引导学生发现生活中的{topic}相关实例",
                "  • 创设认知冲突，激发探究欲望",
                "",
                "🎯 导入目标",
                "  • 明确本节课要解决的核心问题",
                "  • 建立新旧知识的联系，激活前概念",
                "  • 为后续学习做好心理和认知准备"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": f"核心概念 · {topic}的定义与内涵",
            "content": [
                "📌 概念定义（是什么）",
                f"  ⭐ {topic}是指...（核心概念的准确定义）",
                "  • 关键特征一：...",
                "  • 关键特征二：...",
                "  • 关键特征三：...",
                "",
                "🔍 概念辨析（不是什么）",
                "  ⚠️ 易混淆概念辨析：...",
                "  💡 记忆技巧：用类比或口诀帮助记忆",
                "",
                "🌐 概念外延（包括什么）",
                "  • 子概念1：...",
                "  • 子概念2：...",
                "  • 与其他概念的关系：..."
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "深入理解 · 原理与方法",
            "content": [
                "🔬 原理剖析（为什么是这样）",
                "  ⭐ 核心原理/公式/法则的推导过程",
                "  • 第一步：前提条件/已知条件",
                "  • 第二步：推导过程/逻辑链条",
                "  • 第三步：结论得出/公式确立",
                "",
                "🛠️ 方法步骤（怎么做）",
                "  🔑 操作方法一：标准流程",
                "  🔑 操作方法二：变式应用",
                "  💡 技巧提示：提高效率的关键点",
                "",
                "📐 适用范围与限制",
                "  • ✅ 适用于：...",
                "  ❌ 不适用于：...",
                "  ⚠️ 注意事项：边界条件和特殊情况"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "重难点突破 · 重点精讲",
            "content": [
                "⭐ 重点内容（必须掌握）",
                f"  • {topic}的核心要点一：详细阐述",
                f"  • {topic}的核心要点二：详细阐述",
                "  • 考试高频考点总结",
                "",
                "⚠️ 难点分析（容易卡壳的地方）",
                "  • 难点一：为什么难？如何突破？",
                "  • 难点二：常见错误思路及纠正",
                "  • 分步拆解法：将复杂问题简单化",
                "",
                "💡 易错点警示（考试陷阱）",
                "  • 易错类型一：概念混淆",
                "  • 易错类型二：计算/操作失误",
                "  • 📌 避错策略：建立检查清单"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "典型例题 · 方法示范",
            "content": [
                "📝 例题1（基础巩固型）",
                "  【题目】...",
                "  【解题思路】...",
                "  【完整解答】...",
                "  【方法总结】...",
                "",
                "📝 例题2（能力提升型）",
                "  【题目】...",
                "  【解题思路】...",
                "  【完整解答】...",
                "  🔑 关键技巧：...",
                "",
                "📝 例题3（拓展应用型）",
                "  【题目】...",
                "  【解题思路】...",
                "  【完整解答】...",
                "  💡 变式思考：如果条件改变会怎样？"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "课堂练习 · 即时反馈",
            "content": [
                "✏️ 基础练（面向全体学生）",
                "  练习1：...（直接应用本节知识）",
                "  练习2：...（ slight variation）",
                "  练习3：...（判断正误型）",
                "",
                "🚀 能力练（面向大多数学生）",
                "  练习4：...（需要综合运用）",
                "  练习5：...（多步骤推理）",
                "",
                "🌟 挑战练（面向学有余力的学生）",
                "  练习6：...（开放性问题）",
                "  练习7：...（创新应用/跨学科）",
                "",
                "📊 答案与解析（附详细步骤）"
            ],
            "page_type": "content",
            "type": "content",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "课堂小结 · 知识梳理",
            "content": [
                "📋 本节课我们学习了：",
                "",
                "【知识层面】",
                f"  1. {topic}的定义与内涵",
                "  2. 核心原理/公式/方法",
                "  3. 重难点与易错点",
                "",
                "【能力层面】",
                "  1. 观察/分析/归纳能力提升",
                "  2. 逻辑思维与问题解决能力",
                "  3. 知识迁移与应用能力",
                "",
                "🧠 知识网络图（思维导图式回顾）",
                f"  {topic} ← 概念 → 原理 → 应用",
                "                    ↓       ↓      ↓",
                "                  重难点   例题   练习",
                "",
                "❓ 还有什么疑问？欢迎提问讨论！"
            ],
            "page_type": "summary",
            "type": "summary",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        },
        {
            "title": "课后作业 · 拓展延伸",
            "content": [
                "📚 必做作业（巩固基础）",
                f"  1. 完成{topic}相关习题第X页第X题",
                "  2. 复习本节课笔记，整理知识框架",
                "  3. 预习下节课内容：...",
                "",
                "🎯 选做作业（能力提升）",
                "  1. 探究性任务：...",
                "  2. 实践活动：将所学应用于生活",
                "  3. 拓展阅读：推荐资源...",
                "",
                "💪 激励语",
                "  学习是一个循序渐进的过程，",
                "  每一次努力都在为未来积累力量！",
                "",
                "📅 下节预告：...",
                "  我们将继续探索..."
            ],
            "page_type": "ending",
            "type": "ending",
            "variables": {},
            "images": [],
            "tables": [],
            "charts": []
        }
    ]
    
    if page_count < len(slides):
        return slides[:page_count]
    elif page_count > len(slides):
        for i in range(len(slides), page_count):
            slides.append({
                "title": f"内容扩展 {i+1}",
                "content": [
                    f"📌 {topic}相关知识拓展 {i+1}",
                    "",
                    "• 深入探讨...",
                    "• 相关案例...",
                    "• 实际应用...",
                    "",
                    "💡 思考：这个知识点与其他内容有什么联系？"
                ],
                "page_type": "content",
                "type": "content",
                "variables": {},
                "images": [],
                "tables": [],
                "charts": []
            })
    
    logger.info(f"[教育级默认] 生成了{len(slides)}页高质量课件: {topic}")
    return slides


def _validate_slide_count_and_enrich(
    slides: List[Dict[str, Any]], 
    expected_count: int, 
    topic: str,
    grade: str,
    subject: str
) -> List[Dict[str, Any]]:
    """
    校验幻灯片数量并增强内容质量
    
    功能：
    1. 确保页数达到最低标准（最少8页）
    2. 对每页内容进行质量检查
    3. 内容不足时自动增强为教育级水准
    """
    
    MIN_SLIDES = max(8, expected_count)
    
    if not slides or len(slides) == 0:
        logger.warning(f"[页数校验] slides为空，生成默认内容")
        return _generate_education_quality_slides(topic, grade, subject, MIN_SLIDES)
    
    actual_count = len(slides)
    
    enriched_slides = []
    for idx, slide in enumerate(slides):
        enriched = dict(slide)
        
        if not enriched.get('title'):
            enriched['title'] = f"第{idx+1}页"
        
        content = enriched.get('content', [])
        if isinstance(content, str):
            content = [content] if content.strip() else []
            enriched['content'] = content
        
        page_type = enriched.get('page_type', enriched.get('type', 'content'))
        enriched['page_type'] = page_type
        enriched['type'] = enriched.get('type', page_type)
        
        enriched.setdefault('variables', {})
        enriched.setdefault('images', [])
        enriched.setdefault('tables', [])
        enriched.setdefault('charts', [])
        
        content_quality = _assess_content_quality(content, page_type)
        
        if content_quality < 0.5:
            logger.debug(f"[内容增强] 第{idx+1}页内容质量低({content_quality:.0%})，进行增强")
            enhanced_content = _enhance_slide_content(enriched, topic, idx, actual_count)
            enriched['content'] = enhanced_content
        
        enriched_slides.append(enriched)
    
    if len(enriched_slides) < MIN_SLIDES:
        missing = MIN_SLIDES - len(enriched_slides)
        default_extra = _generate_education_quality_slides(topic, grade, subject, missing + 2)
        extra_slides = default_extra[2:2+missing]
        
        for i, extra in enumerate(extra_slides):
            extra['title'] = f"补充内容 {len(enriched_slides)+i+1}"
            enriched_slides.append(extra)
        
        logger.warning(f"[页数校验] 补全{missing}页 ({actual_count}→{len(enriched_slides)})")
    
    elif len(enriched_slides) > expected_count + 5:
        trimmed = enriched_slides[:expected_count]
        logger.warning(f"[页数校验] 裁剪{len(enriched_slides)-expected_count}页 (原{len(enriched_slides)}→现{expected_count})")
        return trimmed
    
    return enriched_slides


def _assess_content_quality(content: List[str], page_type: str) -> float:
    """
    评估单页内容质量
    
    返回值：0.0-1.0
    - 0.0-0.3: 低质量（需要完全替换）
    - 0.3-0.5: 中低质量（需要大幅增强）
    - 0.5-0.7: 中等质量（可以接受）
    - 0.7-1.0: 高质量（优秀）
    """
    if not content:
        return 0.0
    
    score = 0.0
    
    total_chars = sum(len(item) for item in content)
    avg_chars_per_item = total_chars / len(content) if content else 0
    
    if len(content) >= 4:
        score += 0.25
    elif len(content) >= 2:
        score += 0.15
    else:
        score += 0.05
    
    if avg_chars_per_item >= 30:
        score += 0.25
    elif avg_chars_per_item >= 15:
        score += 0.15
    elif avg_chars_per_item >= 8:
        score += 0.08
    
    has_emoji = any('⭐' in item or '⚠️' in item or '💡' in item or '🔑' in item or '📌' in item for item in content)
    if has_emoji:
        score += 0.15
    
    has_numbering = any(item.strip().startswith(('•', '1.', '2.', '3.', '-', '①', '②')) for item in content)
    if has_numbering:
        score += 0.15
    
    has_structure = any('：' in item or ':' in item or '——' in item or '-' in item for item in content)
    if has_structure:
        score += 0.20
    
    return min(score, 1.0)


def _enhance_slide_content(
    slide: Dict[str, Any], 
    topic: str, 
    index: int,
    total: int
) -> List[str]:
    """
    增强单页内容至教育级水准
    """
    original_content = slide.get('content', [])
    title = slide.get('title', f'第{index+1}页')
    page_type = slide.get('page_type', 'content')
    
    if page_type == 'cover':
        return [
            f"⭐ {title}",
            f"📚 {topic}精品课程",
            "✨ 结构化设计 | 多维度展开 | 互动式呈现",
            "💡 以学生为中心，注重知识建构与能力发展"
        ]
    
    if page_type == 'ending':
        return [
            "📚 课后作业",
            "  1. 复习本节课核心知识点",
            "  2. 完成配套练习巩固提高",
            "  3. 预习下节课内容",
            "",
            "💪 激励语",
            "  学习是一个循序渐进的过程，",
            "  每一次努力都在为未来积累力量！"
        ]
    
    if page_type == 'summary':
        return [
            "📋 本节课知识回顾：",
            "",
            f"【核心概念】{topic}的定义与内涵",
            "【重要原理】关键公式/方法/规律",
            "【重难点】⭐重点内容 / ⚠️易错点",
            "【能力提升】思维方法与解题技巧",
            "",
            "🧠 建议绘制思维导图，构建知识网络"
        ]
    
    enhanced = list(original_content) if original_content else []
    
    if len(enhanced) < 3:
        enhanced.insert(0, f"📌 {title}")
    
    if len(enhanced) < 4:
        position = "首" if index <= 2 else ("中" if index < total - 2 else "尾")
        context_hints = {
            "首": ["本部分是学习的基础", "需要重点关注基本概念"],
            "中": ["这是核心内容", "注意前后知识的联系"],
            "尾": ["这是重要的收尾内容", "注意总结与回顾"]
        }
        hints = context_hints.get(position, ["重要内容"])
        enhanced.extend([f"  • {hints[0]}", f"  • {hints[1]}"])
    
    if len(enhanced) < 5:
        enhanced.extend([
            "",
            f"💡 提示：结合{topic}的实际应用来理解"
        ])
    
    while len(enhanced) < 4:
        enhanced.append(f"  • {topic}相关要点{len(enhanced)+1}")
    
    return enhanced


def _log_generation_quality(structured_data: Dict[str, Any]):
    """
    记录PPT生成的质量日志
    """
    slides = structured_data.get("slides", [])
    
    if not slides:
        logger.error("[PPT质量] ❌ 无幻灯片数据")
        return
    
    total_slides = len(slides)
    total_content_items = sum(len(s.get('content', [])) for s in slides)
    avg_content_per_slide = total_content_items / total_slides if total_slides > 0 else 0
    
    pages_with_rich_content = sum(1 for s in slides if len(s.get('content', [])) >= 4)
    rich_ratio = pages_with_rich_content / total_slides if total_slides > 0 else 0
    
    quality_level = "优秀" if rich_ratio >= 0.8 and avg_content_per_slide >= 6 else \
                   ("良好" if rich_ratio >= 0.6 and avg_content_per_slide >= 4 else \
                   ("合格" if rich_ratio >= 0.4 and avg_content_per_slide >= 3 else "需改进"))
    
    logger.info(f"[PPT质量] 生成完成 | 页数:{total_slides} | 平均内容:{avg_content_per_slide:.1f}条/页 | 丰富度:{rich_ratio:.0%} | 等级:{quality_level}")
