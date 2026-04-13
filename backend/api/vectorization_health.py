"""
向量化健康检查 API
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import logging

from core.auth import get_current_user_optional
from service.robust_vector_service import (
    get_robust_embedding_service,
    get_robust_vectorization_service
)
from repository.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vectorization", tags=["vectorization"])


@router.get("/health")
async def get_vectorization_health() -> Dict[str, Any]:
    """
    获取向量化服务健康状态
    
    返回:
    - embedding: 嵌入模型状态
    - stats: 处理统计
    - pending_count: 待处理条目数
    - failed_count: 失败条目数
    """
    try:
        vector_service = get_robust_vectorization_service()
        health = vector_service.get_health_status()
        
        supabase = get_supabase_client()
        
        pending_result = supabase.table("knowledge_items").select(
            "id", count="exact"
        ).eq("vector_status", "pending").execute()
        
        failed_result = supabase.table("knowledge_items").select(
            "id", count="exact"
        ).eq("vector_status", "failed").execute()
        
        completed_result = supabase.table("knowledge_items").select(
            "id", count="exact"
        ).eq("vector_status", "completed").execute()
        
        health["database"] = {
            "pending_count": pending_result.count if pending_result.count else 0,
            "failed_count": failed_result.count if failed_result.count else 0,
            "completed_count": completed_result.count if completed_result.count else 0
        }
        
        health["overall_status"] = "healthy" if health["embedding"]["is_ready"] else "degraded"
        
        return {
            "code": 200,
            "data": health,
            "message": "健康检查完成"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 健康检查失败: {e}")
        return {
            "code": 500,
            "data": {
                "overall_status": "unhealthy",
                "error": str(e)
            },
            "message": "健康检查失败"
        }


@router.get("/embedding/status")
async def get_embedding_status() -> Dict[str, Any]:
    """
    获取嵌入模型详细状态
    """
    try:
        embedding_service = get_robust_embedding_service()
        status = embedding_service.get_status()
        
        return {
            "code": 200,
            "data": status,
            "message": "获取成功"
        }
        
    except Exception as e:
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.post("/retry-failed")
async def retry_failed_items(
    user_id: str = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    重试所有失败的向量化条目
    """
    try:
        vector_service = get_robust_vectorization_service()
        
        result = await vector_service.batch_vectorize(
            user_id=user_id,
            include_failed=True
        )
        
        return {
            "code": 200,
            "data": result,
            "message": f"处理完成: 成功 {result['success']}, 失败 {result['failed']}"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 重试失败条目异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"重试失败: {str(e)}"
        }


@router.post("/process-pending")
async def process_pending_items(
    user_id: str = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    处理所有待向量化的条目
    """
    try:
        vector_service = get_robust_vectorization_service()
        
        result = await vector_service.batch_vectorize(
            user_id=user_id,
            include_failed=False
        )
        
        return {
            "code": 200,
            "data": result,
            "message": f"处理完成: 成功 {result['success']}, 失败 {result['failed']}"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 处理待处理条目异常: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"处理失败: {str(e)}"
        }


@router.get("/stats")
async def get_vectorization_stats() -> Dict[str, Any]:
    """
    获取向量化统计信息
    """
    try:
        vector_service = get_robust_vectorization_service()
        stats = vector_service.get_stats()
        
        supabase = get_supabase_client()
        
        status_counts = {}
        for status in ["pending", "processing", "completed", "failed"]:
            result = supabase.table("knowledge_items").select(
                "id", count="exact"
            ).eq("vector_status", status).execute()
            status_counts[status] = result.count if result.count else 0
        
        return {
            "code": 200,
            "data": {
                "service_stats": stats,
                "database_stats": status_counts
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }
