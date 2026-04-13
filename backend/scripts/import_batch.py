"""
知识库批量导入脚本 - 支持大规模文档导入
特性：
- 扫描目录批量导入
- 支持多种文件格式（TXT, PDF, DOCX, MD）
- 自动解析文件名提取分类信息
- 并行向量化处理
- 进度显示和错误日志
"""

import asyncio
import sys
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
import aiofiles

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
from service.rag_vector_service import vectorize_knowledge_item, parse_document_content
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('import_batch.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


SUPPORTED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.doc', '.pptx'}

GRADE_PATTERNS = {
    r'高一|高中一': '高一',
    r'高二|高中二': '高二',
    r'高三|高中三': '高三',
    r'大一|大学一': '大一',
    r'大二|大学二': '大二',
    r'大三|大学三': '大三',
    r'大四|大学四': '大四',
    r'研究生|硕士|博士': '研究生',
    r'高中通用|高中': '高中通用',
    r'大学通用|大学': '大学通用',
}

SUBJECT_PATTERNS = {
    r'数学|高数|微积分|线性代数': '数学',
    r'物理|力学|电磁学|光学': '物理',
    r'化学|有机化学|无机化学': '化学',
    r'生物|生物学': '生物',
    r'英语|English': '英语',
    r'语文|文学': '语文',
    r'历史': '历史',
    r'地理': '地理',
    r'政治': '政治',
    r'计算机|编程|Python|Java|算法|数据结构': '计算机科学',
    r'电子|电路|信号': '电子信息',
    r'机械': '机械工程',
    r'经济|管理|金融|会计': '经济管理',
    r'法学|法律': '法学',
    r'教育': '教育学',
    r'医学': '医学',
    r'艺术|设计': '艺术设计',
}


class BatchImporter:
    """批量知识库导入器"""
    
    def __init__(self, max_workers: int = 5):
        self.supabase = get_supabase_client()
        self.user_id = None
        self.max_workers = max_workers
        self.stats = {
            "total_files": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
    
    def get_or_create_system_user(self) -> str:
        """获取或创建系统用户"""
        try:
            res = self.supabase.table("users").select("id").eq("email", "system@teacher.local").execute()
            
            if res.data:
                return res.data[0]['id']
            
            system_user_id = str(uuid.uuid4())
            user_data = {
                "id": system_user_id,
                "email": "system@teacher.local",
                "username": "system",
                "hashed_password": "system_user",
                "role": "admin"
            }
            res = self.supabase.table("users").insert(user_data).execute()
            logger.info(f"[OK] 创建系统用户: {system_user_id}")
            return system_user_id
            
        except Exception as e:
            logger.error(f"[ERR] 获取/创建系统用户失败: {e}")
            raise
    
    def parse_filename(self, filename: str) -> Dict[str, Optional[str]]:
        """从文件名解析年级和学科"""
        result = {"grade_level": None, "subject": None}
        
        for pattern, grade in GRADE_PATTERNS.items():
            if re.search(pattern, filename, re.IGNORECASE):
                result["grade_level"] = grade
                break
        
        for pattern, subject in SUBJECT_PATTERNS.items():
            if re.search(pattern, filename, re.IGNORECASE):
                result["subject"] = subject
                break
        
        return result
    
    def scan_directory(self, directory: str, recursive: bool = True) -> List[Path]:
        """扫描目录获取所有支持的文件"""
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")
        
        files = []
        pattern = '**/*' if recursive else '*'
        
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(directory.glob(f"{pattern}{ext}"))
        
        logger.info(f"[INFO] 扫描到 {len(files)} 个文件")
        return sorted(files)
    
    def read_file_content(self, file_path: Path) -> tuple:
        """读取文件内容"""
        ext = file_path.suffix.lower()
        
        try:
            if ext in {'.txt', '.md'}:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content, ext[1:], 1
            
            elif ext in {'.pdf', '.docx', '.doc', '.pptx'}:
                with open(file_path, 'rb') as f:
                    file_bytes = f.read()
                content, page_count = parse_document_content(file_bytes, ext[1:], str(file_path))
                return content, ext[1:], page_count
            
            else:
                return None, None, 0
                
        except Exception as e:
            logger.error(f"[ERR] 读取文件失败 {file_path}: {e}")
            return None, None, 0
    
    def check_exists(self, name: str) -> bool:
        """检查知识库条目是否已存在"""
        try:
            res = self.supabase.table("knowledge_items").select("id").eq("name", name).execute()
            return bool(res.data)
        except:
            return False
    
    def import_single_file(
        self, 
        file_path: Path, 
        grade_level: str = None, 
        subject: str = None,
        visibility: str = "public",
        education_level: str = None,
        resource_type: str = None,
        difficulty: str = None,
        semester: str = None,
        chapter: str = None,
        skip_existing: bool = True
    ) -> Optional[str]:
        """导入单个文件"""
        try:
            name = file_path.stem
            
            if skip_existing and self.check_exists(name):
                logger.info(f"[SKIP] 已存在: {name}")
                self.stats["skipped"] += 1
                return None
            
            content, file_type, page_count = self.read_file_content(file_path)
            
            if not content or len(content.strip()) < 10:
                logger.warning(f"[WARN] 内容为空或过短: {file_path}")
                self.stats["failed"] += 1
                return None
            
            parsed = self.parse_filename(name)
            final_grade = grade_level or parsed["grade_level"]
            final_subject = subject or parsed["subject"]
            
            item_data = {
                "user_id": self.user_id,
                "name": name,
                "type": file_type,
                "size": f"{file_path.stat().st_size / 1024:.2f} KB",
                "content": content,
                "tags": [final_grade or "未分类", final_subject or "通用"],
                "grade_level": final_grade,
                "subject": final_subject,
                "visibility": visibility,
                "education_level": education_level,
                "resource_type": resource_type,
                "difficulty": difficulty,
                "semester": semester,
                "chapter": chapter,
                "vector_status": "pending"
            }
            
            res = self.supabase.table("knowledge_items").insert(item_data).execute()
            item_id = res.data[0]['id']
            
            logger.info(f"[OK] 导入成功: {name} ({final_grade or '未知年级'}/{final_subject or '未知学科'})")
            self.stats["success"] += 1
            return item_id
            
        except Exception as e:
            logger.error(f"[ERR] 导入失败 {file_path}: {e}")
            self.stats["failed"] += 1
            self.stats["errors"].append({"file": str(file_path), "error": str(e)})
            return None
    
    async def vectorize_item(self, item_id: str, name: str, content: str) -> bool:
        """向量化单个条目"""
        try:
            result = await vectorize_knowledge_item(
                item_id=item_id,
                content=content,
                source_resource=name
            )
            
            if result["success"]:
                logger.info(f"[OK] 向量化完成: {name} ({result['chunk_count']} 块)")
                return True
            else:
                logger.error(f"[ERR] 向量化失败: {name} - {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"[ERR] 向量化异常: {name} - {e}")
            return False
    
    async def batch_vectorize(self, batch_size: int = 10) -> Dict:
        """批量向量化待处理条目"""
        try:
            res = self.supabase.table("knowledge_items").select(
                "id, name, content"
            ).eq("vector_status", "pending").execute()
            
            items = res.data
            total = len(items)
            
            if total == 0:
                logger.info("[INFO] 没有待向量化的条目")
                return {"total": 0, "success": 0, "failed": 0}
            
            logger.info(f"[INFO] 开始向量化 {total} 个条目...")
            
            success_count = 0
            failed_count = 0
            
            for i in range(0, total, batch_size):
                batch = items[i:i + batch_size]
                
                tasks = [
                    self.vectorize_item(item["id"], item["name"], item.get("content", ""))
                    for item in batch
                ]
                
                results = await asyncio.gather(*tasks)
                
                success_count += sum(results)
                failed_count += len(results) - sum(results)
                
                logger.info(f"[进度] {min(i + batch_size, total)}/{total} 已处理")
                
                await asyncio.sleep(0.5)
            
            return {
                "total": total,
                "success": success_count,
                "failed": failed_count
            }
            
        except Exception as e:
            logger.error(f"[ERR] 批量向量化异常: {e}")
            return {"total": 0, "success": 0, "failed": 0, "error": str(e)}
    
    def import_from_directory(
        self,
        directory: str,
        recursive: bool = True,
        grade_level: str = None,
        subject: str = None,
        visibility: str = "public",
        education_level: str = None,
        resource_type: str = None,
        difficulty: str = None,
        semester: str = None,
        chapter: str = None,
        skip_existing: bool = True,
        max_files: int = None
    ) -> Dict:
        """从目录批量导入"""
        files = self.scan_directory(directory, recursive)
        
        if max_files:
            files = files[:max_files]
        
        self.stats["total_files"] = len(files)
        imported_ids = []
        
        logger.info(f"[START] 开始导入 {len(files)} 个文件...")
        
        for idx, file_path in enumerate(files, 1):
            logger.info(f"[{idx}/{len(files)}] 处理: {file_path.name}")
            
            item_id = self.import_single_file(
                file_path,
                grade_level=grade_level,
                subject=subject,
                visibility=visibility,
                education_level=education_level,
                resource_type=resource_type,
                difficulty=difficulty,
                semester=semester,
                chapter=chapter,
                skip_existing=skip_existing
            )
            
            if item_id:
                imported_ids.append(item_id)
        
        logger.info(f"\n[统计]")
        logger.info(f"  总文件数: {self.stats['total_files']}")
        logger.info(f"  导入成功: {self.stats['success']}")
        logger.info(f"  导入失败: {self.stats['failed']}")
        logger.info(f"  已跳过: {self.stats['skipped']}")
        
        return {
            "imported_ids": imported_ids,
            "stats": self.stats
        }


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库批量导入工具")
    parser.add_argument("--dir", type=str, help="要导入的目录路径")
    parser.add_argument("--file", type=str, help="单个文件路径")
    parser.add_argument("--recursive", action="store_true", default=True, help="递归扫描子目录")
    parser.add_argument("--grade", type=str, help="指定年级（覆盖自动检测）")
    parser.add_argument("--subject", type=str, help="指定学科（覆盖自动检测）")
    parser.add_argument("--visibility", type=str, default="public", choices=["private", "public"], help="可见性")
    parser.add_argument("--education-level", type=str, help="教育阶段")
    parser.add_argument("--resource-type", type=str, help="资源类型")
    parser.add_argument("--difficulty", type=str, help="难度")
    parser.add_argument("--semester", type=str, help="学期")
    parser.add_argument("--chapter", type=str, help="章节")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="跳过已存在的条目")
    parser.add_argument("--max-files", type=int, help="最大导入文件数")
    parser.add_argument("--mode", choices=["import", "vectorize", "all"], default="all", help="运行模式")
    parser.add_argument("--batch-size", type=int, default=10, help="向量化批处理大小")
    
    args = parser.parse_args()
    
    importer = BatchImporter()
    importer.user_id = importer.get_or_create_system_user()
    
    try:
        if args.mode in ["import", "all"]:
            if args.file:
                importer.stats["total_files"] = 1
                importer.import_single_file(
                    Path(args.file),
                    grade_level=args.grade,
                    subject=args.subject,
                    visibility=args.visibility,
                    education_level=args.education_level,
                    resource_type=args.resource_type,
                    difficulty=args.difficulty,
                    semester=args.semester,
                    chapter=args.chapter,
                    skip_existing=args.skip_existing
                )
            elif args.dir:
                importer.import_from_directory(
                    args.dir,
                    recursive=args.recursive,
                    grade_level=args.grade,
                    subject=args.subject,
                    visibility=args.visibility,
                    education_level=args.education_level,
                    resource_type=args.resource_type,
                    difficulty=args.difficulty,
                    semester=args.semester,
                    chapter=args.chapter,
                    skip_existing=args.skip_existing,
                    max_files=args.max_files
                )
            else:
                logger.error("[ERR] 请指定 --dir 或 --file 参数")
                return
        
        if args.mode in ["vectorize", "all"]:
            logger.info("\n[START] 开始批量向量化...")
            vector_stats = await importer.batch_vectorize(batch_size=args.batch_size)
            logger.info(f"[向量化统计] 成功: {vector_stats['success']}, 失败: {vector_stats['failed']}")
        
        logger.info("\n[DONE] 所有操作完成！")
        
    except Exception as e:
        logger.error(f"[ERR] 导入失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
