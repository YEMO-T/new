import time
import logging
import threading
import os
from typing import Any, Callable, Optional, TypeVar

from supabase import create_client, Client
from core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')

_supabase_client: Optional[Client] = None
_client_lock = threading.Lock()
_client_created_time: float = 0.0
CLIENT_REFRESH_INTERVAL: float = 120.0

os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'


def _reset_supabase_client() -> None:
    global _supabase_client, _client_created_time
    with _client_lock:
        if _supabase_client is not None:
            try:
                del _supabase_client
            except Exception:
                pass
        _supabase_client = None
        _client_created_time = 0.0
        logger.info("[Supabase] 客户端已重置")


def get_supabase_client() -> Client:
    global _supabase_client, _client_created_time
    with _client_lock:
        current_time = time.time()
        if _supabase_client is not None and (current_time - _client_created_time) > CLIENT_REFRESH_INTERVAL:
            logger.info("[Supabase] 客户端已过期，重新创建")
            try:
                del _supabase_client
            except Exception:
                pass
            _supabase_client = None
            _client_created_time = 0.0

        if _supabase_client is None:
            url = settings.SUPABASE_URL
            key = settings.SUPABASE_KEY
            if not url or not key:
                raise ValueError("Supabase URL 和 Key 必须配置")

            try:
                _supabase_client = create_client(url, key)
                _client_created_time = current_time
                logger.info("[Supabase] 客户端创建成功")
            except Exception as e:
                logger.error(f"[Supabase] 创建客户端失败: {e}")
                raise

        return _supabase_client


def is_connection_error(error: Exception) -> bool:
    error_str = str(error)
    error_type_name = type(error).__name__
    return any(
        pattern in error_str or pattern in error_type_name
        for pattern in [
            '10054', '10060', '10061', '10064',
            'ConnectionReset', 'ConnectionRefused',
            'ConnectError', 'ConnectTimeout',
            'Timeout', 'timed out',
            '远程主机强迫关闭', '远程主机',
            'SSL', 'TLS', 'handshake',
            'EOF', 'Broken pipe',
            'Connection aborted',
            'Remote end closed',
            'Network is unreachable',
            'No connection',
            'socket',
        ]
    )


def execute_with_retry(
    operation: Callable[[Client], T],
    max_retries: int = 6,
    base_delay: float = 2.0,
    operation_name: str = "query",
) -> T:
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                _reset_supabase_client()
                time.sleep(min(base_delay * (1.8 ** (attempt - 1)), 15.0))

            client = get_supabase_client()
            result = operation(client)
            return result
        except Exception as exc:
            last_error = exc
            conn_err = is_connection_error(exc)
            if attempt < max_retries - 1:
                if conn_err:
                    wait = min(base_delay * (2.0 ** attempt), 12.0)
                    logger.warning(
                        "[RETRY] %s 连接异常 (%d/%d)，%.1fs 后重试 | %s",
                        operation_name,
                        attempt + 1,
                        max_retries,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                else:
                    logger.warning(
                        "[RETRY] %s 失败 (%d/%d) | %s",
                        operation_name,
                        attempt + 1,
                        max_retries,
                        exc,
                    )
                    time.sleep(base_delay * 0.5)
            else:
                logger.error(
                    "[ERROR] %s 最终失败（%d 次尝试）| %s",
                    operation_name,
                    max_retries,
                    exc,
                )

    raise last_error


def trim_messages(user_id: str, limit: int = 60):
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("messages")
            .select("id")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        all_ids = [item["id"] for item in res.data]
        if len(all_ids) > limit:
            ids_to_delete = all_ids[limit:]
            supabase.table("messages").delete().in_("id", ids_to_delete).execute()
            print(f"Trimmed {len(ids_to_delete)} old messages for user {user_id}")
    except Exception as e:
        print(f"Failed to trim messages: {e}")


def insert_message(user_id: str, role: str, content: str, msg_type: str = "text", file_info: dict = None):
    try:
        supabase = get_supabase_client()
        data = {"user_id": user_id, "role": role, "content": content, "type": msg_type, "file_info": file_info}
        res = supabase.table("messages").insert(data).execute()
        trim_messages(user_id)
        return res.data
    except Exception as e:
        print(f"Failed to insert message: {e}")
        return None


def get_messages(user_id: str, limit: int = 60):
    def _query(client):
        res = (
            client.table("messages")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        messages = res.data
        if messages:
            messages.reverse()
        return messages

    try:
        return execute_with_retry(_query, operation_name="get_messages")
    except Exception as e:
        logger.error("Failed to get messages: %s", e)
        return []


def clear_chat_history(user_id: str):
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
    file_url: str = None,
):
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
            "file_url": file_url,
        }
        res = supabase.table("coursewares").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert courseware: {e}")
        return None


def upload_courseware_to_storage(user_id: str, file_name: str, file_data: bytes):
    import os
    from datetime import datetime

    try:
        supabase = get_supabase_client()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user_id}/{timestamp}_{file_name}"
        content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        preferred_buckets = ["coursewares", "ppt-templates", "teaching-resources"]
        for bucket_name in preferred_buckets:
            try:
                buckets = supabase.storage.list_buckets()
                bucket_names = [b.get("name") for b in buckets]
                if bucket_name not in bucket_names:
                    try:
                        supabase.storage.create_bucket(id=bucket_name, name=bucket_name, options={"public": True})
                        print(f"[Storage] 已创建 Bucket: {bucket_name}")
                    except Exception as create_err:
                        print(f"[Storage] 创建 Bucket {bucket_name} 失败: {create_err}")
                        continue
                res = supabase.storage.from_(bucket_name).upload(storage_path, file_data, {"content-type": content_type})
                url_res = supabase.storage.from_(bucket_name).get_public_url(storage_path)
                print(f"[Storage] 上传成功: bucket={bucket_name}, path={storage_path}")
                return {"url": url_res, "path": storage_path, "bucket": bucket_name}
            except Exception as bucket_err:
                print(f"[Storage] Bucket {bucket_name} 上传失败: {bucket_err}")
                continue
        print("[Storage] 所有云端存储桶上传失败，使用本地存储")
        return _save_to_local_storage(user_id, file_name, file_data)
    except Exception as e:
        print(f"[Storage] 上传失败: {e}")
        return _save_to_local_storage(user_id, file_name, file_data)


def _save_to_local_storage(user_id: str, file_name: str, file_data: bytes) -> dict:
    import os
    from datetime import datetime

    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_dir = os.path.join(base_dir, "data", "coursewares", user_id)
        os.makedirs(local_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_path = os.path.join(local_dir, f"{timestamp}_{file_name}")
        with open(local_path, "wb") as f:
            f.write(file_data)
        print(f"[Storage] 文件已保存到本地: {local_path}")
        return {
            "url": f"/local/coursewares/{user_id}/{timestamp}_{file_name}",
            "path": local_path,
            "bucket": "local",
            "local_path": local_path,
        }
    except Exception as e:
        print(f"[Storage] 本地存储失败: {e}")
        return None


def get_user_by_email(email: str) -> dict | None:
    def _query(client):
        res = client.table("users").select("*").eq("email", email).limit(1).execute()
        data = res.data
        return data[0] if data else None

    try:
        return execute_with_retry(_query, operation_name="get_user_by_email")
    except Exception as e:
        logger.error("Error querying user by email: %s", e)
        return None


def create_user(email: str, username: str, hashed_password: str, role: str = "teacher") -> dict | None:
    def _insert(client):
        data = {"email": email, "username": username, "hashed_password": hashed_password, "role": role}
        res = client.table("users").insert(data).execute()
        return res.data[0] if res.data else None

    try:
        return execute_with_retry(_insert, operation_name="create_user")
    except Exception as e:
        logger.error("Error creating user in Supabase: %s", e)
        return None


def get_templates():
    def _query(client):
        res = client.table("templates").select("*").order("usage_count", desc=True).execute()
        return res.data

    try:
        return execute_with_retry(_query, operation_name="get_templates")
    except Exception as e:
        logger.error("Failed to get templates: %s", e)
        return []


def get_exports(user_id: str):
    def _query(client):
        res = client.table("exports").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return res.data

    try:
        return execute_with_retry(_query, operation_name="get_exports")
    except Exception as e:
        logger.error("Failed to get exports: %s", e)
        return []


def insert_export(user_id: str, title: str, fmt: str, size: str, file_url: str = None):
    def _insert(client):
        data = {"user_id": user_id, "title": title, "format": fmt, "size": size, "file_url": file_url}
        res = client.table("exports").insert(data).execute()
        return res.data

    try:
        return execute_with_retry(_insert, operation_name="insert_export")
    except Exception as e:
        logger.error("Failed to insert export: %s", e)
        return None


def delete_export(export_id: str, user_id: str):
    def _delete(client):
        res = client.table("exports").delete().eq("id", export_id).eq("user_id", user_id).execute()
        return res.data

    try:
        return execute_with_retry(_delete, operation_name="delete_export")
    except Exception as e:
        logger.error("Failed to delete export: %s", e)
        return None


def get_knowledge_items(user_id: str):
    def _query(client):
        res = (
            client.table("knowledge_items")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data

    try:
        return execute_with_retry(_query, operation_name="get_knowledge_items")
    except Exception as e:
        logger.error("Failed to get knowledge items: %s", e)
        return []


def insert_knowledge_item(user_id: str, name: str, item_type: str, size: str, tags: list = None, content: str = None):
    try:
        supabase = get_supabase_client()
        data = {"user_id": user_id, "name": name, "type": item_type, "size": size, "content": content, "tags": tags or ["未分类"]}
        res = supabase.table("knowledge_items").insert(data).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert knowledge item: {e}")
        return None


def delete_knowledge_item(item_id: str, user_id: str):
    try:
        supabase = get_supabase_client()
        res = supabase.table("knowledge_items").delete().eq("id", item_id).eq("user_id", user_id).execute()
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
    try:
        supabase = get_supabase_client()
        update_data = {"name": name, "type": item_type, "size": size, "tags": tags, "content": content}
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if not update_data:
            return None
        res = supabase.table("knowledge_items").update(update_data).eq("id", item_id).eq("user_id", user_id).execute()
        return res.data
    except Exception as e:
        print(f"Failed to update knowledge item: {e}")
        return None


def get_knowledge_vectors(limit: int = 100, offset: int = 0):
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("knowledge_vectors")
            .select("id, chunk_text, source_resource, page_number, vector_embedding, knowledge_item_id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return res.data
    except Exception as e:
        print(f"Failed to get knowledge vectors: {e}")
        return []


def insert_knowledge_vectors(vectors: list):
    try:
        supabase = get_supabase_client()
        res = supabase.table("knowledge_vectors").insert(vectors).execute()
        return res.data
    except Exception as e:
        print(f"Failed to insert knowledge vectors: {e}")
        return None


def get_teaching_resources(grade: str | None = None, subject: str | None = None, limit: int = 20):
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
    description: str | None = None,
):
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
            "description": description,
        }
        res = supabase.table("teaching_resources").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert teaching resource: {e}")
        return None


def get_curriculum_standards(grade: str, subject: str):
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
    vector_embedding: list | None = None,
):
    try:
        supabase = get_supabase_client()
        data = {
            "grade": grade,
            "subject": subject,
            "standard_code": standard_code,
            "standard_content": standard_content,
            "key_points": key_points,
            "vector_embedding": vector_embedding,
        }
        res = supabase.table("curriculum_standards").insert(data).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"Failed to insert curriculum standard: {e}")
        return None


def upload_ppt_to_public_bucket(user_id: str, file_name: str, file_data: bytes) -> dict | None:
    """
    统一的 PPT 上传到 Supabase 公开桶函数
    直接上传到 coursewares 桶的 public_ppts 目录，返回公开下载 URL
    
    如果云端上传失败，自动回退到本地存储
    """
    from datetime import datetime

    # 首先尝试上传到 Supabase 云端存储
    try:
        supabase = get_supabase_client()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"public_ppts/{user_id}/{timestamp}_{file_name}"
        content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        bucket_name = "coursewares"
        
        res = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        
        url_res = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        
        if url_res and not url_res.startswith('http'):
            from core.config import settings
            base_url = settings.SUPABASE_URL.rstrip('/')
            url_res = f"{base_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
        
        logger.info(f"[Storage] PPT 上传成功: bucket={bucket_name}, path={storage_path}")
        return {
            "url": url_res,
            "path": storage_path,
            "bucket": bucket_name,
            "success": True
        }
            
    except Exception as e:
        logger.warning(f"[Storage] PPT 云端上传失败: {e}，回退到本地存储")
    
    # 回退到本地存储
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_dir = os.path.join(base_dir, 'data', 'coursewares', user_id)
        os.makedirs(local_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_file_name = f"{timestamp}_{file_name}"
        local_path = os.path.join(local_dir, local_file_name)
        
        with open(local_path, 'wb') as f:
            f.write(file_data)
        
        # 构建本地访问URL（通过API提供下载）
        local_url = f"/local/coursewares/{user_id}/{local_file_name}"
        
        logger.info(f"[Storage] PPT 已保存到本地: {local_path} ({len(file_data)/1024:.1f} KB)")
        return {
            "url": local_url,
            "path": local_path,
            "bucket": "local",
            "success": True,
            "is_local": True
        }
        
    except Exception as local_err:
        logger.error(f"[Storage] 本地存储也失败: {local_err}")
        return None
