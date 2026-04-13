"""
RAG知识库管理API - 完整的知识库CRUD和向量化接口
支持公共/私有知识库，权限与PPT模板库一致
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from typing import List, Optional
from pydantic import BaseModel
import logging
import base64

from core.auth import get_current_user
from repository.supabase_client import get_supabase_client, execute_with_retry
from service.rag_vector_service import (
    parse_document_content,
    vectorize_knowledge_item,
    search_rag,
    batch_vectorize_pending_items,
    get_vectorization_status,
    delete_knowledge_vectors
)
from service.storage_service import (
    upload_knowledge_file,
    get_file_public_url,
    get_file_signed_url,
    delete_file,
    get_mime_type,
    KNOWLEDGE_BUCKET
)

logger = logging.getLogger(__name__)

router = APIRouter()


class KnowledgeCreateRequest(BaseModel):
    name: str
    type: str = "txt"
    size: str = "0 KB"
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    visibility: str = "private"
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    education_level: Optional[str] = None
    resource_type: Optional[str] = None
    difficulty: Optional[str] = None
    semester: Optional[str] = None
    chapter: Optional[str] = None


class KnowledgeUpdateRequest(BaseModel):
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    visibility: Optional[str] = None
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    education_level: Optional[str] = None
    resource_type: Optional[str] = None
    difficulty: Optional[str] = None
    semester: Optional[str] = None
    chapter: Optional[str] = None


class RAGSearchRequest(BaseModel):
    query: str
    grade: Optional[str] = None
    subject: Optional[str] = None
    top_k: int = 5
    min_confidence: float = 0.5


@router.get("/knowledge/list")
async def list_knowledge(
    visibility: Optional[str] = Query(None, description="可见性过滤: private/public"),
    grade: Optional[str] = Query(None, description="年级过滤"),
    subject: Optional[str] = Query(None, description="学科过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: str = Depends(get_current_user)
):
    """
    获取知识库列表
    
    - 私有知识库：仅返回当前用户的
    - 公共知识库：所有人可见
    - 不传 visibility 则返回用户私有 + 所有公共
    """
    try:
        offset = (page - 1) * page_size
        
        def query_knowledge(supabase):
            if visibility == "private":
                query = supabase.table("knowledge_items").select(
                    "id, name, type, size, tags, visibility, grade_level, subject, description, "
                    "education_level, resource_type, difficulty, semester, chapter, "
                    "vector_status, chunk_count, created_at, updated_at, user_id",
                    count="exact"
                ).eq("user_id", user_id)
                
            elif visibility == "public":
                query = supabase.table("knowledge_items").select(
                    "id, name, type, size, tags, visibility, grade_level, subject, description, "
                    "education_level, resource_type, difficulty, semester, chapter, "
                    "vector_status, chunk_count, created_at, updated_at, user_id",
                    count="exact"
                ).eq("visibility", "public")
                
            else:
                query = supabase.table("knowledge_items").select(
                    "id, name, type, size, tags, visibility, grade_level, subject, description, "
                    "education_level, resource_type, difficulty, semester, chapter, "
                    "vector_status, chunk_count, created_at, updated_at, user_id",
                    count="exact"
                ).or_(f"user_id.eq.{user_id},visibility.eq.public")
            
            if grade:
                query = query.eq("grade_level", grade)
            if subject:
                query = query.eq("subject", subject)
            if search:
                query = query.ilike("name", f"%{search}%")
            
            return query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        
        result = execute_with_retry(query_knowledge, operation_name="list_knowledge")
        
        items = result.data if result.data else []
        total = result.count if hasattr(result, 'count') and result.count else len(items)
        
        for item in items:
            item["is_owner"] = item.get("user_id") == user_id
        
        return {
            "code": 200,
            "data": {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取知识库列表失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.post("/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(..., description="上传的文件"),
    name: Optional[str] = Form(None, description="资源名称"),
    visibility: str = Form("private", description="可见性: private/public"),
    grade_level: Optional[str] = Form(None, description="年级"),
    subject: Optional[str] = Form(None, description="学科"),
    description: Optional[str] = Form(None, description="描述"),
    tags: Optional[str] = Form(None, description="标签，逗号分隔"),
    education_level: Optional[str] = Form(None, description="教育阶段"),
    resource_type: Optional[str] = Form(None, description="资源类型"),
    difficulty: Optional[str] = Form(None, description="难度"),
    semester: Optional[str] = Form(None, description="学期"),
    chapter: Optional[str] = Form(None, description="章节"),
    user_id: str = Depends(get_current_user)
):
    """
    上传知识库文件（支持 TXT/PDF/PPTX/DOCX）
    
    流程:
    1. 上传原始文件到 Storage
    2. 解析文件提取文本
    3. 保存元数据和文本到数据库
    4. 触发向量化
    """
    try:
        file_bytes = await file.read()
        original_name = file.filename or "unknown"
        file_type = original_name.split('.')[-1].lower() if '.' in original_name else 'txt'
        
        if file_type not in ['txt', 'pdf', 'pptx', 'docx']:
            return {
                "code": 400,
                "data": None,
                "message": "不支持的文件类型，仅支持 TXT/PDF/PPTX/DOCX"
            }
        
        storage_result = None
        mime_type = get_mime_type(file_type)
        
        storage_result = upload_knowledge_file(
            user_id=user_id,
            file_name=original_name,
            file_data=file_bytes,
            mime_type=mime_type
        )
        
        if not storage_result:
            logger.warning(f"[WARN] 原文件上传失败，仅保存文本内容")
        
        content, page_count = parse_document_content(file_bytes, file_type, original_name)
        
        if not content or len(content.strip()) < 10:
            if storage_result:
                delete_file(storage_result["path"], bucket=KNOWLEDGE_BUCKET)
            return {
                "code": 400,
                "data": None,
                "message": "文件内容为空或解析失败"
            }
        
        file_size_kb = len(file_bytes) / 1024
        size_str = f"{file_size_kb:.2f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
        
        resource_name = name or original_name.rsplit('.', 1)[0]
        
        tags_list = []
        if tags:
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]
        if grade_level and grade_level not in tags_list:
            tags_list.append(grade_level)
        if subject and subject not in tags_list:
            tags_list.append(subject)
        if not tags_list:
            tags_list = ["未分类"]
        
        def insert_knowledge(supabase):
            insert_data = {
                "user_id": user_id,
                "name": resource_name,
                "type": file_type,
                "size": size_str,
                "tags": tags_list,
                "content": content,
                "visibility": visibility,
                "grade_level": grade_level,
                "subject": subject,
                "description": description,
                "file_original_name": original_name,
                "education_level": education_level,
                "resource_type": resource_type,
                "difficulty": difficulty,
                "semester": semester,
                "chapter": chapter,
                "file_path": storage_result["path"] if storage_result else None,
                "file_bucket": storage_result["bucket"] if storage_result else None,
                "file_size_bytes": len(file_bytes),
                "file_mime_type": mime_type,
                "has_original_file": storage_result is not None,
                "vector_status": "pending"
            }
            return supabase.table("knowledge_items").insert(insert_data).execute()
        
        result = execute_with_retry(insert_knowledge, operation_name="upload_knowledge_file")
        
        if not result.data:
            if storage_result:
                delete_file(storage_result["path"], bucket=KNOWLEDGE_BUCKET)
            return {
                "code": 500,
                "data": None,
                "message": "插入数据库失败"
            }
        
        item = result.data[0]
        item_id = item["id"]
        
        logger.info(f"[OK] 知识库条目创建成功: {item_id}")
        
        vectorize_result = await vectorize_knowledge_item(
            item_id=item_id,
            content=content,
            source_resource=resource_name,
            page_number=page_count
        )
        
        item["vectorize_result"] = vectorize_result
        item["is_owner"] = True
        
        return {
            "code": 200,
            "data": item,
            "message": f"上传成功，已生成 {vectorize_result.get('chunk_count', 0)} 个向量"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 上传知识库失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"上传失败: {str(e)}"
        }


@router.post("/knowledge/create")
async def create_knowledge(
    request: KnowledgeCreateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    创建知识库条目（纯文本内容）
    """
    try:
        if not request.content or len(request.content.strip()) < 10:
            return {
                "code": 400,
                "data": None,
                "message": "内容不能为空且至少10个字符"
            }
        
        def create_text_knowledge(supabase):
            insert_data = {
                "user_id": user_id,
                "name": request.name,
                "type": request.type,
                "size": request.size,
                "tags": request.tags or ["未分类"],
                "content": request.content,
                "visibility": request.visibility,
                "grade_level": request.grade_level,
                "subject": request.subject,
                "description": request.description,
                "vector_status": "pending"
            }
            return supabase.table("knowledge_items").insert(insert_data).execute()
        
        result = execute_with_retry(create_text_knowledge, operation_name="create_knowledge_text")
        
        if not result.data:
            return {
                "code": 500,
                "data": None,
                "message": "创建失败"
            }
        
        item = result.data[0]
        item_id = item["id"]
        
        vectorize_result = await vectorize_knowledge_item(
            item_id=item_id,
            content=request.content,
            source_resource=request.name
        )
        
        item["vectorize_result"] = vectorize_result
        item["is_owner"] = True
        
        return {
            "code": 200,
            "data": item,
            "message": f"创建成功，已生成 {vectorize_result.get('chunk_count', 0)} 个向量"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 创建知识库失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"创建失败: {str(e)}"
        }


@router.get("/knowledge/stats")
async def get_knowledge_stats(
    user_id: str = Depends(get_current_user)
):
    """
    获取知识库统计信息
    """
    try:
        def query_private(supabase):
            return supabase.table("knowledge_items").select(
                "id", count="exact"
            ).eq("user_id", user_id).eq("visibility", "private").execute()
        
        def query_public(supabase):
            return supabase.table("knowledge_items").select(
                "id", count="exact"
            ).eq("visibility", "public").execute()
        
        def query_vectorized(supabase):
            return supabase.table("knowledge_items").select(
                "id", count="exact"
            ).or_(f"user_id.eq.{user_id},visibility.eq.public").eq("vector_status", "completed").execute()
        
        def query_pending(supabase):
            return supabase.table("knowledge_items").select(
                "id", count="exact"
            ).or_(f"user_id.eq.{user_id},visibility.eq.public").eq("vector_status", "pending").execute()
        
        private_count = execute_with_retry(query_private, operation_name="stats_private")
        public_count = execute_with_retry(query_public, operation_name="stats_public")
        vectorized_count = execute_with_retry(query_vectorized, operation_name="stats_vectorized")
        pending_count = execute_with_retry(query_pending, operation_name="stats_pending")
        
        return {
            "code": 200,
            "data": {
                "private_count": private_count.count if private_count.count else 0,
                "public_count": public_count.count if public_count.count else 0,
                "vectorized_count": vectorized_count.count if vectorized_count.count else 0,
                "pending_count": pending_count.count if pending_count.count else 0
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取统计失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.get("/knowledge/{item_id}")
async def get_knowledge_detail(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取知识库条目详情
    """
    try:
        def query_detail(supabase):
            return supabase.table("knowledge_items").select("*").eq("id", item_id).execute()
        
        result = execute_with_retry(query_detail, operation_name="get_knowledge_detail")
        
        if not result.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        item = result.data[0]
        
        if item["visibility"] != "public" and item["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权访问此条目"
            }
        
        item["is_owner"] = item["user_id"] == user_id
        
        return {
            "code": 200,
            "data": item,
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取知识库详情失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.get("/knowledge/{item_id}/download")
async def download_knowledge_file(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取知识库原始文件的下载链接
    
    - 公共知识库: 返回公共URL
    - 私有知识库: 返回签名URL (1小时有效)
    """
    try:
        def query_file_info(supabase):
            return supabase.table("knowledge_items").select(
                "id, user_id, visibility, file_path, file_bucket, has_original_file, file_original_name"
            ).eq("id", item_id).execute()
        
        res = execute_with_retry(query_file_info, operation_name="download_knowledge_file")
        
        if not res.data:
            return {"code": 404, "data": None, "message": "条目不存在"}
        
        item = res.data[0]
        
        is_owner = item["user_id"] == user_id
        is_public = item["visibility"] == "public"
        
        if not is_owner and not is_public:
            return {"code": 403, "data": None, "message": "无权访问此文件"}
        
        if not item.get("has_original_file") or not item.get("file_path"):
            return {"code": 404, "data": None, "message": "该条目没有原始文件"}
        
        if is_public:
            download_url = get_file_public_url(item["file_path"])
        else:
            download_url = get_file_signed_url(item["file_path"], expires_in=3600)
        
        if not download_url:
            return {"code": 500, "data": None, "message": "获取下载链接失败"}
        
        return {
            "code": 200,
            "data": {
                "download_url": download_url,
                "file_name": item.get("file_original_name"),
                "expires_in": 3600 if not is_public else None
            },
            "message": "获取成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 获取下载链接失败: {e}")
        return {"code": 500, "data": None, "message": f"获取失败: {str(e)}"}


@router.put("/knowledge/{item_id}")
async def update_knowledge(
    item_id: str,
    request: KnowledgeUpdateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    更新知识库条目
    
    仅创建者可更新
    """
    try:
        def query_existing(supabase):
            return supabase.table("knowledge_items").select("*").eq("id", item_id).execute()
        
        existing = execute_with_retry(query_existing, operation_name="update_knowledge_query")
        
        if not existing.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        item = existing.data[0]
        
        if item["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权修改此条目"
            }
        
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.tags is not None:
            update_data["tags"] = request.tags
        if request.visibility is not None:
            update_data["visibility"] = request.visibility
        if request.grade_level is not None:
            update_data["grade_level"] = request.grade_level
        if request.subject is not None:
            update_data["subject"] = request.subject
        if request.description is not None:
            update_data["description"] = request.description
        
        content_changed = False
        if request.content is not None and request.content != item.get("content"):
            update_data["content"] = request.content
            update_data["vector_status"] = "pending"
            content_changed = True
        
        if not update_data:
            return {
                "code": 200,
                "data": item,
                "message": "无更新内容"
            }
        
        def update_knowledge(supabase):
            return supabase.table("knowledge_items").update(update_data).eq("id", item_id).execute()
        
        result = execute_with_retry(update_knowledge, operation_name="update_knowledge_save")
        
        if not result.data:
            return {
                "code": 500,
                "data": None,
                "message": "更新失败"
            }
        
        updated_item = result.data[0]
        
        if content_changed:
            delete_knowledge_vectors(item_id)
            
            vectorize_result = await vectorize_knowledge_item(
                item_id=item_id,
                content=request.content,
                source_resource=updated_item.get("name", "unknown")
            )
            
            updated_item["vectorize_result"] = vectorize_result
        
        updated_item["is_owner"] = True
        
        return {
            "code": 200,
            "data": updated_item,
            "message": "更新成功"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 更新知识库失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"更新失败: {str(e)}"
        }


@router.delete("/knowledge/{item_id}")
async def delete_knowledge(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除知识库条目
    
    仅创建者可删除（包括公共知识库）
    """
    try:
        def query_existing(supabase):
            return supabase.table("knowledge_items").select("id, user_id, name").eq("id", item_id).execute()
        
        existing = execute_with_retry(query_existing, operation_name="delete_knowledge_query")
        
        if not existing.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        item = existing.data[0]
        
        if item["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权删除此条目"
            }
        
        delete_knowledge_vectors(item_id)
        
        def delete_item(supabase):
            return supabase.table("knowledge_items").delete().eq("id", item_id).execute()
        
        result = execute_with_retry(delete_item, operation_name="delete_knowledge")
        
        return {
            "code": 200,
            "data": None,
            "message": f"已删除「{item['name']}」"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 删除知识库失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"删除失败: {str(e)}"
        }


@router.post("/knowledge/search")
async def search_knowledge(
    request: RAGSearchRequest,
    user_id: str = Depends(get_current_user)
):
    """
    RAG 向量相似度搜索
    
    搜索范围：用户私有知识库 + 所有公共知识库
    """
    try:
        if not request.query or len(request.query.strip()) < 2:
            return {
                "code": 400,
                "data": [],
                "message": "查询内容至少2个字符"
            }
        
        results = await search_rag(
            query=request.query,
            user_id=user_id,
            grade=request.grade,
            subject=request.subject,
            top_k=request.top_k,
            min_confidence=request.min_confidence
        )
        
        return {
            "code": 200,
            "data": results,
            "message": f"找到 {len(results)} 条相关内容"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 搜索失败: {e}")
        return {
            "code": 500,
            "data": [],
            "message": f"搜索失败: {str(e)}"
        }


@router.post("/knowledge/vectorize/{item_id}")
async def vectorize_item(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    手动触发向量化（重新向量化）
    """
    try:
        def query_item(supabase):
            return supabase.table("knowledge_items").select("*").eq("id", item_id).execute()
        
        item = execute_with_retry(query_item, operation_name="vectorize_item_query")
        
        if not item.data:
            return {
                "code": 404,
                "data": None,
                "message": "条目不存在"
            }
        
        item_data = item.data[0]
        
        if item_data["user_id"] != user_id:
            return {
                "code": 403,
                "data": None,
                "message": "无权操作此条目"
            }
        
        delete_knowledge_vectors(item_id)
        
        result = await vectorize_knowledge_item(
            item_id=item_id,
            content=item_data.get("content", ""),
            source_resource=item_data.get("name", "unknown")
        )
        
        return {
            "code": 200,
            "data": result,
            "message": "向量化完成" if result["success"] else f"向量化失败: {result.get('error')}"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 向量化失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"向量化失败: {str(e)}"
        }


@router.get("/knowledge/status/{item_id}")
async def get_status(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取向量化状态
    """
    try:
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
        logger.error(f"[ERR] 获取状态失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"获取失败: {str(e)}"
        }


@router.post("/knowledge/repair-vectorize")
async def repair_vectorize_all(
    user_id: str = Depends(get_current_user)
):
    """
    批量修复所有未向量化的知识库条目
    
    处理范围：
    - vector_status 为 pending（待处理）
    - vector_status 为 NULL（从未处理）
    - vector_status 为 failed（之前失败）
    
    用于修复历史数据或恢复向量化
    """
    try:
        logger.info(f"[REPAIR] 用户 {user_id} 请求批量修复向量化")
        
        result = await batch_vectorize_pending_items(user_id=user_id)
        
        logger.info(f"[REPAIR] 批量修复完成: 总计{result.get('total', 0)}, 成功{result.get('success', 0)}, 失败{result.get('failed', 0)}")
        
        return {
            "code": 200,
            "data": result,
            "message": f"修复完成: 成功 {result.get('success', 0)} 条, 失败 {result.get('failed', 0)} 条"
        }
        
    except Exception as e:
        logger.error(f"[ERR] 批量修复失败: {e}")
        return {
            "code": 500,
            "data": None,
            "message": f"修复失败: {str(e)}"
        }
