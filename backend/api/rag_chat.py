"""
RAG智能问答API - 基于知识库的AI问答
结合向量检索和大语言模型实现精准问答
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncGenerator
from pydantic import BaseModel
import logging
import json
import asyncio

from core.auth import get_current_user
from core.config import settings
from repository.supabase_client import get_supabase_client
from service.rag_vector_service import search_rag

logger = logging.getLogger(__name__)

router = APIRouter()


class RAGQuestionRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None
    grade: Optional[str] = None
    subject: Optional[str] = None
    top_k: int = 5
    min_confidence: float = 0.3
    stream: bool = True


class RAGAnswerResponse(BaseModel):
    answer: str
    sources: List[dict]
    conversation_id: str


def build_rag_prompt(question: str, contexts: List[dict], grade: str = None, subject: str = None) -> str:
    """
    构建 RAG 提示词
    """
    context_text = ""
    for i, ctx in enumerate(contexts, 1):
        source_name = ctx.get("item_name") or ctx.get("source_resource", "未知来源")
        chunk_text = ctx.get("chunk_text", "")
        similarity = ctx.get("similarity", 0)
        context_text += f"\n【参考资料 {i}】(来源: {source_name}, 相关度: {similarity:.2%})\n{chunk_text}\n"
    
    grade_subject_info = ""
    if grade or subject:
        parts = []
        if grade:
            parts.append(grade)
        if subject:
            parts.append(subject)
        grade_subject_info = f"当前教学背景：{'、'.join(parts)}\n\n"
    
    system_prompt = f"""你是一位专业的教学助手，擅长根据提供的参考资料回答教师的问题。

{grade_subject_info}请基于以下参考资料回答问题，要求：
1. 回答要准确、专业，尽量引用参考资料中的内容
2. 如果参考资料不足以回答问题，请诚实说明
3. 回答要有条理，适合教学场景使用
4. 如果涉及知识点，请给出清晰的解释

{context_text}

---
教师问题：{question}

请给出专业、详细的回答："""

    return system_prompt


async def generate_rag_answer_stream(
    prompt: str,
    conversation_id: str,
    sources: List[dict]
) -> AsyncGenerator[str, None]:
    """
    流式生成 RAG 回答
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE
        )
        
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位专业的教学助手，擅长根据参考资料回答教师的问题。"},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            temperature=0.7,
            max_tokens=2000
        )
        
        full_answer = ""
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer += content
                
                data = json.dumps({"token": content}, ensure_ascii=False)
                yield f"data: {data}\n\n"
        
        supabase = get_supabase_client()
        supabase.table("rag_messages").insert({
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": full_answer,
            "sources": sources
        }).execute()
        
        supabase.table("rag_conversations").update({
            "updated_at": "NOW()"
        }).eq("id", conversation_id).execute()
        
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        
    except Exception as e:
        logger.error(f"[ERR] 流式生成失败: {e}")
        error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
        yield f"data: {error_data}\n\n"


async def generate_rag_answer(prompt: str) -> str:
    """
    非流式生成 RAG 回答
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE
        )
        
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一位专业的教学助手，擅长根据参考资料回答教师的问题。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"[ERR] 生成回答失败: {e}")
        return f"抱歉，生成回答时出现错误：{str(e)}"


@router.post("/rag/ask")
async def ask_rag_question(
    request: RAGQuestionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    RAG 智能问答
    
    基于知识库检索相关内容，结合大模型生成回答
    支持流式和非流式两种模式
    """
    try:
        if not request.question or len(request.question.strip()) < 2:
            return {
                "code": 400,
                "data": None,
                "message": "问题内容至少2个字符"
            }
        
        logger.info(f"[INFO] RAG问答: user={user_id}, question={request.question[:50]}...")
        
        contexts = await search_rag(
            query=request.question,
            user_id=user_id,
            grade=request.grade,
            subject=request.subject,
            top_k=request.top_k,
            min_confidence=request.min_confidence
        )
        
        sources = []
        for ctx in contexts:
            sources.append({
                "knowledge_item_id": ctx.get("knowledge_item_id"),
                "chunk_text": ctx.get("chunk_text", "")[:200] + "...",
                "source_resource": ctx.get("item_name") or ctx.get("source_resource"),
                "similarity": ctx.get("similarity"),
                "grade": ctx.get("item_grade"),
                "subject": ctx.get("item_subject")
            })
        
        supabase = get_supabase_client()
        
        if request.conversation_id:
            conv_check = supabase.table("rag_conversations").select("id").eq(
                "id", request.conversation_id
            ).eq("user_id", user_id).execute()
            
            if not conv_check.data:
                request.conversation_id = None
        
        if not request.conversation_id:
            title = request.question[:30] + ("..." if len(request.question) > 30 else "")
            conv_result = supabase.table("rag_conversations").insert({
                "user_id": user_id,
                "title": title
            }).execute()
            
            if conv_result.data:
                request.conversation_id = conv_result.data[0]["id"]
        
        supabase.table("rag_messages").insert({
            "conversation_id": request.conversation_id,
            "role": "user",
            "content": request.question
        }).execute()
        
        prompt = build_rag_prompt(
            question=request.question,
            contexts=contexts,
            grade=request.grade,
            subject=request.subject
        )
        
        if request.stream:
            return StreamingResponse(
                generate_rag_answer_stream(
                    prompt=prompt,
                    conversation_id=request.conversation_id,
                    sources=sources
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Conversation-Id": request.conversation_id
                }
            )
        
        else:
            answer = await generate_rag_answer(prompt)
            
            supabase.table("rag_messages").insert({
                "conversation_id": request.conversation_id,
                "role": "assistant",
                "content": answer,
                "sources": sources
            }).execute()
            
            supabase.table("rag_conversations").update({
                "updated_at": "NOW()"
            }).eq("id", request.conversation_id).execute()
            
            return {
                "code": 200,
                "data": {
                    "answer": answer,
                    "sources": sources,
                    "conversation_id": request.conversation_id
                },
                "message": "回答生成成功"
            }
        
    except Exception as e:
        logger.error(f"[ERR] RAG问答失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"问答失败: {str(e)}"
        }


@router.get("/rag/conversations")
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_current_user)
):
    """
    获取用户的对话列表
    """
    try:
        supabase = get_supabase_client()
        
        offset = (page - 1) * page_size
        
        result = supabase.table("rag_conversations").select(
            "id, title, created_at, updated_at",
            count="exact"
        ).eq("user_id", user_id).order("updated_at", desc=True).range(
            offset, offset + page_size - 1
        ).execute()
        
        conversations = result.data if result.data else []
        total = result.count if hasattr(result, 'count') and result.count else len(conversations)
        
        return {
            "code": 200,
            "data": {
                "conversations": conversations,
                "total": total,
                "page": page,
                "page_size": page_size
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取对话列表失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.get("/rag/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取对话详情（包含所有消息）
    """
    try:
        supabase = get_supabase_client()
        
        conv = supabase.table("rag_conversations").select("*").eq(
            "id", conversation_id
        ).eq("user_id", user_id).execute()
        
        if not conv.data:
            return {
                "code": 404,
                "data": None,
                "message": "对话不存在"
            }
        
        messages = supabase.table("rag_messages").select(
            "id, role, content, sources, created_at"
        ).eq("conversation_id", conversation_id).order("created_at").execute()
        
        return {
            "code": 200,
            "data": {
                "conversation": conv.data[0],
                "messages": messages.data if messages.data else []
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取对话详情失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.delete("/rag/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除对话
    """
    try:
        supabase = get_supabase_client()
        
        conv = supabase.table("rag_conversations").select("id").eq(
            "id", conversation_id
        ).eq("user_id", user_id).execute()
        
        if not conv.data:
            return {
                "code": 404,
                "data": None,
                "message": "对话不存在"
            }
        
        supabase.table("rag_messages").delete().eq(
            "conversation_id", conversation_id
        ).execute()
        
        supabase.table("rag_conversations").delete().eq(
            "id", conversation_id
        ).execute()
        
        return {
            "code": 200,
            "data": None,
            "message": "对话已删除"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 删除对话失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"删除失败: {str(e)}"
        }


@router.post("/rag/quick-search")
async def quick_search(
    request: RAGQuestionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    快速搜索 - 仅返回相关知识点，不生成回答
    """
    try:
        contexts = await search_rag(
            query=request.question,
            user_id=user_id,
            grade=request.grade,
            subject=request.subject,
            top_k=request.top_k,
            min_confidence=request.min_confidence
        )
        
        results = []
        for ctx in contexts:
            results.append({
                "content": ctx.get("chunk_text"),
                "source": ctx.get("item_name") or ctx.get("source_resource"),
                "similarity": ctx.get("similarity"),
                "grade": ctx.get("item_grade"),
                "subject": ctx.get("item_subject"),
                "visibility": ctx.get("item_visibility")
            })
        
        return {
            "code": 200,
            "data": results,
            "message": f"找到 {len(results)} 条相关内容"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 快速搜索失败: {e}")
        return {
            "code": 500,
            "data": [],
            "message": f"搜索失败: {str(e)}"
        }
