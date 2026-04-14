"""
一键PPT生成模块 (Direct PPT Generator)
========================================

核心设计：
- 取消所有中间步骤（大纲/预览）
- 用户触发生成 → 直接输出渲染完成的PPTX文件
- 强制使用模板库样式，完全匹配视觉效果

工作流程：
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  用户请求     │────▶│  LLM内容生成     │────▶│  样式应用引擎     │
│ (主题+模板)   │     │ (内部自动完成)    │     │  (强制匹配模板)    │
└──────────────┘     └─────────────────┘     └──────────────────┘
                                                      │
                                                      ▼
                                              ┌──────────────────┐
                                              │  输出PPTX文件     │
                                              │  (直接下载)       │
                                              └──────────────────┘

API 端点：
POST /api/ppt/generate-direct          - 一键生成（传入slides数据）
POST /api/ppt/generate-from-topic      - 从主题生成（LLM自动生成内容）

与旧版区别：
- 旧版：decompose → generate slides → preview → render → export（5步）
- 本版：generate-direct → download（1步）
"""

import os
import json
import logging
import asyncio
import concurrent.futures
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from io import BytesIO

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.auth import get_current_user
from repository.supabase_client import upload_ppt_to_public_bucket, get_supabase_client
from service.template_library_service import (
    TemplateLibraryService,
    get_template_library_service,
)
from utils.intelligent_ppt_builder import IntelligentPPTBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ppt", tags=["ppt_direct"])

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

GENERATE_TIMEOUT = 180


# ============================================================
# Pydantic Models
# ============================================================

class SlideInput(BaseModel):
    """单页幻灯片输入"""
    title: str = Field(..., description="页面标题")
    subtitle: str = Field("", description="副标题")
    content: List[str] = Field(default_factory=list, description="内容列表")
    page_type: str = Field("content", description="页面类型: cover/content/toc/summary/ending")


class DirectGenerateRequest(BaseModel):
    """一键生成请求（已有slides数据）"""
    title: str = Field(..., description="演示文稿标题")
    template_id: str = Field(..., description="模板ID（从模板库选择）")
    slides: List[SlideInput] = Field(..., description="幻灯片数据列表")
    auto_download: bool = Field(True, description="是否直接返回文件流")


class TopicGenerateRequest(BaseModel):
    """从主题生成请求（LLM自动生成内容）"""
    topic: str = Field(..., description="教学主题")
    template_id: str = Field(..., description="模板ID")
    title: str = Field("", description="演示文稿标题（可选，默认用topic）")
    grade: str = Field("", description="年级")
    subject: str = Field("", description="学科")
    slide_count: int = Field(10, ge=3, le=30, description="期望页数")
    auto_download: bool = Field(True, description="是否直接返回文件流")


class GenerateResponse(BaseModel):
    """生成响应"""
    success: bool = True
    message: str = ""
    file_name: str = ""
    file_size: int = 0
    slide_count: int = 0
    engine_used: str = ""
    style_applied: bool = False
    template_name: str = ""
    download_url: Optional[str] = None
    generation_time: float = 0.0


# ============================================================
# 核心生成逻辑
# ============================================================

def _generate_ppt_direct(
    slides_data: List[Dict[str, Any]],
    template_id: str,
    title: str = "未命名演示"
) -> Tuple[bytes, Dict[str, Any]]:
    """
    核心生成函数 - 直接输出渲染好的PPT
    
    完整流程：
    1. 从模板库获取样式基因
    2. 使用 IntelligentPPTBuilder 构建PPT
    3. 强制应用完整样式（颜色/字体/版式）
    
    Args:
        slides_data: 幻灯片数据
        template_id: 模板ID
        title: 标题
        
    Returns:
        (pptx_bytes, metadata)
    """
    start_time = datetime.now()
    
    logger.info(f"[DirectGenerate] 开始生成 | 标题: {title} | 页数: {len(slides_data)} | 模板: {template_id}")
    
    if not slides_data:
        raise ValueError("幻灯片数据为空")
    
    slides_data = _validate_and_enrich_slides(slides_data)
    
    logger.info(f"[DirectGenerate] 数据校验完成 | 实际页数: {len(slides_data)}")
    
    for idx, slide in enumerate(slides_data):
        content_len = len(slide.get('content', []))
        logger.debug(f"  第{idx+1}页: {slide.get('title', '无标题')} [{slide.get('page_type', 'content')}] 内容{content_len}条")
    
    svc = get_template_library_service()
    
    style_profile = svc.get_template_style(template_id)
    
    if style_profile:
        logger.info(f"[DirectGenerate] 样式加载成功:")
        logger.info(f"  主色调: {style_profile.primary_color}")
        logger.info(f"  标题字体: {style_profile.title_font}")
        logger.info(f"  正文字体: {style_profile.body_font}")
        logger.info(f"  版式数: {len(style_profile.layouts)}")
    else:
        logger.warning(f"[DirectGenerate] 未找到模板样式，将使用默认样式")
    
    builder = IntelligentPPTBuilder()
    
    result_bytes, engine_used = builder.build_with_fallback(
        slides_data=slides_data,
        template_id=template_id,
        title=title,
    )
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    metadata = {
        'engine_used': engine_used,
        'style_applied': style_profile is not None,
        'template_name': '',
        'generation_time': elapsed,
        'file_size': len(result_bytes),
        'slide_count': len(slides_data),
    }
    
    if style_profile:
        metadata['style_info'] = {
            'primary_color': style_profile.primary_color,
            'title_font': style_profile.title_font,
            'body_font': style_profile.body_font,
        }
    
    logger.info(f"[DirectGenerate] 生成完成 | 引擎: {engine_used} | 耗时: {elapsed:.1f}s | 大小: {len(result_bytes)/1024:.1f}KB")
    
    return result_bytes, metadata


async def _generate_slides_from_topic(
    topic: str,
    template_id: str,
    grade: str = "",
    subject: str = "",
    expected_count: int = 10
) -> Tuple[List[Dict[str, Any]], str]:
    """
    从主题自动生成幻灯片内容（内部调用LLM）
    
    Args:
        topic: 教学主题
        template_id: 模板ID
        grade: 年级
        subject: 学科
        expected_count: 期望页数
        
    Returns:
        (slides_data, title)
    """
    logger.info(f"[DirectGenerate] LLM生成内容 | 主题: {topic} | 期望页数: {expected_count}")
    
    try:
        from service.llm_service import decompose_topic, generate_single_slide
        
        tasks = await decompose_topic(
            prompt=topic,
            grade=grade or None,
            subject=subject or None,
            template_id=template_id
        )
        
        if not tasks:
            raise ValueError("LLM未能拆解大纲")
        
        logger.info(f"[DirectGenerate] 大纲已拆解: {len(tasks)} 个任务")
        
        slides_data = []
        
        for i, task in enumerate(tasks[:expected_count]):
            try:
                task_dict = task.dict() if hasattr(task, 'dict') else dict(task)
                
                slide_content = await generate_single_slide(
                    task=task_dict,
                    context={"topic": topic, "index": i + 1},
                    user_id="direct-generate",
                    template_id=template_id
                )
                
                if isinstance(slide_content, dict):
                    slide_data = {
                        'title': slide_content.get('title', task_dict.get('topic', f'第{i+1}页')),
                        'subtitle': slide_content.get('subtitle', ''),
                        'content': slide_content.get('content', []),
                        'page_type': _detect_page_type(i, len(tasks), task_dict),
                    }
                else:
                    slide_data = {
                        'title': task_dict.get('topic', f'第{i+1}页'),
                        'content': [],
                        'page_type': _detect_page_type(i, len(tasks), task_dict),
                    }
                
                slides_data.append(slide_data)
                
                content_count = len(slide_data.get('content', []))
                if content_count < 5:
                    logger.warning(f"  ⚠️ 第{i+1}页内容过少({content_count}条)，自动补充至5条")
                    slides_data[-1] = _ensure_min_content(slide_data, task_dict, i, len(tasks))
                
                logger.debug(f"  已生成第{i+1}页: {slide_data['title']} | 内容{len(slides_data[-1].get('content', []))}条")
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"  第{i+1}页生成失败: {e}，使用智能兜底内容")
                task_dict = task.dict() if hasattr(task, 'dict') else dict(task)
                topic_text = task_dict.get('topic', f'第{i+1}页')
                desc_text = task_dict.get('description', '')
                fallback_content = _build_fallback_slide_content(topic_text, desc_text, i, len(tasks))
                slides_data.append(fallback_content)
        
        if not slides_data:
            raise ValueError("未能生成任何幻灯片内容")
        
        title = topic
        logger.info(f"[DirectGenerate] LLM内容生成完成: {len(slides_data)} 页")
        
        return slides_data, title
        
    except Exception as e:
        logger.error(f"[DirectGenerate] LLM内容生成失败: {e}", exc_info=True)
        raise


def _validate_and_enrich_slides(slides_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    渲染前的最终数据质量校验与丰富
    
    确保每页幻灯片都有：
      1. 非空标题
      2. 至少5条内容
      3. 正确的page_type
      4. 结构化的content数组
    
    Args:
        slides_data: 原始幻灯片数据列表
        
    Returns:
        校验并丰富后的幻灯片数据列表
    """
    if not slides_data:
        raise ValueError("幻灯片数据为空")
    
    total = len(slides_data)
    enriched = []
    
    for idx, slide in enumerate(slides_data):
        if not isinstance(slide, dict):
            logger.warning(f"  [校验] 第{idx+1}页数据类型异常: {type(slide)}，使用默认")
            slide = {'title': f'第{idx+1}页', 'content': [], 'page_type': 'content'}
        
        validated = dict(slide)
        
        title = str(validated.get('title', '')).strip()
        if not title:
            validated['title'] = f'第{idx+1}页内容'
            logger.warning(f"  [校验] 第{idx+1}页标题为空，已设置默认")
        
        content = validated.get('content', [])
        if isinstance(content, str):
            content = [c.strip() for c in content.split('\n') if c.strip()]
        elif not isinstance(content, list):
            content = []
        
        if len(content) < 5:
            original_count = len(content)
            page_type = validated.get('page_type', 'content')
            
            expansion_templates = {
                'cover': [
                    f'📚 课程主题：{validated["title"]}',
                    '🎯 本课件由AI智能生成',
                    '✨ 内容经过教学化设计',
                    '💡 可根据学情灵活调整',
                    '📖 建议预习相关背景知识',
                ],
                'toc': [
                    f'📌 本节课核心内容：{validated["title"]}',
                    '⭐ 知识目标：理解核心概念',
                    '⭐ 能力目标：培养分析能力',
                    '⭐ 情感目标：激发学习兴趣',
                    '📊 学习路径清晰明确',
                ],
                'summary': [
                    f'✅ 核心要点一：{validated["title"]}',
                    '✅ 核心要点二：重点知识总结',
                    '✅ 要点回顾：易错点提醒',
                    '📊 知识框架梳理',
                    '🎯 课后巩固建议',
                ],
                'ending': [
                    '🙏 感谢认真听讲！',
                    '📝 完成配套练习巩固所学',
                    '❓ 欢迎提问交流',
                    '📚 预习下节内容',
                    '💪 及时复习温故知新',
                ],
            }
            
            pool = expansion_templates.get(page_type, [
                f'📖 {validated["title"]}要点解析',
                f'🔍 深入理解核心知识',
                f'⚠️ 注意关键细节',
                f'💡 实际应用指导',
                f'🔗 知识拓展延伸',
            ])
            
            for item in pool:
                if len(content) >= 5:
                    break
                if item not in content:
                    content.append(item)
            
            while len(content) < 5:
                content.append(f'• {validated["title"]}相关内容 ({len(content)+1})')
            
            validated['content'] = content[:10]
            logger.info(f"  [校验] 第{idx+1}页内容丰富: {original_count}→{len(validated['content'])}条")
        
        page_type = validated.get('page_type', 'content').lower()
        if page_type not in ('cover', 'toc', 'content', 'summary', 'ending'):
            if idx == 0:
                page_type = 'cover'
            elif idx == total - 1:
                page_type = 'ending'
            else:
                page_type = 'content'
            validated['page_type'] = page_type
        
        enriched.append(validated)
    
    logger.info(f"[数据校验] 完成 | 总页数: {total} | 所有页面内容均≥5条")
    
    return enriched


def _ensure_min_content(
    slide_data: Dict[str, Any],
    task_dict: Dict[str, Any],
    index: int,
    total: int
) -> Dict[str, Any]:
    """
    确保每页至少有5条有实质内容
    
    当LLM返回的content少于5条时，
    基于大纲description智能扩展内容。
    
    Args:
        slide_data: 原始幻灯片数据
        task_dict: 大纲任务数据（含topic/description）
        index: 当前页索引
        total: 总页数
        
    Returns:
        内容丰富度达标后的幻灯片数据
    """
    content = slide_data.get('content', [])
    if not isinstance(content, list):
        content = [content] if content else []
    
    topic_text = task_dict.get('topic', slide_data.get('title', f'第{index+1}页'))
    desc_text = task_dict.get('description', '')
    page_type = slide_data.get('page_type', 'content')
    
    min_required = 5
    
    if len(content) >= min_required:
        return slide_data
    
    logger.info(f"  [_ensure_min_content] 原始{len(content)}条 → 目标{min_required}条")
    
    enriched = list(content)
    
    expansion_pool = {
        'cover': [
            f'📚 课程主题：{topic_text}',
            '🎯 适用学段：通用',
            '✨ 本课件由AI智能生成，内容经过教学化设计',
            '💡 教学建议：可根据实际学情灵活调整内容深度',
            '📖 课前准备：请学生预习相关背景知识',
        ],
        'toc': [
            f'📌 本节课将系统讲解：{topic_text}',
            f'⭐ 核心知识点一：基础概念与定义',
            f'⭐ 核心知识点二：原理与方法详解',
            f'⭐ 核心知识点三：实际应用与拓展',
            '💪 能力目标：培养分析与解决问题的能力',
        ],
        'content': [
            f'📖 概念解析：{topic_text}的基本内涵',
            f'🔍 深入理解：核心要点与关键细节',
            f'⚠️ 注意事项：学习过程中需要特别留意的方面',
            f'💡 实际应用：如何将所学知识运用到实践中',
            f'🔗 知识联系：与本单元其他内容的关联',
        ],
        'summary': [
            f'✅ 要点回顾一：{topic_text}的核心概念',
            f'✅ 要点回顾二：重点知识与方法总结',
            f'✅ 要点回顾三：易错点与注意事项',
            f'📊 知识框架：本节课内容体系梳理',
            f'🎯 课后任务：巩固练习与预习提示',
        ],
        'ending': [
            f'🙏 感谢各位同学的认真听讲！',
            f'📝 课后作业：完成配套练习，巩固所学内容',
            f'❓ 筑疑时间：欢迎提问交流',
            f'📚 预习任务：下节课我们将学习...',
            f'💪 学习建议：及时复习，温故知新',
        ],
    }
    
    pool = expansion_pool.get(page_type, expansion_pool['content'])
    
    if desc_text:
        desc_lines = [line.strip() for line in desc_text.split('，') if line.strip()][:3]
        for line in desc_lines:
            if len(enriched) >= min_required:
                break
            enriched.append(f'• {line}')
    
    for item in pool:
        if len(enriched) >= min_required:
            break
        if item not in enriched:
            enriched.append(item)
    
    while len(enriched) < min_required:
        enriched.append(f'• {topic_text}相关内容补充 ({len(enriched)+1})')
    
    result = dict(slide_data)
    result['content'] = enriched[:10]
    
    logger.info(f"  [_ensure_min_content] 完成: {len(content)}→{len(result['content'])}条")
    
    return result


def _build_fallback_slide_content(topic: str, description: str, index: int, total: int) -> Dict[str, Any]:
    """
    构建智能兜底内容 — 确保每页都有有意义的文字
    
    当LLM单页生成失败时，根据大纲信息自动构建
    有实质内容的幻灯片数据，而不是空content。
    """
    page_type = _detect_page_type(index, total, {'topic': topic})

    fallback_templates = {
        'cover': {
            'title': topic,
            'subtitle': '教学课件',
            'content': [
                f'课程主题：{topic}',
                '本课件由AI智能生成',
            ],
            'page_type': 'cover',
        },
        'toc': {
            'title': '学习目标',
            'subtitle': '',
            'content': [
                '⭐ 知识目标：理解并掌握本节课的核心概念与原理',
                '⭐ 能力目标：能够运用所学知识解决实际问题',
                '⭐ 情感目标：培养学习兴趣，树立正确的学习态度',
            ],
            'page_type': 'toc',
        },
        'ending': {
            'title': '感谢观看',
            'subtitle': '',
            'content': [
                '谢谢大家！',
                '课后请认真完成作业，巩固所学知识。',
                '下节课我们将继续深入学习，敬请期待！',
            ],
            'page_type': 'ending',
        },
        'summary': {
            'title': '课堂小结',
            'subtitle': '',
            'content': [
                f'📌 本节课我们学习了：{topic}',
                '⭐ 核心要点回顾（详见课件正文）',
                '💡 重点知识已标注，请课后复习巩固',
                '📝 如有疑问，欢迎随时提问讨论',
            ],
            'page_type': 'summary',
        },
        'content': {
            'title': topic,
            'subtitle': '',
            'content': _build_content_fallback(topic, description),
            'page_type': 'content',
        },
    }

    result = fallback_templates.get(page_type, fallback_templates['content'])
    logger.info(f"[兜底内容] 第{index+1}页({page_type}): '{result['title']}' | {len(result.get('content',[]))}条内容")
    return result


def _build_content_fallback(topic: str, description: str) -> List[str]:
    """为正文页构建有意义的兜底内容"""
    lines = []

    if description and len(description) > 10:
        desc_lines = [d.strip() for d in description.replace('。', '\n').replace('；', '\n').split('\n') if d.strip()]
        for dl in desc_lines[:5]:
            if len(dl) > 5:
                lines.append(f'• {dl}')
    else:
        lines.append(f'📖 本页主题：{topic}')

    lines.extend([
        '',
        '⭐ 核心知识点一：基本概念与定义',
        '   - 理解该知识点的内涵和外延',
        '   - 掌握相关的专业术语和表达方式',
        '',
        '⭐ 核心知识点二：原理与方法',
        '   - 明确其背后的原理机制',
        '   - 学会运用相关方法解决问题',
        '',
        '💡 易错提醒：注意常见错误和误区',
        '📌 实际应用：结合实例理解并运用',
    ])

    return [l for l in lines if l.strip()]


def _detect_page_type(index: int, total: int, task: Dict[str, Any]) -> str:
    """根据位置和任务信息检测页面类型"""
    if index == 0:
        return 'cover'
    elif index == total - 1:
        return 'ending'
    elif index == 1 and total > 5:
        return 'toc'
    elif '总结' in str(task.get('topic', '')) or '小结' in str(task.get('topic', '')):
        return 'summary'
    else:
        return 'content'


# ============================================================
# API 端点
# ============================================================

@router.post("/generate-direct", response_model=GenerateResponse)
async def generate_direct_endpoint(
    request: DirectGenerateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    一键生成PPT（核心接口）
    
    用户传入已有的幻灯片数据和模板ID，
    直接返回渲染好的PPTX文件。
    
    无需经过大纲、预览等中间步骤。
    """
    start_time = datetime.now()
    
    logger.info(f"[Direct-API] 收到生成请求 | user={user_id} | title={request.title} | slides={len(request.slides)} | template={request.template_id}")
    
    try:
        slides_input = [s.dict() for s in request.slides]
        
        future = _executor.submit(
            _generate_ppt_direct,
            slides_input,
            request.template_id,
            request.title
        )
        
        try:
            pptx_bytes, metadata = future.result(timeout=GENERATE_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise HTTPException(status_code=504, detail=f"PPT生成超时（超过{GENERATE_TIMEOUT}秒）")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = request.title.replace('/', '_').replace('\\', '_').replace(':', '_')
        file_name = f"{safe_title}_{timestamp}.pptx"
        
        export_id = f"direct_{timestamp}_{user_id[:8]}"
        
        upload_res = upload_ppt_to_public_bucket(user_id, file_name, pptx_bytes)
        
        if not upload_res or not upload_res.get("success"):
            raise HTTPException(status_code=500, detail="PPT上传到Supabase存储失败，请检查存储配置")
        
        download_url = upload_res.get("url")
        storage_path = upload_res.get("path")
        storage_bucket = upload_res.get("bucket")
        
        logger.info(f"[Direct-API] 文件已上传Supabase公开桶: {storage_path}")
        
        try:
            supabase = get_supabase_client()
            supabase.table('ppt_exports').insert({
                'id': export_id,
                'user_id': user_id,
                'template_id': request.template_id,
                'title': request.title,
                'file_name': file_name,
                'file_size': len(pptx_bytes),
                'format': 'pptx',
                'storage_bucket': storage_bucket,
                'storage_path': storage_path,
                'download_url': download_url,
                'slide_count': len(request.slides),
                'engine_used': metadata.get('engine_used', 'unknown'),
                'status': 'completed',
                'created_at': datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            logger.debug(f"[Direct-API] 导出记录创建失败: {e}")
        
        try:
            supabase.table('user_templates').update({
                'usage_count': ... ,
                'updated_at': datetime.now().isoformat(),
            }).eq('id', request.template_id).execute()
        except Exception:
            pass
        
        return GenerateResponse(
            success=True,
            message=f"PPT生成成功！共 {len(request.slides)} 页，耗时 {elapsed:.1f} 秒",
            file_name=file_name,
            file_size=len(pptx_bytes),
            slide_count=len(request.slides),
            engine_used=metadata.get('engine_used', 'unknown'),
            style_applied=metadata.get('style_applied', False),
            template_name=metadata.get('template_name', ''),
            download_url=download_url,
            generation_time=elapsed,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Direct-API] 生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PPT生成失败: {str(e)}")


@router.post("/generate-from-topic", response_model=GenerateResponse)
async def generate_from_topic_endpoint(
    request: TopicGenerateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    从主题一键生成PPT（全自动）
    
    只需要提供主题和模板ID，
    内部自动完成：LLM生成内容 → 应用样式 → 输出PPTX
    
    最简化的用户交互。
    """
    start_time = datetime.now()
    title = request.title or request.topic
    
    logger.info(f"[Topic-API] 收到主题生成请求 | user={user_id} | topic={request.topic} | template={request.template_id}")
    
    try:
        loop = asyncio.get_event_loop()
        
        slides_data, generated_title = await _generate_slides_from_topic(
            topic=request.topic,
            template_id=request.template_id,
            grade=request.grade,
            subject=request.subject,
            expected_count=request.slide_count,
        )
        
        future = _executor.submit(
            _generate_ppt_direct,
            slides_data,
            request.template_id,
            title
        )
        
        try:
            pptx_bytes, metadata = future.result(timeout=GENERATE_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise HTTPException(status_code=504, detail=f"PPT生成超时（超过{GENERATE_TIMEOUT}秒）")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')
        file_name = f"{safe_title}_{timestamp}.pptx"
        
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        download_url = None
        storage_path = ''
        
        try:
            storage_path = f"exports/{user_id}/topic_{timestamp}_{file_name}"
            
            supabase.storage.from_('coursewares').upload(
                storage_path,
                pptx_bytes,
                {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            )
            
            download_url = supabase.storage.from_('coursewares').get_public_url(storage_path)
            
        except Exception as e:
            logger.warning(f"[Topic-API] 上传Storage失败: {e}")
        
        try:
            supabase.table('ppt_exports').insert({
                'id': f"topic_{timestamp}_{user_id[:8]}",
                'user_id': user_id,
                'template_id': request.template_id,
                'title': title,
                'file_name': file_name,
                'file_size': len(pptx_bytes),
                'format': 'pptx',
                'storage_bucket': 'coursewares',
                'storage_path': storage_path,
                'download_url': download_url or '',
                'slide_count': len(slides_data),
                'engine_used': metadata.get('engine_used', 'unknown'),
                'status': 'completed',
                'created_at': datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            logger.debug(f"[Topic-API] 导出记录创建失败: {e}")
        
        return GenerateResponse(
            success=True,
            message=f"PPT生成成功！从主题「{request.topic}」生成了 {len(slides_data)} 页，耗时 {elapsed:.1f} 秒",
            file_name=file_name,
            file_size=len(pptx_bytes),
            slide_count=len(slides_data),
            engine_used=metadata.get('engine_used', 'unknown'),
            style_applied=metadata.get('style_applied', False),
            template_name=metadata.get('template_name', ''),
            download_url=download_url,
            generation_time=elapsed,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Topic-API] 生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PPT生成失败: {str(e)}")


@router.post("/download-file")
async def download_generated_file(
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    下载生成的PPT文件（文件流方式）
    
    当 auto_download=true 时使用此端点直接返回文件流。
    """
    body = await request.json()
    download_url = body.get('download_url')
    
    if not download_url:
        raise HTTPException(status_code=400, detail="缺少download_url参数")
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)
            response.raise_for_status()
            
            file_bytes = response.content
            
            return StreamingResponse(
                iter([file_bytes]),
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={
                    "Content-Disposition": f'attachment; filename="{body.get("file_name", "generated.pptx")}"'
                }
            )
            
    except Exception as e:
        logger.error(f"[Download] 下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")


@router.get("/exports/{export_id}/download")
async def download_export_file(export_id: str, user_id: str = Depends(get_current_user)):
    """
    本地导出文件下载端点 — 最可靠的下载方式
    
    当Supabase Storage上传失败时，
    文件保存在本地data/exports/目录，
    通过此端点直接返回文件流。
    
    优先级：
      1. 本地文件存在 → 直接FileResponse
      2. 数据库有记录且是http URL → RedirectResponse
      3. 都没有 → 返回404
    """
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', export_id):
        raise HTTPException(status_code=400, detail="无效的导出ID格式")

    from fastapi.responses import FileResponse, RedirectResponse

    local_export_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'exports'
    )

    local_files = []
    if os.path.isdir(local_export_dir):
        local_files = [
            f for f in os.listdir(local_export_dir)
            if f.startswith(export_id) and f.endswith('.pptx')
        ]

    if local_files:
        file_path = os.path.join(local_export_dir, local_files[0])
        file_name = local_files[0].split('_', 1)[1] if '_' in local_files[0] else 'generated.pptx'
        logger.info(f"[LocalDownload] 找到本地文件: {file_path} ({os.path.getsize(file_path)} bytes)")
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=file_name,
        )

    try:
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        response = supabase.table('ppt_exports').select('*').eq('id', export_id).execute()

        if response.data:
            record = response.data[0]
            public_url = record.get('download_url', '')
            if public_url and public_url.startswith('http'):
                logger.info(f"[LocalDownload] 重定向到公开URL")
                return RedirectResponse(url=public_url)

            local_db_path = record.get('local_path')
            if local_db_path and os.path.exists(local_db_path):
                file_name = record.get('file_name', 'generated.pptx')
                return FileResponse(
                    local_db_path,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    filename=file_name,
                )
    except Exception as e:
        logger.debug(f"[LocalDownload] 数据库查询失败: {e}")

    raise HTTPException(status_code=404, detail=f"导出文件不存在 (ID: {export_id})")


@router.get("/templates-with-style")
async def list_templates_with_style(
    user_id: str = Depends(get_current_user)
):
    """
    获取可用模板列表（含样式摘要）
    
    供前端选择模板时展示。
    """
    svc = get_template_library_service()
    
    items, total = svc.get_template_list(
        user_id=user_id,
        template_type='personal',
        page=1,
        page_size=50,
    )
    
    templates = []
    for item in items:
        templates.append({
            'id': item.id,
            'title': item.title,
            'usage_count': item.usage_count,
            'style_preview': {
                'primary_color': item.primary_color,
                'title_font': item.title_font,
                'body_font': item.body_font,
                'layout_count': item.layout_count,
                'has_style': item.has_style,
            }
        })
    
    return {
        'success': True,
        'templates': templates,
        'total': total,
    }
