"""
RAG知识库检索API - 精准搜索接口
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import logging
from service.vector_service import (
    vectorize_knowledge_item,
    search_rag,
    batch_vectorize_pending_items,
    get_vectorization_status
)
from core.auth import get_current_user
from repository.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/knowledge/search-rag")
async def search_rag_endpoint(
    query: str = Query(..., description="查询文本"),
    grade: Optional[str] = Query(None, description="年级（可选）"),
    subject: Optional[str] = Query(None, description="学科（可选）"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0, description="最小置信度")
):
    """
    RAG精准检索接口
    
    执行向量相似度搜索，返回匹配度最高的知识点
    
    Args:
        query: 查询文本（必需）
        grade: 年级（可选，如：小学三年级）
        subject: 学科（可选，如：数学）
        top_k: 返回结果数（1-20，默认5）
        min_confidence: 最小置信度（0-1，默认0.5）
    
    Returns:
        {
            "code": 200,
            "data": [
                {
                    "content": "知识点内容",
                    "source_resource": "来源资源名称",
                    "page_number": 10,
                    "confidence_score": 0.95,
                    "chunk_index": 2
                }
            ],
            "message": "检索成功"
        }
    """
    try:
        if not query or len(query.strip()) == 0:
            return {
                "code": 400,
                "data": [],
                "message": "查询文本不能为空"
            }
        
        logger.info(f"🔍 RAG搜索请求: query='{query}', grade={grade}, subject={subject}, top_k={top_k}")
        
        # 执行RAG搜索
        results = await search_rag(
            query=query,
            grade=grade,
            subject=subject,
            top_k=top_k,
            min_confidence=min_confidence
        )
        
        return {
            "code": 200,
            "data": results,
            "message": f"检索成功，返回 {len(results)} 条结果"
        }
        
    except Exception as e:
        logger.error(f"❌ RAG搜索异常: {e}")
        return {
            "code": 500,
            "data": [],
            "message": f"检索失败: {str(e)}"
        }


@router.post("/knowledge/vectorize-item")
async def vectorize_item_endpoint(
    item_id: str = Query(..., description="知识库条目ID"),
    user_id: str = Depends(get_current_user)
):
    """
    手动触发单个知识库条目的向量化处理
    
    Args:
        item_id: 知识库条目ID
    
    Returns:
        {
            "code": 200,
            "data": {
                "item_id": "...",
                "chunk_count": 10,
                "status": "processing"
            },
            "message": "向量化处理已启动"
        }
    """
    try:
        supabase = get_supabase_client()
        
        # 验证条目存在且属于当前用户
        item = supabase.table("knowledge_items").select(
            "id, name, content, user_id"
        ).eq("id", item_id).execute()
        
        if not item.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        item_data = item.data[0]
        
        # 权限检查
        if item_data["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权访问此条目"
            }
        
        logger.info(f"🔄 启动向量化: item_id={item_id}, name={item_data['name']}")
        
        # 异步执行向量化
        result = await vectorize_knowledge_item(
            item_id=item_id,
            content=item_data.get("content", ""),
            source_resource=item_data.get("name", "unknown")
        )
        
        if result["success"]:
            return {
                "code": 200,
                "data": {
                    "item_id": item_id,
                    "chunk_count": result["chunk_count"],
                    "status": "completed"
                },
                "message": f"向量化完成，生成 {result['chunk_count']} 个向量"
            }
        else:
            return {
                "code": 500,
                "data": {
                    "item_id": item_id,
                    "status": "failed"
                },
                "message": f"向量化失败: {result.get('error', '未知错误')}"
            }
        
    except Exception as e:
        logger.error(f"❌ 向量化异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"处理异常: {str(e)}"
        }


@router.post("/knowledge/vectorize-batch")
async def vectorize_batch_endpoint(
    user_id: str = Depends(get_current_user)
):
    """
    批量处理所有待向量化的条目
    
    Returns:
        {
            "code": 200,
            "data": {
                "total": 10,
                "success": 8,
                "failed": 2
            },
            "message": "批量处理完成"
        }
    """
    try:
        logger.info("🔄 启动批量向量化处理")
        
        results = await batch_vectorize_pending_items()
        
        return {
            "code": 200,
            "data": results,
            "message": f"批量处理完成: 成功 {results['success']}, 失败 {results['failed']}"
        }
        
    except Exception as e:
        logger.error(f"❌ 批量处理异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"处理异常: {str(e)}"
        }


@router.get("/knowledge/vectorization-status/{item_id}")
async def get_vectorization_status_endpoint(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取条目的向量化状态
    
    Args:
        item_id: 知识库条目ID
    
    Returns:
        {
            "code": 200,
            "data": {
                "item_id": "...",
                "name": "资源名称",
                "status": "completed",
                "chunk_count": 10
            },
            "message": "获取成功"
        }
    """
    try:
        supabase = get_supabase_client()
        
        # 验证条目存在且属于当前用户
        item = supabase.table("knowledge_items").select(
            "id, user_id"
        ).eq("id", item_id).execute()
        
        if not item.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        # 权限检查
        if item.data[0]["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权访问此条目"
            }
        
        status = await get_vectorization_status(item_id)
        
        if "error" in status:
            return {
                "code": 404,
                "data": None,
                "message": status["error"]
            }
        
        return {
            "code": 200,
            "data": status,
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取状态异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.get("/knowledge/search-history")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user)
):
    """
    获取用户的搜索历史
    
    Args:
        limit: 返回记录数（1-100，默认20）
    
    Returns:
        {
            "code": 200,
            "data": [
                {
                    "query": "查询文本",
                    "grade": "年级",
                    "subject": "学科",
                    "results_count": 5,
                    "top_confidence_score": 0.95,
                    "searched_at": "2024-01-01T12:00:00Z"
                }
            ],
            "message": "获取成功"
        }
    """
    try:
        supabase = get_supabase_client()
        
        history = supabase.table("search_history").select(
            "query, grade, subject, results_count, top_confidence_score, searched_at"
        ).eq("user_id", user_id).order("searched_at", desc=True).limit(limit).execute()
        
        return {
            "code": 200,
            "data": history.data,
            "message": f"获取成功，返回 {len(history.data)} 条记录"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取搜索历史异常: {e}")
        return {
            "code": 500,
            "data": [],
            "message": f"获取失败: {str(e)}"
        }


@router.get("/knowledge/resources")
async def list_teaching_resources(
    grade: Optional[str] = Query(None, description="年级"),
    subject: Optional[str] = Query(None, description="学科"),
    resource_type: Optional[str] = Query(None, description="资源类型"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    列出公共教学资源
    
    Args:
        grade: 年级（可选）
        subject: 学科（可选）
        resource_type: 资源类型（可选）
        limit: 返回数量
        offset: 偏移量
    
    Returns:
        {
            "code": 200,
            "data": [
                {
                    "id": "...",
                    "resource_name": "资源名称",
                    "grade_level": "小学三年级",
                    "subject": "数学",
                    "resource_type": "教材",
                    "preview_url": "...",
                    "download_url": "..."
                }
            ],
            "message": "获取成功"
        }
    """
    try:
        supabase = get_supabase_client()
        
        query = supabase.table("teaching_resources").select(
            "id, resource_name, grade_level, subject, resource_type, preview_url, download_url, description"
        ).eq("is_public", True)
        
        if grade:
            query = query.eq("grade_level", grade)
        if subject:
            query = query.eq("subject", subject)
        if resource_type:
            query = query.eq("resource_type", resource_type)
        
        resources = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return {
            "code": 200,
            "data": resources.data,
            "message": f"获取成功，返回 {len(resources.data)} 条资源"
        }
        
    except Exception as e:
        logger.error(f"❌ 列出资源异常: {e}")
        return {
            "code": 500,
            "data": [],
            "message": f"获取失败: {str(e)}"
        }
