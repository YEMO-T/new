"""
Supabase Storage 服务 - 处理文件上传/下载
支持知识库和模板文件
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import uuid
from repository.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

KNOWLEDGE_BUCKET = "teaching-resources"
TEMPLATE_BUCKET = "ppt-templates"

MIME_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg"
}


def sanitize_storage_filename(filename: str) -> str:
    """
    将文件名转换为 Storage 安全的格式（只保留字母、数字、下划线、连字符、点）
    """
    if not filename:
        return f"file_{uuid.uuid4().hex[:8]}.bin"
    
    from pathlib import Path
    name = Path(filename).stem
    ext = Path(filename).suffix.lower()
    
    if not ext:
        ext = ".bin"
    
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    safe_name = re.sub(r'_+', '_', safe_name)
    safe_name = safe_name.strip('_')
    
    if not safe_name:
        safe_name = f"file_{uuid.uuid4().hex[:8]}"
    
    return f"{safe_name}{ext}"


def ensure_bucket_exists(bucket_name: str) -> bool:
    """
    确保 Storage bucket 存在，不存在则尝试创建
    
    Args:
        bucket_name: bucket 名称
    
    Returns:
        bool: bucket 是否可用
    """
    try:
        supabase = get_supabase_client()

        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]  # ✅ 修复：使用 .name 属性

        if bucket_name in bucket_names:
            logger.info(f"[Storage] Bucket '{bucket_name}' 已存在")
            return True
        
        try:
            supabase.storage.create_bucket(
                id=bucket_name,
                name=bucket_name,
                options={"public": False}
            )
            logger.info(f"[Storage] 已创建 Bucket: {bucket_name}")
            return True
        except Exception as e:
            logger.warning(f"[Storage] 创建 Bucket 失败: {e}")
            return False
            
    except Exception as e:
        logger.error(f"[Storage] 检查 Bucket 失败: {e}")
        return False


def get_available_buckets() -> List[str]:
    """获取所有可用的 bucket 名称"""
    try:
        supabase = get_supabase_client()
        buckets = supabase.storage.list_buckets()
        return [b.name for b in buckets]  # ✅ 修复：使用 .name 属性
    except Exception as e:
        logger.error(f"[Storage] 获取 Bucket 列表失败: {e}")
        return []


def upload_knowledge_file(
    user_id: str,
    file_name: str,
    file_data: bytes,
    mime_type: str = "application/octet-stream"
) -> Optional[Dict[str, Any]]:
    """
    上传知识库原始文件到 Storage
    
    Args:
        user_id: 用户ID
        file_name: 原始文件名
        file_data: 文件二进制数据
        mime_type: MIME类型
    
    Returns:
        {"path": "xxx", "bucket": "xxx", "size": xxx} 或 None
    """
    try:
        supabase = get_supabase_client()
        
        safe_file_name = sanitize_storage_filename(file_name)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user_id}/{timestamp}_{safe_file_name}"
        
        res = supabase.storage.from_(KNOWLEDGE_BUCKET).upload(
            storage_path,
            file_data,
            {"content-type": mime_type}
        )
        
        logger.info(f"[OK] 文件上传成功: {storage_path}")
        
        return {
            "path": storage_path,
            "bucket": KNOWLEDGE_BUCKET,
            "size": len(file_data)
        }
        
    except Exception as e:
        logger.error(f"[ERR] 文件上传失败: {e}")
        return None


def upload_template_file(
    user_id: str,
    file_name: str,
    file_data: bytes,
    mime_type: str = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
) -> Optional[Dict[str, Any]]:
    """
    上传模板PPT文件到 Storage
    
    Args:
        user_id: 用户ID
        file_name: 原始文件名
        file_data: 文件二进制数据
        mime_type: MIME类型
    
    Returns:
        {"path": "xxx", "bucket": "xxx", "size": xxx} 或 None
    """
    try:
        supabase = get_supabase_client()
        
        safe_file_name = sanitize_storage_filename(file_name)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user_id}/{timestamp}_{safe_file_name}"
        
        available_buckets = get_available_buckets()
        logger.info(f"[Storage] 可用的 Buckets: {available_buckets}")
        
        target_bucket = TEMPLATE_BUCKET
        if target_bucket not in available_buckets:
            if not ensure_bucket_exists(target_bucket):
                for alt_bucket in ['coursewares', 'templates', 'teaching-resources']:
                    if alt_bucket in available_buckets:
                        target_bucket = alt_bucket
                        logger.info(f"[Storage] 使用备用 Bucket: {target_bucket}")
                        break
        
        try:
            res = supabase.storage.from_(target_bucket).upload(
                storage_path,
                file_data,
                {"content-type": mime_type}
            )
            logger.info(f"[OK] 模板文件上传成功: bucket={target_bucket}, path={storage_path}")
        except Exception as upload_err:
            logger.warning(f"[Storage] 上传到 {target_bucket} 失败: {upload_err}, 尝试其他 bucket...")
            for alt_bucket in available_buckets:
                if alt_bucket == target_bucket:
                    continue
                try:
                    res = supabase.storage.from_(alt_bucket).upload(
                        storage_path,
                        file_data,
                        {"content-type": mime_type}
                    )
                    target_bucket = alt_bucket
                    logger.info(f"[OK] 模板文件上传成功(备用): bucket={target_bucket}, path={storage_path}")
                    break
                except Exception as alt_err:
                    logger.debug(f"[Storage] 上传到 {alt_bucket} 失败: {alt_err}")
                    continue
            else:
                raise upload_err
        
        return {
            "path": storage_path,
            "bucket": target_bucket,
            "size": len(file_data)
        }
        
    except Exception as e:
        logger.error(f"[ERR] 模板文件上传失败: {e}")
        return None



def download_template_file(bucket_name: str, file_path: str) -> Optional[bytes]:
    """
    从 Storage 下载模板文件
    
    Args:
        bucket_name: 存储桶名称
        file_path: 文件在存储中的路径
    
    Returns:
        文件二进制数据，失败返回 None
    """
    try:
        supabase = get_supabase_client()
        
        file_data = supabase.storage.from_(bucket_name).download(file_path)
        
        logger.info(f"[Storage] 模板下载成功: bucket={bucket_name}, path={file_path}, size={len(file_data)} 字节")
        return file_data
        
    except Exception as e:
        logger.error(f"[ERR] 模板文件下载失败: bucket={bucket_name}, path={file_path}, error={e}")
        return None


def upload_template_thumbnail(
    user_id: str,
    template_id: str,
    thumbnail_data: bytes
) -> Optional[Dict[str, Any]]:
    """
    上传模板预览图到 Storage
    
    Args:
        user_id: 用户ID
        template_id: 模板ID
        thumbnail_data: 预览图二进制数据
    
    Returns:
        {"path": "xxx", "bucket": "xxx", "size": xxx} 或 None
    """
    try:
        supabase = get_supabase_client()
        
        storage_path = f"{user_id}/thumbnails/{template_id}.png"
        
        res = supabase.storage.from_(TEMPLATE_BUCKET).upload(
            storage_path,
            thumbnail_data,
            {"content-type": "image/png"}
        )
        
        logger.info(f"[OK] 预览图上传成功: {storage_path}")
        
        return {
            "path": storage_path,
            "bucket": TEMPLATE_BUCKET,
            "size": len(thumbnail_data)
        }
        
    except Exception as e:
        logger.error(f"[ERR] 预览图上传失败: {e}")
        return None


def get_file_public_url(storage_path: str, bucket: str = None) -> Optional[str]:
    """
    获取文件的公共URL (适用于公共资源)
    
    注意：此方法仅对公开桶有效。如果桶是私有的，需要使用 get_file_signed_url
    
    Args:
        storage_path: 存储路径
        bucket: 桶名称，默认为知识库桶
    
    Returns:
        公共URL或None
    """
    try:
        if not storage_path:
            return None
            
        supabase = get_supabase_client()
        bucket_name = bucket or KNOWLEDGE_BUCKET
        
        url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        
        if url and not url.startswith('http'):
            from core.config import settings
            base_url = settings.SUPABASE_URL.rstrip('/')
            url = f"{base_url}/storage/v1/object/public/{bucket_name}/{storage_path}"
        
        return url
    except Exception as e:
        logger.error(f"[ERR] 获取公共URL失败: {e}")
        return None


def get_file_signed_url(storage_path: str, expires_in: int = 3600, bucket: str = None) -> Optional[str]:
    """
    获取文件的签名URL (适用于私有资源)
    
    Args:
        storage_path: 存储路径
        expires_in: 过期时间(秒)，默认1小时
        bucket: 桶名称，默认为知识库桶
    
    Returns:
        签名URL或None
    """
    try:
        if not storage_path:
            return None
            
        supabase = get_supabase_client()
        bucket_name = bucket or KNOWLEDGE_BUCKET
        
        res = supabase.storage.from_(bucket_name).create_signed_url(
            storage_path,
            expires_in
        )
        
        signed_url = res.get("signedURL") if res else None
        
        if signed_url and not signed_url.startswith('http'):
            from core.config import settings
            base_url = settings.SUPABASE_URL.rstrip('/')
            signed_url = f"{base_url}/storage/v1/object/sign/{bucket_name}/{storage_path}?token={signed_url}"
        
        return signed_url
    except Exception as e:
        logger.error(f"[ERR] 获取签名URL失败: {e}")
        return None


def get_thumbnail_url(
    storage_path: str, 
    bucket: str = None, 
    use_signed: bool = False,
    expires_in: int = 3600
) -> Optional[str]:
    """
    获取缩略图URL（智能选择公开URL或签名URL）
    
    Args:
        storage_path: 存储路径
        bucket: 桶名称
        use_signed: 是否使用签名URL（私有桶需要）
        expires_in: 签名URL过期时间（秒）
    
    Returns:
        URL或None
    """
    if not storage_path:
        return None
    
    if use_signed:
        return get_file_signed_url(storage_path, expires_in, bucket)
    else:
        return get_file_public_url(storage_path, bucket)


def delete_file(storage_path: str, bucket: str = None) -> bool:
    """
    删除 Storage 中的文件
    
    Args:
        storage_path: 存储路径
        bucket: 桶名称，默认为知识库桶
    """
    try:
        supabase = get_supabase_client()
        bucket_name = bucket or KNOWLEDGE_BUCKET
        supabase.storage.from_(bucket_name).remove([storage_path])
        logger.info(f"[OK] 文件删除成功: {storage_path}")
        return True
    except Exception as e:
        logger.error(f"[ERR] 文件删除失败: {e}")
        return False


def check_file_exists(storage_path: str, bucket: str = None) -> bool:
    """
    检查文件是否存在
    
    Args:
        storage_path: 存储路径
        bucket: 桶名称，默认为知识库桶
    """
    try:
        supabase = get_supabase_client()
        bucket_name = bucket or KNOWLEDGE_BUCKET
        folder_path = "/".join(storage_path.split("/")[:-1])
        file_name = storage_path.split("/")[-1]
        
        res = supabase.storage.from_(bucket_name).list(path=folder_path)
        return any(f.get("name") == file_name for f in res)
    except Exception as e:
        logger.error(f"[ERR] 检查文件存在失败: {e}")
        return False


def get_mime_type(file_type: str) -> str:
    """
    根据文件扩展名获取 MIME 类型
    """
    return MIME_TYPES.get(file_type.lower(), "application/octet-stream")
