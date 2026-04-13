"""
批量文件上传脚本 - 支持上传大量文件到知识库
支持：PDF、PPTX、DOCX、TXT 格式
"""

import asyncio
import sys
import os
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client, get_supabase_with_retry
from service.storage_service import (
    upload_knowledge_file,
    get_mime_type,
    delete_file,
    KNOWLEDGE_BUCKET
)
from service.robust_vector_service import vectorize_knowledge_item_robust

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

SUPPORTED_EXTENSIONS = ['.pdf', '.pptx', '.docx', '.txt']


def sanitize_filename(filename: str) -> str:
    """
    将文件名转换为Storage安全格式（只保留字母、数字、下划线、连字符、点）
    """
    if not filename:
        return f"file_{uuid.uuid4().hex[:8]}.bin"
    
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


def sanitize_storage_path(path: str) -> str:
    """
    清理存储路径中的非法字符
    """
    if not path:
        return path
    
    parts = path.split('/')
    safe_parts = []
    for part in parts:
        if part:
            safe_part = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', part)
            safe_part = re.sub(r'_+', '_', safe_part)
            safe_part = safe_part.strip('_')
            if safe_part:
                safe_parts.append(safe_part)
    
    return '/'.join(safe_parts)


def clean_content(content: str) -> str:
    """
    彻底清理文本内容中的无效字符
    - 移除 \u0000 空字符
    - 移除所有 ASCII 控制字符（保留换行、回车、制表符）
    - 移除其他无效 Unicode 字符
    """
    if not content:
        return ""
    
    result = []
    for char in content:
        code = ord(char)
        
        if code == 0:
            continue
        
        if code < 32:
            if char in '\n\r\t':
                result.append(char)
            continue
        
        if code == 127:
            continue
        
        if 128 <= code <= 159:
            continue
        
        if code == 0xFFFE or code == 0xFFFF:
            continue
        
        result.append(char)
    
    cleaned = ''.join(result)
    
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    
    cleaned = cleaned.replace('\ufffe', '').replace('\uffff', '')
    
    return cleaned.strip()


EDUCATION_LEVEL_MAP = {
    'senior_high': 'senior_high',
    'high_school': 'senior_high',
    '高中': 'senior_high',
    'university': 'university',
    '大学': 'university',
    'college': 'university',
    'junior_high': 'junior_high',
    '初中': 'junior_high',
    'primary': 'primary',
    '小学': 'primary',
    'exam': 'exam',
    '考试': 'exam',
}

SUBJECT_MAP = {
    'math': '数学',
    '数学': '数学',
    'physics': '物理',
    '物理': '物理',
    'chemistry': '化学',
    '化学': '化学',
    'biology': '生物',
    '生物': '生物',
    'chinese': '语文',
    '语文': '语文',
    'english': '英语',
    '英语': '英语',
    'history': '历史',
    '历史': '历史',
    'geography': '地理',
    '地理': '地理',
    'politics': '政治',
    '政治': '政治',
    'computer': '计算机',
    '计算机': '计算机',
}


class BatchUploader:
    """批量文件上传器"""
    
    def __init__(self):
        self.supabase = get_supabase_with_retry(max_retries=3)
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }
    
    def ensure_system_user(self) -> str:
        """确保系统用户存在"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                res = self.supabase.table("users").select("id").eq("id", SYSTEM_USER_ID).execute()
                if res.data:
                    return SYSTEM_USER_ID
                
                user_data = {
                    "id": SYSTEM_USER_ID,
                    "email": "system@preset-knowledge.local",
                    "username": "系统预设知识库",
                    "hashed_password": "system_preset_user",
                    "role": "admin"
                }
                self.supabase.table("users").insert(user_data).execute()
                return SYSTEM_USER_ID
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"[RETRY] 创建系统用户失败，重试 ({attempt + 1}/{max_retries}): {e}")
                    import time
                    time.sleep(2)
                else:
                    logger.error(f"[ERR] 创建系统用户失败: {e}")
                    raise
    
    def check_file_exists(self, file_name: str) -> bool:
        """检查文件是否已上传"""
        try:
            res = self.supabase.table("knowledge_items").select("id").eq(
                "file_original_name", file_name
            ).eq("visibility", "public").execute()
            return len(res.data) > 0
        except:
            return False
    
    def parse_metadata_from_path(self, file_path: Path) -> Dict[str, Any]:
        """从文件路径解析元数据"""
        metadata = {
            "visibility": "public",
            "education_level": None,
            "grade_level": None,
            "subject": None,
        }
        
        parts = file_path.parts
        
        for part in parts:
            part_lower = part.lower()
            
            if part_lower in EDUCATION_LEVEL_MAP:
                metadata["education_level"] = EDUCATION_LEVEL_MAP[part_lower]
            
            if part_lower in SUBJECT_MAP:
                metadata["subject"] = SUBJECT_MAP[part_lower]
            
            if '高一' in part or '高二' in part or '高三' in part:
                grade = part[part.find('高'):part.find('高')+2]
                metadata["grade_level"] = grade
            elif '大一' in part or '大二' in part or '大三' in part or '大四' in part:
                grade = part[part.find('大'):part.find('大')+2]
                metadata["grade_level"] = grade
        
        return metadata
    
    def parse_document_content(self, file_path: Path, file_type: str) -> tuple:
        """解析文档内容"""
        try:
            if file_type == 'txt':
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                return content, 1
            
            from service.rag_vector_service import parse_document_content
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            return parse_document_content(file_bytes, file_type, file_path.name)
            
        except Exception as e:
            logger.error(f"[ERR] 解析文档失败: {file_path} - {e}")
            return None, 0
    
    async def upload_single_file(
        self,
        file_path: Path,
        metadata: Dict[str, Any] = None,
        skip_existing: bool = True
    ) -> Optional[str]:
        """上传单个文件"""
        try:
            file_ext = file_path.suffix.lower()
            if file_ext not in SUPPORTED_EXTENSIONS:
                logger.warning(f"[SKIP] 不支持的格式: {file_path}")
                self.stats["skipped"] += 1
                return None
            
            file_name = file_path.name
            
            if skip_existing and self.check_file_exists(file_name):
                logger.info(f"[SKIP] 已存在: {file_name}")
                self.stats["skipped"] += 1
                return None
            
            self.stats["total"] += 1
            
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            
            file_type = file_ext[1:]
            content, page_count = self.parse_document_content(file_path, file_type)
            
            content = clean_content(content)
            
            if not content or len(content.strip()) < 10:
                logger.warning(f"[SKIP] 内容为空: {file_name}")
                self.stats["skipped"] += 1
                return None
            
            safe_file_name = sanitize_filename(file_name)
            mime_type = get_mime_type(file_type)
            
            storage_result = upload_knowledge_file(
                user_id=SYSTEM_USER_ID,
                file_name=safe_file_name,
                file_data=file_bytes,
                mime_type=mime_type
            )
            
            if storage_result:
                storage_result["path"] = sanitize_storage_path(storage_result.get("path", ""))
            else:
                logger.warning(f"[WARN] Storage上传失败，仅保存文本: {file_name}")
            
            file_size_kb = len(file_bytes) / 1024
            size_str = f"{file_size_kb:.2f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
            
            resource_name = clean_content(file_path.stem)
            
            parsed_meta = self.parse_metadata_from_path(file_path)
            if metadata:
                parsed_meta.update(metadata)
            
            insert_data = {
                "user_id": SYSTEM_USER_ID,
                "name": resource_name,
                "type": file_type,
                "size": size_str,
                "tags": [],
                "content": content,
                "visibility": parsed_meta.get("visibility", "public"),
                "grade_level": parsed_meta.get("grade_level"),
                "subject": parsed_meta.get("subject"),
                "education_level": parsed_meta.get("education_level"),
                "file_original_name": file_name,
                "file_path": storage_result["path"] if storage_result else None,
                "file_bucket": storage_result["bucket"] if storage_result else None,
                "file_size_bytes": len(file_bytes),
                "file_mime_type": mime_type,
                "has_original_file": storage_result is not None,
                "vector_status": "pending"
            }
            
            result = self.supabase.table("knowledge_items").insert(insert_data).execute()
            
            if not result.data:
                if storage_result:
                    delete_file(storage_result["path"], bucket=KNOWLEDGE_BUCKET)
                logger.error(f"[ERR] 插入数据库失败: {file_name}")
                self.stats["failed"] += 1
                return None
            
            item = result.data[0]
            item_id = item["id"]
            
            logger.info(f"[OK] 上传成功: {file_name} -> {item_id[:8]}...")
            self.stats["success"] += 1
            
            return item_id
            
        except Exception as e:
            logger.error(f"[ERR] 上传失败: {file_path} - {e}")
            self.stats["failed"] += 1
            self.stats["details"].append({
                "file": str(file_path),
                "error": str(e)
            })
            return None
    
    async def upload_directory(
        self,
        dir_path: Path,
        recursive: bool = True,
        skip_existing: bool = True
    ) -> List[str]:
        """批量上传目录中的文件"""
        uploaded_ids = []
        
        if not dir_path.exists():
            logger.error(f"[ERR] 目录不存在: {dir_path}")
            return uploaded_ids
        
        files = []
        if recursive:
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(dir_path.rglob(f"*{ext}"))
        else:
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(dir_path.glob(f"*{ext}"))
        
        logger.info(f"[INFO] 发现 {len(files)} 个文件待上传")
        
        for idx, file_path in enumerate(files, 1):
            logger.info(f"[{idx}/{len(files)}] 处理: {file_path.name}")
            
            item_id = await self.upload_single_file(
                file_path,
                skip_existing=skip_existing
            )
            
            if item_id:
                uploaded_ids.append(item_id)
            
            await asyncio.sleep(0.1)
        
        return uploaded_ids
    
    async def vectorize_uploaded(self, item_ids: List[str] = None, include_failed: bool = False):
        """向量化已上传的文件"""
        if item_ids:
            items_to_vectorize = item_ids
        else:
            query = self.supabase.table("knowledge_items").select(
                "id, name, content"
            ).eq("vector_status", "pending").eq("visibility", "public")
            
            items_to_vectorize = [item["id"] for item in query.execute().data]
            
            if include_failed:
                failed_query = self.supabase.table("knowledge_items").select(
                    "id, name, content"
                ).eq("vector_status", "failed").eq("visibility", "public")
                items_to_vectorize.extend([item["id"] for item in failed_query.execute().data])
        
        if not items_to_vectorize:
            logger.info("[INFO] 没有待向量化的条目")
            return
        
        logger.info(f"[INFO] 开始向量化 {len(items_to_vectorize)} 个条目")
        
        for idx, item_id in enumerate(items_to_vectorize, 1):
            try:
                res = self.supabase.table("knowledge_items").select(
                    "id, name, content"
                ).eq("id", item_id).execute()
                
                if not res.data:
                    continue
                
                item = res.data[0]
                logger.info(f"[{idx}/{len(items_to_vectorize)}] 向量化: {item['name']}")
                
                cleaned_content = clean_content(item.get("content", ""))
                
                result = await vectorize_knowledge_item_robust(
                    item_id=item["id"],
                    content=cleaned_content,
                    source_resource=clean_content(item.get("name", "unknown"))
                )
                
                if result["success"]:
                    logger.info(f"[OK] 完成: {item['name']} ({result['chunk_count']} 块) [后端: {result.get('backend_used', 'unknown')}]")
                else:
                    logger.error(f"[ERR] 失败: {item['name']} - {result.get('error', 'unknown')}")
                
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"[ERR] 向量化异常: {item_id} - {e}")
    
    def print_stats(self):
        """打印统计信息"""
        logger.info("=" * 50)
        logger.info("上传统计:")
        logger.info(f"  总文件数: {self.stats['total']}")
        logger.info(f"  成功: {self.stats['success']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  失败: {self.stats['failed']}")
        logger.info("=" * 50)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="批量文件上传工具")
    parser.add_argument("--dir", type=str, help="上传目录路径")
    parser.add_argument("--file", type=str, help="上传单个文件")
    parser.add_argument("--no-recursive", action="store_true", help="不递归子目录")
    parser.add_argument("--no-skip", action="store_true", help="不跳过已存在的文件")
    parser.add_argument("--vectorize", action="store_true", help="上传后自动向量化")
    parser.add_argument("--vectorize-only", action="store_true", help="仅向量化待处理条目")
    parser.add_argument("--retry-failed", action="store_true", help="重试失败的向量化条目")
    parser.add_argument("--health", action="store_true", help="检查向量化服务健康状态")
    
    args = parser.parse_args()
    
    uploader = BatchUploader()
    uploader.ensure_system_user()
    
    if args.health:
        from service.robust_vector_service import get_robust_vectorization_service
        service = get_robust_vectorization_service()
        health = service.get_health_status()
        logger.info("=" * 50)
        logger.info("向量化服务健康状态:")
        logger.info(f"  嵌入后端: {health['embedding']['backend']}")
        logger.info(f"  模型名称: {health['embedding']['model_name']}")
        logger.info(f"  就绪状态: {health['embedding']['is_ready']}")
        logger.info(f"  处理统计: {health['stats']}")
        logger.info("=" * 50)
        return
    
    if args.vectorize_only:
        await uploader.vectorize_uploaded(include_failed=args.retry_failed)
        return
    
    uploaded_ids = []
    
    if args.file:
        file_path = Path(args.file)
        item_id = await uploader.upload_single_file(
            file_path,
            skip_existing=not args.no_skip
        )
        if item_id:
            uploaded_ids.append(item_id)
    
    elif args.dir:
        dir_path = Path(args.dir)
        uploaded_ids = await uploader.upload_directory(
            dir_path,
            recursive=not args.no_recursive,
            skip_existing=not args.no_skip
        )
    
    else:
        default_dir = Path(__file__).parent.parent / "data" / "batch_upload"
        if default_dir.exists():
            logger.info(f"[INFO] 使用默认目录: {default_dir}")
            uploaded_ids = await uploader.upload_directory(default_dir)
        else:
            parser.print_help()
            return
    
    uploader.print_stats()
    
    if args.vectorize and uploaded_ids:
        await uploader.vectorize_uploaded(uploaded_ids)


if __name__ == "__main__":
    asyncio.run(main())
