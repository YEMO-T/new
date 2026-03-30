"""
向量化处理服务 - 负责文本切块、向量化、存储
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from sentence_transformers import SentenceTransformer
from repository.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

_embedding_model = None

def get_embedding_model():
    """获取或初始化向量模型（单例模式）"""
    global _embedding_model
    if _embedding_model is None:
        logger.info("[INFO] 正在加载向量模型 all-MiniLM-L6-v2...")
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("[OK] 向量模型加载完成")
    return _embedding_model


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 100) -> List[str]:
    """
    将文本切块，支持重叠
    
    Args:
        text: 原始文本
        chunk_size: 每块大小（字符数）
        overlap: 块之间的重叠字符数
    
    Returns:
        切块后的文本列表
    """
    if not text or len(text) == 0:
        return []
    
    chunks = []
    step = chunk_size - overlap
    
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_size]
        if len(chunk.strip()) > 0:
            chunks.append(chunk)
        
        if i + chunk_size >= len(text):
            break
    
    logger.info(f"[INFO] 文本切块完成: {len(text)} 字符 -> {len(chunks)} 块")
    return chunks


def embed_text(text: str) -> Optional[List[float]]:
    """
    将文本向量化
    
    Args:
        text: 要向量化的文本
    
    Returns:
        384维的向量列表，失败返回None
    """
    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"[ERR] 向量化失败: {e}")
        return None


async def vectorize_knowledge_item(
    item_id: str,
    content: str,
    source_resource: str = "unknown",
    page_number: int = 0
) -> Dict[str, Any]:
    """
    对单个知识库条目进行向量化处理
    """
    try:
        supabase = get_supabase_client()
        
        supabase.table("knowledge_items").update({
            "vector_status": "processing"
        }).eq("id", item_id).execute()
        
        logger.info(f"[INFO] 开始向量化条目: {item_id}")
        
        chunks = chunk_text(content, chunk_size=512, overlap=100)
        if not chunks:
            raise ValueError("文本切块失败或内容为空")
        
        vectors_to_insert = []
        for chunk_index, chunk_text_content in enumerate(chunks):
            embedding = embed_text(chunk_text_content)
            if embedding is None:
                logger.warning(f"[WARN] 第{chunk_index}块向量化失败，跳过")
                continue
            
            vectors_to_insert.append({
                "knowledge_item_id": item_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text_content,
                "vector_embedding": embedding,
                "source_resource": source_resource,
                "page_number": page_number,
                "confidence_score": 1.0
            })
        
        if vectors_to_insert:
            supabase.table("knowledge_vectors").insert(vectors_to_insert).execute()
            logger.info(f"[OK] 插入 {len(vectors_to_insert)} 个向量")
        
        supabase.table("knowledge_items").update({
            "vector_status": "completed",
            "chunk_count": len(vectors_to_insert)
        }).eq("id", item_id).execute()
        
        supabase.table("vectorization_logs").insert({
            "knowledge_item_id": item_id,
            "status": "success",
            "chunk_count": len(vectors_to_insert)
        }).execute()
        
        logger.info(f"[OK] 条目 {item_id} 向量化完成: {len(vectors_to_insert)} 块")
        
        return {
            "success": True,
            "chunk_count": len(vectors_to_insert),
            "item_id": item_id
        }
        
    except Exception as e:
        logger.error(f"[ERR] 向量化失败: {e}")
        
        try:
            supabase = get_supabase_client()
            supabase.table("knowledge_items").update({
                "vector_status": "failed"
            }).eq("id", item_id).execute()
            
            supabase.table("vectorization_logs").insert({
                "knowledge_item_id": item_id,
                "status": "failed",
                "error_message": str(e)
            }).execute()
        except Exception as log_error:
            logger.error(f"[ERR] 记录失败日志异常: {log_error}")
        
        return {
            "success": False,
            "error": str(e),
            "item_id": item_id
        }


async def batch_vectorize_pending_items() -> Dict[str, Any]:
    """
    批量处理所有待向量化的条目
    """
    try:
        supabase = get_supabase_client()
        
        pending_items = supabase.table("knowledge_items").select(
            "id, name, content"
        ).eq("vector_status", "pending").execute()
        
        items = pending_items.data
        logger.info(f"[INFO] 发现 {len(items)} 个待处理条目")
        
        results = {
            "total": len(items),
            "success": 0,
            "failed": 0
        }
        
        for item in items:
            result = await vectorize_knowledge_item(
                item_id=item["id"],
                content=item.get("content", ""),
                source_resource=item.get("name", "unknown")
            )
            
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
            
            await asyncio.sleep(0.1)
        
        logger.info(f"[OK] 批量处理完成: 成功{results['success']}, 失败{results['failed']}")
        return results
        
    except Exception as e:
        logger.error(f"[ERR] 批量处理异常: {e}")
        return {"total": 0, "success": 0, "failed": 0, "error": str(e)}


async def search_rag(
    query: str,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    top_k: int = 5,
    min_confidence: float = 0.5
) -> List[Dict[str, Any]]:
    """
    RAG精准检索
    """
    try:
        query_embedding = embed_text(query)
        if query_embedding is None:
            logger.error("[ERR] 查询向量化失败")
            return []
        
        logger.info(f"[INFO] 执行RAG搜索: query='{query}', grade={grade}, subject={subject}")
        
        supabase = get_supabase_client()
        
        query_sql = """
        SELECT 
            kv.id,
            kv.chunk_text as content,
            kv.source_resource,
            kv.page_number,
            kv.chunk_index,
            ki.grade_level,
            ki.subject,
            1 - (kv.vector_embedding <=> %s::vector) as similarity_score
        FROM public.knowledge_vectors kv
        JOIN public.knowledge_items ki ON kv.knowledge_item_id = ki.id
        WHERE 1 - (kv.vector_embedding <=> %s::vector) > %s
        """
        
        params = [query_embedding, query_embedding, min_confidence]
        
        if grade:
            query_sql += " AND ki.grade_level = %s"
            params.append(grade)
        
        if subject:
            query_sql += " AND ki.subject = %s"
            params.append(subject)
        
        query_sql += f" ORDER BY similarity_score DESC LIMIT {top_k}"
        
        all_vectors = supabase.table("knowledge_vectors").select(
            "id, chunk_text, source_resource, page_number, chunk_index, vector_embedding, knowledge_item_id"
        ).execute()
        
        results_with_scores = []
        for vector_record in all_vectors.data:
            try:
                stored_embedding = vector_record.get("vector_embedding")
                if not stored_embedding:
                    continue
                
                similarity = _cosine_similarity(query_embedding, stored_embedding)
                
                if similarity >= min_confidence:
                    results_with_scores.append({
                        "id": vector_record["id"],
                        "content": vector_record["chunk_text"],
                        "source_resource": vector_record["source_resource"],
                        "page_number": vector_record["page_number"],
                        "chunk_index": vector_record["chunk_index"],
                        "confidence_score": float(similarity),
                        "knowledge_item_id": vector_record["knowledge_item_id"]
                    })
            except Exception as e:
                logger.warning(f"[WARN] 处理向量记录异常: {e}")
                continue
        
        results_with_scores.sort(key=lambda x: x["confidence_score"], reverse=True)
        final_results = results_with_scores[:top_k]
        
        logger.info(f"[OK] 检索完成: 返回 {len(final_results)} 条结果")
        
        try:
            supabase.table("search_history").insert({
                "query": query,
                "grade": grade,
                "subject": subject,
                "results_count": len(final_results),
                "top_confidence_score": final_results[0]["confidence_score"] if final_results else 0.0
            }).execute()
        except Exception as e:
            logger.warning(f"[WARN] 记录搜索历史异常: {e}")
        
        return final_results
        
    except Exception as e:
        logger.error(f"[ERR] RAG搜索异常: {e}")
        return []


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算两个向量的余弦相似度
    """
    try:
        import numpy as np
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return (similarity + 1) / 2
        
    except Exception as e:
        logger.error(f"[ERR] 相似度计算异常: {e}")
        return 0.0


async def get_vectorization_status(item_id: str) -> Dict[str, Any]:
    """
    获取条目的向量化状态
    """
    try:
        supabase = get_supabase_client()
        
        item = supabase.table("knowledge_items").select(
            "id, name, vector_status, chunk_count"
        ).eq("id", item_id).execute()
        
        if not item.data:
            return {"error": "条目不存在"}
        
        return {
            "item_id": item_id,
            "name": item.data[0]["name"],
            "status": item.data[0]["vector_status"],
            "chunk_count": item.data[0]["chunk_count"]
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取状态异常: {e}")
        return {"error": str(e)}
