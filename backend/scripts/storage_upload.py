"""
直接上传文件到 Supabase Storage
不涉及数据库操作，仅上传文件
"""

import sys
from pathlib import Path
from typing import List, Optional
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
from service.storage_service import get_mime_type

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = ['.pdf', '.pptx', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.mp4', '.mp3']


def upload_to_storage(
    bucket: str,
    local_path: str,
    storage_path: str = None,
    public: bool = False
) -> Optional[str]:
    """
    上传单个文件到 Storage
    
    Args:
        bucket: 桶名称 (teaching-resources, ppt-templates, coursewares)
        local_path: 本地文件路径
        storage_path: 存储路径 (不含文件名)，默认为根目录
        public: 是否公开
    
    Returns:
        存储路径或 None
    """
    try:
        file_path = Path(local_path)
        
        if not file_path.exists():
            logger.error(f"[ERR] 文件不存在: {local_path}")
            return None
        
        file_ext = file_path.suffix.lower()
        if file_ext not in SUPPORTED_EXTENSIONS:
            logger.warning(f"[SKIP] 不支持的格式: {file_ext}")
            return None
        
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        
        mime_type = get_mime_type(file_ext[1:]) if file_ext[1:] in ['pdf', 'pptx', 'docx', 'txt'] else 'application/octet-stream'
        
        if storage_path:
            dest_path = f"{storage_path}/{file_path.name}"
        else:
            dest_path = file_path.name
        
        supabase = get_supabase_client()
        
        res = supabase.storage.from_(bucket).upload(
            dest_path,
            file_bytes,
            file_options={
                "content-type": mime_type,
                "upsert": "true"
            }
        )
        
        if res:
            logger.info(f"[OK] 上传成功: {local_path} -> {bucket}/{dest_path}")
            
            if public:
                try:
                    supabase.storage.from_(bucket).update(dest_path, {"public": True})
                except:
                    pass
            
            return dest_path
        else:
            logger.error(f"[ERR] 上传失败: {local_path}")
            return None
            
    except Exception as e:
        logger.error(f"[ERR] 上传异常: {local_path} - {e}")
        return None


def upload_directory(
    bucket: str,
    local_dir: str,
    storage_prefix: str = "",
    recursive: bool = True
) -> List[str]:
    """
    批量上传目录到 Storage
    
    Args:
        bucket: 桶名称
        local_dir: 本地目录
        storage_prefix: 存储路径前缀
        recursive: 是否递归子目录
    
    Returns:
        成功上传的路径列表
    """
    dir_path = Path(local_dir)
    
    if not dir_path.exists():
        logger.error(f"[ERR] 目录不存在: {local_dir}")
        return []
    
    files = []
    if recursive:
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(dir_path.rglob(f"*{ext}"))
    else:
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(dir_path.glob(f"*{ext}"))
    
    logger.info(f"[INFO] 发现 {len(files)} 个文件")
    
    uploaded = []
    for idx, file_path in enumerate(files, 1):
        rel_path = file_path.relative_to(dir_path)
        
        if storage_prefix:
            dest_path = f"{storage_prefix}/{rel_path.parent}" if rel_path.parent != Path('.') else storage_prefix
        else:
            dest_path = str(rel_path.parent) if rel_path.parent != Path('.') else None
        
        logger.info(f"[{idx}/{len(files)}] {file_path.name}")
        
        result = upload_to_storage(
            bucket=bucket,
            local_path=str(file_path),
            storage_path=dest_path
        )
        
        if result:
            uploaded.append(result)
    
    logger.info(f"[完成] 成功上传 {len(uploaded)}/{len(files)} 个文件")
    return uploaded


def list_bucket_files(bucket: str, folder: str = "") -> List[dict]:
    """列出桶中的文件"""
    try:
        supabase = get_supabase_client()
        res = supabase.storage.from_(bucket).list(path=folder)
        return res
    except Exception as e:
        logger.error(f"[ERR] 列出文件失败: {e}")
        return []


def delete_storage_file(bucket: str, path: str) -> bool:
    """删除 Storage 中的文件"""
    try:
        supabase = get_supabase_client()
        supabase.storage.from_(bucket).remove([path])
        logger.info(f"[OK] 删除成功: {bucket}/{path}")
        return True
    except Exception as e:
        logger.error(f"[ERR] 删除失败: {e}")
        return False


def get_public_url(bucket: str, path: str) -> Optional[str]:
    """获取公开 URL"""
    try:
        supabase = get_supabase_client()
        return supabase.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        logger.error(f"[ERR] 获取URL失败: {e}")
        return None


def get_signed_url(bucket: str, path: str, expires_in: int = 3600) -> Optional[str]:
    """获取签名 URL（私有文件）"""
    try:
        supabase = get_supabase_client()
        res = supabase.storage.from_(bucket).create_signed_url(path, expires_in)
        return res.get("signedURL")
    except Exception as e:
        logger.error(f"[ERR] 获取签名URL失败: {e}")
        return None


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="直接上传文件到 Supabase Storage")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    upload_parser = subparsers.add_parser("upload", help="上传文件")
    upload_parser.add_argument("bucket", help="桶名称 (teaching-resources/ppt-templates/coursewares)")
    upload_parser.add_argument("path", help="本地文件或目录路径")
    upload_parser.add_argument("--dest", help="存储目标路径")
    upload_parser.add_argument("--recursive", "-r", action="store_true", help="递归上传目录")
    upload_parser.add_argument("--public", action="store_true", help="设为公开")
    
    list_parser = subparsers.add_parser("list", help="列出文件")
    list_parser.add_argument("bucket", help="桶名称")
    list_parser.add_argument("--folder", default="", help="文件夹路径")
    
    delete_parser = subparsers.add_parser("delete", help="删除文件")
    delete_parser.add_argument("bucket", help="桶名称")
    delete_parser.add_argument("path", help="文件路径")
    
    url_parser = subparsers.add_parser("url", help="获取文件URL")
    url_parser.add_argument("bucket", help="桶名称")
    url_parser.add_argument("path", help="文件路径")
    url_parser.add_argument("--signed", action="store_true", help="获取签名URL")
    
    args = parser.parse_args()
    
    if args.command == "upload":
        path = Path(args.path)
        
        if path.is_file():
            upload_to_storage(
                bucket=args.bucket,
                local_path=args.path,
                storage_path=args.dest,
                public=args.public
            )
        elif path.is_dir():
            upload_directory(
                bucket=args.bucket,
                local_dir=args.path,
                storage_prefix=args.dest or "",
                recursive=args.recursive
            )
        else:
            logger.error(f"[ERR] 路径不存在: {args.path}")
    
    elif args.command == "list":
        files = list_bucket_files(args.bucket, args.folder)
        for f in files:
            print(f"  {f.get('name', '')} ({f.get('metadata', {}).get('size', 0)} bytes)")
    
    elif args.command == "delete":
        delete_storage_file(args.bucket, args.path)
    
    elif args.command == "url":
        if args.signed:
            url = get_signed_url(args.bucket, args.path)
        else:
            url = get_public_url(args.bucket, args.path)
        print(f"URL: {url}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
