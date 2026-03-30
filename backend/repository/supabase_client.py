from supabase import create_client, Client
from core.config import settings

def get_supabase_client() -> Client:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    if not url or not key:
        raise ValueError("Supabase URL and Key must be provided")
    return create_client(url, key)

def trim_messages(user_id: str, limit: int = 60):
    """
    自动清理陈旧消息，仅保留最新的指定条数（默认 60 条/30 轮）
    """
    try:
        supabase = get_supabase_client()
        # 1. 查出该用户所有消息的 ID，按时间倒序
        res = supabase.table("messages") \
            .select("id") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()
        
        all_ids = [item["id"] for item in res.data]
        if len(all_ids) > limit:
            # 2. 识别出需要删除的旧消息 ID (超出 limit 部分)
            ids_to_delete = all_ids[limit:]
            # 3. 执行物理删除
            supabase.table("messages").delete().in_("id", ids_to_delete).execute()
            print(f"Trimmed {len(ids_to_delete)} old messages for user {user_id}")
    except Exception as e:
        print(f"Failed to trim messages: {e}")

def insert_message(user_id: str, role: str, content: str, msg_type: str = "text", file_info: dict = None):
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "role": role,
            "content": content,
            "type": msg_type,
            "file_info": file_info
        }
        res = supabase.table("messages").insert(data).execute()
        
        # 成功插入后，执行数据库容量修剪，确保“至多保存 30 轮”
        trim_messages(user_id)
        
        return res.data
    except Exception as e:
        print(f"Failed to insert message: {e}")
        return None

def get_messages(user_id: str, limit: int = 60):
    """
    获取最新的对话记录（默认 60 条，即 30 轮对话）
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("messages") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        # 数据库返回的是倒序（最新的在最前），反转为正序（时间轴向后延伸）返回给前端
        messages = res.data
        if messages:
            messages.reverse()
        return messages
    except Exception as e:
        print(f"Failed to get messages: {e}")
        return []

def clear_chat_history(user_id: str):
    """
    清空指定用户的所有对话记录
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("messages").delete().eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print(f"Failed to clear chat history: {e}")
        return None

def insert_courseware(
    user_id: str, 
    title: str, 
    slides: list, 
    lesson_plan: dict = None, 
    interaction: dict = None,
    template_id: str = None,
    template_info: dict = None,
    file_url: str = None
):
    """
    插入课件数据，包含下载链接
    """
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "title": title,
            "slides": slides,
            "lesson_plan": lesson_plan,
            "interaction": interaction,
            "template_id": template_id,
            "template_info": template_info,
            "file_url": file_url # 保存云端链接
        }
        res = supabase.table("coursewares").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert courseware: {e}")
        return None

def upload_courseware_to_storage(user_id: str, file_name: str, file_data: bytes):
    """
    上传 PPT 文件到 Supabase Storage
    """
    try:
        supabase = get_supabase_client()
        bucket_name = "coursewares"
        # 路径规则: user_id/timestamp_filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user_id}/{timestamp}_{file_name}"
        
        # 执行上传
        res = supabase.storage.from_(bucket_name).upload(
            storage_path, 
            file_data,
            {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
        )
        
        # 获取公共 URL (假设 bucket 已设为 public)
        # 如果不是 public，则需要 get_public_url
        url_res = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        
        return {
            "url": url_res,
            "path": storage_path
        }
    except Exception as e:
        print(f"Failed to upload to storage: {e}")
        return None


def get_user_by_email(email: str) -> dict | None:
    """
    按邮箱查询用户，用于登录校验和注册唯一性检查
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("users").select("*").eq("email", email).limit(1).execute()
        data = res.data
        return data[0] if data else None
    except Exception as e:
        print(f"Error querying user by email: {e}")
        return None


def create_user(email: str, username: str, hashed_password: str, role: str = "teacher") -> dict | None:
    """
    创建新用户记录，存储 bcrypt 哈希后的密码
    """
    try:
        supabase = get_supabase_client()
        data = {
            "email": email,
            "username": username,
            "hashed_password": hashed_password,
            "role": role
        }
        res = supabase.table("users").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Error creating user in Supabase: {e}")
        return None

def get_templates():
    try:
        supabase = get_supabase_client()
        res = supabase.table("templates").select("*").order("usage_count", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get templates: {e}")
        return []

def get_exports(user_id: str):
    try:
        supabase = get_supabase_client()
        res = supabase.table("exports").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get exports: {e}")
        return []

def insert_export(user_id: str, title: str, fmt: str, size: str, file_url: str = None):
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "title": title,
            "format": fmt,
            "size": size,
            "file_url": file_url
        }
        res = supabase.table("exports").insert(data).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert export: {e}")
        return None

def delete_export(export_id: str, user_id: str):
    """
    删除指定的导出记录
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("exports") \
            .delete() \
            .eq("id", export_id) \
            .eq("user_id", user_id) \
            .execute()
        return res.data
    except Exception as e:
        print(f"Failed to delete export: {e}")
        return None

def get_knowledge_items(user_id: str):
    try:
        supabase = get_supabase_client()
        # 按用户隔离知识库：只返回当前用户的资料
        res = (
            supabase.table("knowledge_items")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"Failed to get knowledge items: {e}")
        return []

def insert_knowledge_item(user_id: str, name: str, item_type: str, size: str, tags: list = None, content: str = None):
    try:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "name": name,
            "type": item_type,
            "size": size,
            "content": content,
            "tags": tags or ["未分类"]
        }
        res = supabase.table("knowledge_items").insert(data).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert knowledge item: {e}")
        return None

def delete_knowledge_item(item_id: str, user_id: str):
    """
    物理删除知识库条目，仅限所属用户执行
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("knowledge_items") \
            .delete() \
            .eq("id", item_id) \
            .eq("user_id", user_id) \
            .execute()
        return res.data
    except Exception as e:
        print(f"Failed to delete knowledge item: {e}")
        return None

def update_knowledge_item(
    item_id: str,
    user_id: str,
    name: str | None = None,
    item_type: str | None = None,
    size: str | None = None,
    tags: list | None = None,
    content: str | None = None,
):
    """
    更新知识库条目，仅限所属用户。
    """
    try:
        supabase = get_supabase_client()
        update_data = {"name": name, "type": item_type, "size": size, "tags": tags, "content": content}
        # 移除 None 字段，避免覆盖为 null
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            return None

        res = (
            supabase.table("knowledge_items")
            .update(update_data)
            .eq("id", item_id)
            .eq("user_id", user_id)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"Failed to update knowledge item: {e}")
        return None


# ============================================================
# RAG向量检索相关函数
# ============================================================

def get_knowledge_vectors(limit: int = 100, offset: int = 0):
    """
    获取知识向量列表
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("knowledge_vectors").select(
            "id, chunk_text, source_resource, page_number, vector_embedding, knowledge_item_id"
        ).range(offset, offset + limit - 1).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get knowledge vectors: {e}")
        return []


def insert_knowledge_vectors(vectors: list):
    """
    批量插入知识向量
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("knowledge_vectors").insert(vectors).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert knowledge vectors: {e}")
        return None


def get_teaching_resources(grade: str | None = None, subject: str | None = None, limit: int = 20):
    """
    获取公共教学资源
    """
    try:
        supabase = get_supabase_client()
        query = supabase.table("teaching_resources").select("*").eq("is_public", True)
        
        if grade:
            query = query.eq("grade_level", grade)
        if subject:
            query = query.eq("subject", subject)
        
        res = query.order("created_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get teaching resources: {e}")
        return []


def insert_teaching_resource(
    resource_name: str,
    grade_level: str,
    subject: str,
    resource_type: str,
    storage_path: str | None = None,
    download_url: str | None = None,
    is_public: bool = True,
    created_by: str | None = None,
    preview_url: str | None = None,
    description: str | None = None
):
    """
    插入教学资源
    """
    try:
        supabase = get_supabase_client()
        data = {
            "resource_name": resource_name,
            "grade_level": grade_level,
            "subject": subject,
            "resource_type": resource_type,
            "storage_path": storage_path,
            "download_url": download_url,
            "is_public": is_public,
            "created_by": created_by,
            "preview_url": preview_url,
            "description": description
        }
        res = supabase.table("teaching_resources").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert teaching resource: {e}")
        return None


def get_curriculum_standards(grade: str, subject: str):
    """
    获取课标
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("curriculum_standards").select("*").eq("grade", grade).eq("subject", subject).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get curriculum standards: {e}")
        return []


def insert_curriculum_standard(
    grade: str,
    subject: str,
    standard_code: str,
    standard_content: str,
    key_points: list | None = None,
    vector_embedding: list | None = None
):
    """
    插入课标
    """
    try:
        supabase = get_supabase_client()
        data = {
            "grade": grade,
            "subject": subject,
            "standard_code": standard_code,
            "standard_content": standard_content,
            "key_points": key_points,
            "vector_embedding": vector_embedding
        }
        res = supabase.table("curriculum_standards").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert curriculum standard: {e}")
        return None


def get_vectorization_logs(item_id: str, limit: int = 10):
    """
    获取向量化处理日志
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("vectorization_logs").select("*").eq("knowledge_item_id", item_id).order("processed_at", desc=True).limit(limit).execute()
        return res.data
    except Exception as e:
        print(f"Failed to get vectorization logs: {e}")
        return []


def insert_vectorization_log(
    knowledge_item_id: str,
    status: str,
    chunk_count: int | None = None,
    error_message: str | None = None
):
    """
    插入向量化处理日志
    """
    try:
        supabase = get_supabase_client()
        data = {
            "knowledge_item_id": knowledge_item_id,
            "status": status,
            "chunk_count": chunk_count,
            "error_message": error_message
        }
        res = supabase.table("vectorization_logs").insert(data).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert vectorization log: {e}")
        return None
