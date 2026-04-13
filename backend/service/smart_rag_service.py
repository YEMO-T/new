"""
智能RAG搜索服务 - 三层检索策略
支持：用户私有知识库 → 公共知识库 → LLM兜底
"""

import logging
import re
import time
from typing import List, Dict, Any, Optional
from repository.supabase_client import get_supabase_client, execute_with_retry
from service.vector_service import embed_text, _cosine_similarity

logger = logging.getLogger(__name__)

# RAG结果缓存（5分钟过期）
_rag_cache = {}
_rag_cache_ttl = 300  # 5分钟

def _get_cache_key(query: str, user_id: Optional[str], top_k: int) -> str:
    """生成缓存键"""
    return f"{query}:{user_id or 'none'}:{top_k}"

def _get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """获取缓存结果"""
    if cache_key in _rag_cache:
        cached = _rag_cache[cache_key]
        if time.time() - cached['timestamp'] < _rag_cache_ttl:
            logger.info(f"[RAG-CACHE] 命中缓存: {cache_key[:30]}...")
            return cached['data']
        else:
            del _rag_cache[cache_key]
    return None

def _set_cache_result(cache_key: str, result: Dict[str, Any]):
    """设置缓存结果"""
    _rag_cache[cache_key] = {
        'data': result,
        'timestamp': time.time()
    }
    
    # 清理过期缓存
    current_time = time.time()
    expired_keys = [k for k, v in _rag_cache.items() if current_time - v['timestamp'] > _rag_cache_ttl]
    for k in expired_keys:
        del _rag_cache[k]

EDUCATION_KEYWORDS = {
    "senior_high": [
        "高中", "高一", "高二", "高三", "高考", "会考",
        "必修", "选修", "学业水平"
    ],
    "university": [
        "大学", "大一", "大二", "大三", "大四", "研究生",
        "考研", "四六级", "CET", "高等数学", "线代", "概率论",
        "微积分", "大学物理", "大学语文"
    ],
    "exam": [
        "高考", "考研", "四六级", "托福", "雅思", "GRE",
        "教师资格证", "公务员", "考试"
    ],
    "junior_high": [
        "初中", "初一", "初二", "初三", "中考"
    ],
    "primary": [
        "小学", "一年级", "二年级", "三年级", "四年级", "五年级", "六年级"
    ]
}

SUBJECT_KEYWORDS = {
    "语文": ["语文", "作文", "文言文", "古诗", "阅读理解", "修辞", "成语"],
    "数学": ["数学", "函数", "方程", "几何", "代数", "概率", "统计", "导数", "积分"],
    "英语": ["英语", "English", "语法", "单词", "词汇", "完形填空", "阅读", "听力"],
    "物理": ["物理", "力学", "电学", "光学", "热学", "牛顿", "电路"],
    "化学": ["化学", "元素", "反应", "方程式", "有机", "无机", "氧化还原"],
    "生物": ["生物", "细胞", "遗传", "生态", "基因", "DNA", "RNA"],
    "历史": ["历史", "朝代", "古代", "近代", "现代", "战争", "革命"],
    "地理": ["地理", "气候", "地形", "地图", "经纬", "洋流"],
    "政治": ["政治", "哲学", "经济", "法律", "马克思主义"]
}


def detect_education_level(query: str) -> Optional[str]:
    """
    从查询中智能识别教育阶段
    """
    query_lower = query.lower()
    
    for level, keywords in EDUCATION_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in query_lower:
                return level
    
    return None


def detect_subject(query: str) -> Optional[str]:
    """
    从查询中智能识别学科
    """
    query_lower = query.lower()
    
    for subject, keywords in SUBJECT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in query_lower:
                return subject
    
    return None


async def search_knowledge(
    query: str,
    user_id: Optional[str] = None,
    visibility: Optional[str] = None,
    education_level: Optional[str] = None,
    grade: Optional[str] = None,
    subject: Optional[str] = None,
    top_k: int = 5,
    min_confidence: float = 0.3
) -> List[Dict[str, Any]]:
    """
    知识库检索 - 支持多条件过滤
    """
    try:
        query_embedding = embed_text(query)
        if query_embedding is None:
            logger.error("[ERR] 查询向量化失败")
            return []
        
        supabase = get_supabase_client()
        
        all_vectors = supabase.table("knowledge_vectors").select(
            "id, chunk_text, source_resource, page_number, chunk_index, vector_embedding, knowledge_item_id"
        ).execute()
        
        results_with_scores = []
        
        for vector_record in all_vectors.data:
            try:
                stored_embedding = vector_record.get("vector_embedding")
                if not stored_embedding:
                    continue
                
                item_id = vector_record.get("knowledge_item_id")
                item_info = supabase.table("knowledge_items").select(
                    "visibility, user_id, education_level, grade_level, subject, name"
                ).eq("id", item_id).execute()
                
                if not item_info.data:
                    continue
                
                item = item_info.data[0]
                
                if visibility and item.get("visibility") != visibility:
                    continue
                
                if user_id and item.get("user_id") != user_id:
                    if item.get("visibility") != "public":
                        continue
                
                if education_level and item.get("education_level") != education_level:
                    continue
                
                if grade and item.get("grade_level") != grade:
                    continue
                
                if subject and item.get("subject") != subject:
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
                        "knowledge_item_id": item_id,
                        "visibility": item.get("visibility"),
                        "education_level": item.get("education_level"),
                        "grade_level": item.get("grade_level"),
                        "subject": item.get("subject"),
                        "name": item.get("name")
                    })
                    
            except Exception as e:
                logger.warning(f"[WARN] 处理向量记录异常: {e}")
                continue
        
        results_with_scores.sort(key=lambda x: x["confidence_score"], reverse=True)
        return results_with_scores[:top_k]
        
    except Exception as e:
        logger.error(f"[ERR] 知识库检索异常: {e}")
        return []


async def smart_rag_search(
    query: str,
    user_id: Optional[str] = None,
    top_k: int = 5,
    min_confidence: float = 0.3
) -> Dict[str, Any]:
    """
    智能RAG搜索 - 三层检索策略（带缓存）
    
    返回格式：
    {
        "results": [...],
        "sources": ["用户知识库", "公共知识库"],
        "confidence": "high/medium/low",
        "detected_context": {
            "education_level": "senior_high",
            "subject": "数学"
        }
    }
    """
    cache_key = _get_cache_key(query, user_id, top_k)
    
    cached_result = _get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    detected_education = detect_education_level(query)
    detected_subject = detect_subject(query)
    
    logger.info(f"[INFO] 智能识别: education_level={detected_education}, subject={detected_subject}")
    
    all_results = []
    sources = []
    
    if user_id:
        private_results = await search_knowledge(
            query=query,
            user_id=user_id,
            visibility="private",
            top_k=3,
            min_confidence=min_confidence
        )
        
        if private_results:
            all_results.extend(private_results)
            sources.append("用户知识库")
            logger.info(f"[INFO] 用户私有知识库命中: {len(private_results)} 条")
    
    public_results = await search_knowledge(
        query=query,
        visibility="public",
        education_level=detected_education,
        subject=detected_subject,
        top_k=top_k,
        min_confidence=min_confidence
    )
    
    if public_results:
        seen_ids = {r["id"] for r in all_results}
        for r in public_results:
            if r["id"] not in seen_ids:
                all_results.append(r)
        
        if "公共知识库" not in sources:
            sources.append("公共知识库")
        logger.info(f"[INFO] 公共知识库命中: {len(public_results)} 条")
    
    all_results.sort(key=lambda x: x["confidence_score"], reverse=True)
    final_results = all_results[:top_k]
    
    if len(final_results) >= 3:
        confidence = "high"
    elif len(final_results) >= 1:
        confidence = "medium"
    else:
        confidence = "low"
    
    result = {
        "results": final_results,
        "sources": sources,
        "confidence": confidence,
        "detected_context": {
            "education_level": detected_education,
            "subject": detected_subject
        },
        "total_found": len(all_results)
    }
    
    _set_cache_result(cache_key, result)
    
    return result


async def get_rag_context_for_chat(
    query: str,
    user_id: Optional[str] = None,
    max_context_length: int = 3000
) -> str:
    """
    为对话获取RAG上下文（增强版）
    - 支持多轮对话查询优化
    - 智能过滤低质量结果
    - 格式化引用来源
    """
    search_result = await smart_rag_search(
        query=query,
        user_id=user_id,
        top_k=5,
        min_confidence=0.25
    )
    
    if not search_result["results"]:
        return ""
    
    context_parts = []
    current_length = 0
    
    for idx, result in enumerate(search_result["results"], 1):
        content = result.get("content", "")
        source = result.get("name") or result.get("source_resource", "未知来源")
        confidence = result.get("confidence_score", 0)
        
        if confidence < 0.3:
            continue
        
        snippet = content[:800]
        if len(content) > 800:
            snippet += "..."
        
        part = f"\n【参考资料{idx}】(来源: {source}, 相关度: {confidence:.1%})\n{snippet}\n"
        
        if current_length + len(part) > max_context_length:
            break
        
        context_parts.append(part)
        current_length += len(part)
    
    if context_parts:
        sources_list = search_result.get("sources", [])
        confidence_level = search_result.get("confidence", "low")
        header = f"以下是从知识库中检索到的相关资料（共{len(context_parts)}条，来源: {'+'.join(sources_list) if sources_list else '知识库'}，置信度: {confidence_level}）：\n"
        return header + "".join(context_parts)
    
    return ""


def build_conversation_summary(history: list, max_tokens: int = 1500) -> str:
    """
    构建对话历史摘要（用于注入LLM上下文）
    
    Args:
        history: 对话历史消息列表
        max_tokens: 最大token限制
    
    Returns:
        格式化的对话摘要字符串
    """
    if not history or len(history) == 0:
        return ""
    
    summary_parts = []
    total_chars = 0
    
    recent_messages = history[-20:] if len(history) > 20 else history
    
    for msg in recent_messages:
        role = getattr(msg, 'role', 'unknown')
        content = getattr(msg, 'content', '') or ''
        
        if not content.strip():
            continue
        
        role_label = "教师" if role == "user" else "豆沙包"
        truncated_content = content[:200] + ("..." if len(content) > 200 else "")
        
        part = f"- {role_label}: {truncated_content}\n"
        
        if total_chars + len(part) > max_tokens:
            break
        
        summary_parts.append(part)
        total_chars += len(part)
    
    if summary_parts:
        return f"【对话历史摘要】\n{''.join(summary_parts)}"
    
    return ""


def format_search_results_for_display(results: List[Dict[str, Any]]) -> str:
    """
    格式化搜索结果用于显示
    """
    if not results:
        return "未找到相关内容"
    
    output = []
    for idx, result in enumerate(results, 1):
        content = result.get("content", "")[:200]
        if len(result.get("content", "")) > 200:
            content += "..."
        
        source = result.get("name") or result.get("source_resource", "未知来源")
        confidence = result.get("confidence_score", 0)
        subject = result.get("subject", "")
        grade = result.get("grade_level", "")
        
        output.append(f"\n{idx}. 【{source}】")
        if subject or grade:
            output.append(f"   分类: {grade} {subject}")
        output.append(f"   相关度: {confidence:.2%}")
        output.append(f"   内容: {content}")
    
    return "\n".join(output)


async def get_knowledge_stats() -> Dict[str, Any]:
    """
    获取知识库统计信息
    """
    try:
        def query_stats(supabase):
            return supabase.table("knowledge_items").select(
                "education_level, grade_level, subject, resource_type, vector_status, visibility"
            ).execute()
        
        items = execute_with_retry(query_stats, operation_name="get_knowledge_stats")
        
        data = items.data
        
        stats = {
            "total": len(data),
            "public": 0,
            "private": 0,
            "by_education": {},
            "by_subject": {},
            "by_status": {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0
            }
        }
        
        for item in data:
            visibility = item.get("visibility", "private")
            if visibility == "public":
                stats["public"] += 1
            else:
                stats["private"] += 1
            
            edu = item.get("education_level") or "未分类"
            stats["by_education"][edu] = stats["by_education"].get(edu, 0) + 1
            
            subject = item.get("subject") or "未分类"
            stats["by_subject"][subject] = stats["by_subject"].get(subject, 0) + 1
            
            status = item.get("vector_status") or "pending"
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        
        return stats
        
    except Exception as e:
        logger.error(f"[ERR] 获取统计信息异常: {e}")
        return {"error": str(e)}
