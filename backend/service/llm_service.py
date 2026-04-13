import re
import json
import logging
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional

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

llm_client = AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_API_BASE,
    timeout=LLM_TIMEOUT
)

# NOTE: 引导式多轮对话系统提示
SYSTEM_INSTRUCTION_CHAT = """你是一个名为"豆沙包"的专业 AI 教学助手，专门帮助教师设计课件、教案和互动环节。

## 知识库增强能力
你会自动从教师的知识库中检索相关资料。当检索到相关内容时，你会在回复中引用这些资料，提供更精准、更专业的回答。检索结果会标注来源和相关性。

## 多轮对话引导策略
当教师描述了一个教学需求时，你必须先通过对话充分收集以下三要素，才能确认生成：
1. **📚 课程学科** (如：小学数学、高中英语、初中物理)
2. **🎯 教学主题** (如：长方形周长、定语从句、惯性运动)
3. **学段年级** (如：三年级、高一、初二)

## 触发生成指令
只有当你收集齐了上述三个要素，并认为可以开始构思大纲时，你才可以在回复的**最末尾**（单独一行）添加标记：`[READY_TO_GENERATE]`。
注意：如果用户需求模糊，禁止添加标记！必须先礼貌追问。

## 对话风格
- 专业、温暖、富有同理心。
- 每次追问只提 1 个关键问题，避免信息过载。
- 回复内容要详实、有深度，支持长篇专业论述。
- 优先使用知识库中的资料来支撑你的回答，并标注引用来源。
- 如果知识库中有相关内容，要主动提及并说明如何利用这些资料。"""


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
                
        except Exception as e:
            logger.error(f"Kimi 流式对话失败: {e}")
            err_str = str(e)
            if "Insufficient Balance" in err_str or "402" in err_str:
                yield "【系统提示】Kimi 服务余额不足，请联系管理员充值。"
            elif "401" in err_str or "Unauthorized" in err_str or "invalid api key" in err_str.lower():
                yield "【系统提示】Kimi API Key 无效，请检查 .env 中的 MOONSHOT_API_KEY 是否正确。"
            elif "429" in err_str or "rate_limit" in err_str.lower():
                yield "【系统提示】Kimi 请求频率超限，请稍等几秒后重试。"
            elif "Timeout" in err_str or "timeout" in err_str:
                yield "【系统提示】Kimi 响应超时，请稍后重试。"
            else:
                yield f"【系统提示】Kimi 对话异常：{err_str[:100]}"

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
    
    decompose_prompt = f"""你是一个教学架构师。请将以下教学主题拆解为 {page_count} 页 PPT 的结构化大纲。
主题：{prompt}
学段：{grade}
学科：{subject}

【强制输出要求 - 违反将导致解析失败】
1. 只输出 JSON 数组，禁止任何解释文字、开场白或结束语。
2. 内部文本内容中禁止使用双引号 "，必须全部用单引号 ' 代替（例如：'赋值为'张三''）。
3. 禁止使用任何 Markdown 格式（如 **、-、# 等），输出纯文本内容。
4. 严格保持以下 JSON 结构：
[
  {{"page": 1, "topic": "标题", "layout_suggestion": "cover", "description": "描述内容", "content_type": "text"}}
]

【content_type 说明】
- text: 普通文本内容
- table: 适合用表格展示（数据对比、步骤流程、属性列表等）
- chart: 适合用图表展示（趋势分析、占比分析、对比分析等）
- mixed: 混合内容（文字+表格或图表）

请根据每页的主题内容，智能判断最适合的 content_type。
"""
    
    messages = [
        {"role": "system", "content": "你是一个专业的教学大纲设计专家，只输出 JSON 数组。"},
        {"role": "user", "content": decompose_prompt}
    ]
    
    try:
        logger.info(f"[decompose_topic] 开始调用 LLM，超时设置: {LLM_DECOMPOSE_TIMEOUT}秒")
        resp = await asyncio.wait_for(
            llm_client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                temperature=0.3
            ),
            timeout=LLM_DECOMPOSE_TIMEOUT
        )
        result_text = resp.choices[0].message.content
        result = _extract_json(result_text)
        logger.info(f"[decompose_topic] LLM 返回成功，任务数: {len(result) if isinstance(result, list) else 0}")
        return result if isinstance(result, list) else []
    except asyncio.TimeoutError:
        logger.error(f"[decompose_topic] LLM 调用超时（{LLM_DECOMPOSE_TIMEOUT}秒）")
        return []
    except (APITimeoutError, APIConnectionError) as e:
        logger.error(f"[decompose_topic] LLM 连接错误: {e}")
        return []
    except Exception as e:
        logger.error(f"[decompose_topic] 拆解主题失败: {e}")
        return []

async def generate_single_slide(task: dict, context: str, user_id: str = "default_user", template_id: Optional[str] = None) -> dict:
    """
    根据特定任务生成单页 PPT 的详细内容
    支持生成图片、表格、图表数据
    """
    template_info = None
    if template_id:
        template_info = await TemplateService.get_template_by_id(template_id)
        
    prompt = f"""请为幻灯片第 {task.get('page')} 页生成详细内容。
本页主题：{task.get('topic')}
教学上下文：{context}
建议版式：{task.get('layout_suggestion')}
要点要求：{task.get('description')}

【强制输出要求 - 极度重要】
1. 只返回一个 JSON 对象，严禁任何额外解释文字。
2. JSON 字符串内部内容中，严禁出现双引号 "，请全部替换为单引号 '。
3. 严禁使用 Markdown 格式（如 **、-、# 等），仅保留纯文本。
4. 必须包含：title, content, type 字段。
5. 如果内容适合用表格展示（如数据对比、步骤流程），请添加 tables 字段。
6. 如果内容适合用图表展示（如趋势分析、占比分析），请添加 charts 字段。
7. 如果需要配图，请添加 imagePrompt 字段描述图片内容。

【JSON 结构示例】
{{
  "title": "销售数据分析",
  "content": ["本季度销售数据如下", "总体呈上升趋势"],
  "type": "content",
  "imagePrompt": "数据图表背景图",
  "tables": [
    {{
      "name": "销售数据表",
      "headers": ["产品", "销量", "金额"],
      "rows": [["产品A", 100, 10000], ["产品B", 200, 20000]]
    }}
  ],
  "charts": [
    {{
      "name": "销售趋势",
      "chart_type": "column_clustered",
      "categories": ["Q1", "Q2", "Q3", "Q4"],
      "series": [{{"name": "销售额", "values": [100, 150, 200, 180]}}]
    }}
  ]
}}
"""
    
    knowledge_docs = get_knowledge_items(user_id)
    knowledge_context = _format_knowledge_context(knowledge_docs[:5])
    
    messages = [
        {"role": "system", "content": f"你是一个顶尖的课件撰写专家，擅长生成包含表格和图表的丰富内容。参考资料：\n{knowledge_context}"},
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
        logger.error(f"[generate_single_slide] 第 {task.get('page')} 页生成失败: {e}")
        return {
            "title": task.get('topic', '无标题'), 
            "content": ["生成失败，请重试"], 
            "type": task.get('layout_suggestion', 'content'),
            "variables": {},
            "images": [],
            "tables": [],
            "charts": [],
            "_error": str(e)
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
    
    prompt = f"""你是一个顶级的 PPT 设计专家。请根据以下需求，输出包含幻灯片结构的嵌套 JSON 对象。
【主题】: {req.theme}
【学段学科】: {req.grade} {req.subject}
【页数限制】: {template_page_count} 页左右。
{template_context}
【终极强制输出格式】
1. 只允许输出纯 JSON，禁止任何 Markdown 标记（不要用 ```json 包裹），禁止任何解释性文字。
2. JSON 内部的所有文本描述中，禁止使用双引号 "，请统一使用单引号 ' 代替。
3. 禁止使用 Markdown 符号（如 **、- 等）。
4. 格式模板：
{{
  "title": "{req.theme}",
  "slides": [
    {{
      "title": "页标题",
      "content": ["要点1", "要点2"],
      "page_type": "cover",
      "type": "cover",
      "layout_suggestion": "layout",
      "variables": {{}},
      "images": [],
      "tables": [],
      "charts": []
    }}
  ]
}}

【增强内容要求】
- 如果某页包含数据对比、步骤流程，请添加 tables 字段
- 如果某页包含趋势分析、占比分析，请添加 charts 字段
- tables 格式: {{"name": "表格名", "headers": ["列1", "列2"], "rows": [["数据1", "数据2"]]}}
- charts 格式: {{"name": "图表名", "chart_type": "column_clustered", "categories": ["类1", "类2"], "series": [{{"name": "系列1", "values": [1, 2]}}]}}
- chart_type 可选: column_clustered, bar_clustered, line, pie, doughnut
- page_type 必须为以下值之一: cover, content, summary, ending
"""

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
            
        return structured_data
        
    except asyncio.TimeoutError:
        logger.error("AI 响应超时")
        return {"slides": [], "title": req.theme, "_error": "TIMEOUT"}
    except Exception as e:
        logger.error(f"Generate Direct Structure Failed: {e}")
        return {"slides": [], "title": req.theme, "_error": str(e)}
