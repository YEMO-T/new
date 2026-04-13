"""
智能问答API - 基于RAG的智能回答
支持：知识库检索 → LLM生成回答 → 兜底处理
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging
import asyncio

from service.smart_rag_service import (
    smart_rag_search,
    get_rag_context_for_chat,
    format_search_results_for_display,
    get_knowledge_stats,
    detect_education_level,
    detect_subject
)
from service.llm_service import get_llm_response
from core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/knowledge/smart-search")
async def smart_search_endpoint(
    query: str = Query(..., description="查询文本"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数"),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0, description="最小置信度"),
    user_id: str = Depends(get_current_user)
):
    """
    智能搜索接口 - 三层检索策略
    
    检索顺序：
    1. 用户私有知识库
    2. 公共知识库（预设教材）
    3. 返回置信度评估
    
    Returns:
        {
            "code": 200,
            "data": {
                "results": [...],
                "sources": ["用户知识库", "公共知识库"],
                "confidence": "high/medium/low",
                "detected_context": {
                    "education_level": "senior_high",
                    "subject": "数学"
                }
            }
        }
    """
    try:
        if not query or len(query.strip()) == 0:
            return {
                "code": 400,
                "data": None,
                "message": "查询文本不能为空"
            }
        
        logger.info(f"🔍 智能搜索: query='{query}', user={user_id[:8] if user_id else 'anonymous'}...")
        
        result = await smart_rag_search(
            query=query,
            user_id=user_id,
            top_k=top_k,
            min_confidence=min_confidence
        )
        
        return {
            "code": 200,
            "data": result,
            "message": f"检索完成，置信度: {result['confidence']}"
        }
        
    except Exception as e:
        logger.error(f"❌ 智能搜索异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"搜索失败: {str(e)}"
        }


@router.post("/knowledge/smart-answer")
async def smart_answer_endpoint(
    query: str = Query(..., description="用户问题"),
    use_llm: bool = Query(True, description="是否使用LLM生成回答"),
    user_id: str = Depends(get_current_user)
):
    """
    智能问答接口 - 基于RAG的智能回答
    
    流程：
    1. 检索知识库获取相关内容
    2. 如果有结果，基于知识库生成回答
    3. 如果无结果，使用LLM通用知识兜底
    
    Returns:
        {
            "code": 200,
            "data": {
                "answer": "回答内容",
                "sources": ["公共知识库"],
                "confidence": "high",
                "source_details": [...],
                "is_fallback": false
            }
        }
    """
    try:
        if not query or len(query.strip()) == 0:
            return {
                "code": 400,
                "data": None,
                "message": "问题不能为空"
            }
        
        logger.info(f"💬 智能问答: query='{query}'")
        
        search_result = await smart_rag_search(
            query=query,
            user_id=user_id,
            top_k=5,
            min_confidence=0.3
        )
        
        results = search_result["results"]
        sources = search_result["sources"]
        confidence = search_result["confidence"]
        detected = search_result["detected_context"]
        
        is_fallback = False
        answer = ""
        
        if results and use_llm:
            context = await get_rag_context_for_chat(query, user_id)
            
            if context:
                prompt = f"""你是一个专业的教学助手。请根据以下参考资料回答用户的问题。

参考资料：
{context}

用户问题：{query}

请基于参考资料给出准确、专业的回答。如果参考资料中没有相关信息，请明确说明。"""
                
                try:
                    answer = await get_llm_response(prompt)
                    logger.info(f"[OK] 基于知识库生成回答")
                except Exception as e:
                    logger.error(f"[ERR] LLM生成失败: {e}")
                    answer = format_search_results_for_display(results)
            else:
                answer = format_search_results_for_display(results)
        
        elif results:
            answer = format_search_results_for_display(results)
        
        else:
            is_fallback = True
            sources = ["AI通用知识"]
            
            if use_llm:
                detected_info = ""
                if detected.get("education_level"):
                    level_map = {
                        "senior_high": "高中",
                        "university": "大学",
                        "exam": "考试"
                    }
                    detected_info += f"教育阶段：{level_map.get(detected['education_level'], detected['education_level'])}。"
                if detected.get("subject"):
                    detected_info += f"学科：{detected['subject']}。"
                
                prompt = f"""你是一个专业的教学助手。{detected_info}

用户问题：{query}

知识库中暂无相关资料，请根据你的通用知识给出回答。请注意说明这是基于通用知识的回答，建议用户上传相关教材获取更精准的答案。"""
                
                try:
                    answer = await get_llm_response(prompt)
                    logger.info(f"[OK] 使用LLM通用知识兜底")
                except Exception as e:
                    logger.error(f"[ERR] LLM兜底失败: {e}")
                    answer = "抱歉，知识库中暂无相关资料，且AI服务暂时不可用。请稍后再试或上传相关教材。"
            else:
                answer = "知识库中未找到相关内容。建议上传相关教材或使用其他关键词搜索。"
        
        return {
            "code": 200,
            "data": {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "source_details": [
                    {
                        "name": r.get("name"),
                        "subject": r.get("subject"),
                        "grade_level": r.get("grade_level"),
                        "confidence_score": r.get("confidence_score")
                    }
                    for r in results[:3]
                ] if results else [],
                "is_fallback": is_fallback,
                "detected_context": detected,
                "notice": "此回答基于AI通用知识，建议上传相关教材获取更精准答案" if is_fallback else None
            },
            "message": "回答生成成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 智能问答异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"回答生成失败: {str(e)}"
        }


@router.get("/knowledge/stats")
async def knowledge_stats_endpoint():
    """
    获取知识库统计信息
    
    Returns:
        {
            "code": 200,
            "data": {
                "total": 100,
                "public": 80,
                "private": 20,
                "by_education": {...},
                "by_subject": {...},
                "by_status": {...}
            }
        }
    """
    try:
        stats = await get_knowledge_stats()
        
        return {
            "code": 200,
            "data": stats,
            "message": "获取统计信息成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取统计信息异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取统计信息失败: {str(e)}"
        }


@router.post("/knowledge/detect-context")
async def detect_context_endpoint(
    query: str = Query(..., description="查询文本")
):
    """
    智能识别查询的教育阶段和学科
    
    Returns:
        {
            "code": 200,
            "data": {
                "education_level": "senior_high",
                "education_level_name": "高中",
                "subject": "数学"
            }
        }
    """
    try:
        education_level = detect_education_level(query)
        subject = detect_subject(query)
        
        level_names = {
            "senior_high": "高中",
            "university": "大学",
            "exam": "考试",
            "junior_high": "初中",
            "primary": "小学"
        }
        
        return {
            "code": 200,
            "data": {
                "education_level": education_level,
                "education_level_name": level_names.get(education_level, "未识别"),
                "subject": subject
            },
            "message": "识别成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 识别异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"识别失败: {str(e)}"
        }
