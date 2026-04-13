"""
预设知识库导入脚本 - 支持高中/大学分类
支持：批量导入、自动分类、向量化处理
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid
import logging
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
from core.config import settings

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"

EDUCATION_LEVELS = {
    "senior_high": "高中",
    "university": "大学",
    "junior_high": "初中",
    "primary": "小学",
    "exam": "考试",
    "vocational": "职业教育",
    "general": "通用"
}

RESOURCE_TYPES = {
    "textbook": "教材",
    "curriculum": "课标",
    "question_bank": "题库",
    "notes": "笔记",
    "exam_paper": "试卷",
    "other": "其他"
}

DIFFICULTY_LEVELS = {
    "basic": "基础",
    "intermediate": "中等",
    "advanced": "进阶",
    "exam": "考试"
}


class PresetKnowledgeImporter:
    """预设知识库导入器"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.data_dir = Path(__file__).parent.parent / "data" / "preset_knowledge"
        self.stats = {
            "total": 0,
            "success": 0,
            "skipped": 0,
            "failed": 0,
            "details": []
        }
    
    def ensure_system_user(self) -> str:
        """确保系统用户存在"""
        try:
            res = self.supabase.table("users").select("id").eq("id", SYSTEM_USER_ID).execute()
            
            if res.data:
                logger.info(f"[OK] 系统用户已存在: {SYSTEM_USER_ID}")
                return SYSTEM_USER_ID
            
            user_data = {
                "id": SYSTEM_USER_ID,
                "email": "system@preset-knowledge.local",
                "username": "系统预设知识库",
                "hashed_password": "system_preset_user",
                "role": "admin"
            }
            self.supabase.table("users").insert(user_data).execute()
            logger.info(f"[OK] 创建系统用户: {SYSTEM_USER_ID}")
            return SYSTEM_USER_ID
            
        except Exception as e:
            logger.error(f"[ERR] 确保系统用户失败: {e}")
            raise
    
    def check_item_exists(self, name: str) -> bool:
        """检查条目是否已存在"""
        try:
            res = self.supabase.table("knowledge_items").select("id").eq("name", name).eq("visibility", "public").execute()
            return len(res.data) > 0
        except:
            return False
    
    def import_single_item(self, data: Dict[str, Any]) -> Optional[str]:
        """导入单个知识库条目"""
        try:
            name = data.get("name", "")
            if not name:
                logger.error("[ERR] 条目缺少name字段")
                return None
            
            if self.check_item_exists(name):
                logger.info(f"[SKIP] 已存在: {name}")
                self.stats["skipped"] += 1
                return None
            
            item_data = {
                "user_id": SYSTEM_USER_ID,
                "name": name,
                "type": data.get("type", "txt"),
                "size": f"{len(data.get('content', '')) / 1024:.2f} KB",
                "content": data.get("content", ""),
                "tags": data.get("tags", []),
                "visibility": "public",
                "vector_status": "pending",
                
                "education_level": data.get("education_level"),
                "grade_level": data.get("grade_level"),
                "subject": data.get("subject"),
                "semester": data.get("semester"),
                "chapter": data.get("chapter"),
                "resource_type": data.get("resource_type", "textbook"),
                "source": data.get("source"),
                "knowledge_points": data.get("knowledge_points", []),
                "difficulty": data.get("difficulty"),
                "description": data.get("description", "")
            }
            
            item_data = {k: v for k, v in item_data.items() if v is not None}
            
            res = self.supabase.table("knowledge_items").insert(item_data).execute()
            item_id = res.data[0]['id']
            
            logger.info(f"[OK] 导入成功: {name} (ID: {item_id[:8]}...)")
            self.stats["success"] += 1
            self.stats["details"].append({
                "name": name,
                "status": "success",
                "id": item_id
            })
            
            return item_id
            
        except Exception as e:
            logger.error(f"[ERR] 导入失败: {data.get('name', 'unknown')} - {e}")
            self.stats["failed"] += 1
            self.stats["details"].append({
                "name": data.get("name", "unknown"),
                "status": "failed",
                "error": str(e)
            })
            return None
    
    def import_from_json_file(self, file_path: Path) -> List[str]:
        """从JSON文件导入"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                items = data
            else:
                items = [data]
            
            imported_ids = []
            for item in items:
                self.stats["total"] += 1
                item_id = self.import_single_item(item)
                if item_id:
                    imported_ids.append(item_id)
            
            return imported_ids
            
        except Exception as e:
            logger.error(f"[ERR] 读取文件失败: {file_path} - {e}")
            return []
    
    def import_from_txt_file(self, file_path: Path, metadata: Dict[str, Any] = None) -> Optional[str]:
        """从TXT文件导入"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                logger.warning(f"[WARN] 文件为空: {file_path}")
                return None
            
            self.stats["total"] += 1
            
            name = metadata.get("name") if metadata else None
            if not name:
                name = file_path.stem
            
            data = {
                "name": name,
                "content": content,
                "type": "txt"
            }
            
            if metadata:
                data.update(metadata)
            
            return self.import_single_item(data)
            
        except Exception as e:
            logger.error(f"[ERR] 读取TXT文件失败: {file_path} - {e}")
            self.stats["failed"] += 1
            return None
    
    def import_from_directory(self, dir_path: Path) -> List[str]:
        """从目录批量导入"""
        imported_ids = []
        
        if not dir_path.exists():
            logger.warning(f"[WARN] 目录不存在: {dir_path}")
            return imported_ids
        
        json_files = list(dir_path.glob("**/*.json"))
        txt_files = list(dir_path.glob("**/*.txt"))
        
        logger.info(f"[INFO] 发现 {len(json_files)} 个JSON文件, {len(txt_files)} 个TXT文件")
        
        for json_file in json_files:
            ids = self.import_from_json_file(json_file)
            imported_ids.extend(ids)
        
        for txt_file in txt_files:
            rel_path = txt_file.relative_to(self.data_dir)
            parts = list(rel_path.parts[:-1])
            
            metadata = self._parse_metadata_from_path(parts)
            item_id = self.import_from_txt_file(txt_file, metadata)
            if item_id:
                imported_ids.append(item_id)
        
        return imported_ids
    
    def _parse_metadata_from_path(self, path_parts: List[str]) -> Dict[str, Any]:
        """从路径解析元数据"""
        metadata = {}
        
        if not path_parts:
            return metadata
        
        education_map = {
            "senior_high": "senior_high",
            "university": "university",
            "exam": "exam",
            "junior_high": "junior_high",
            "primary": "primary"
        }
        
        subject_map = {
            "chinese": "语文",
            "math": "数学",
            "english": "英语",
            "physics": "物理",
            "chemistry": "化学",
            "biology": "生物",
            "history": "历史",
            "geography": "地理",
            "politics": "政治",
            "mathematics": "数学",
            "computer": "计算机"
        }
        
        for part in path_parts:
            if part in education_map:
                metadata["education_level"] = education_map[part]
            elif part in subject_map:
                metadata["subject"] = subject_map[part]
            elif part.startswith("grade") or part in ["高一", "高二", "高三", "大一", "大二", "大三", "大四"]:
                metadata["grade_level"] = part
        
        return metadata
    
    def import_all_preset_data(self) -> Dict[str, Any]:
        """导入所有预设数据"""
        logger.info("=" * 60)
        logger.info("开始导入预设知识库数据")
        logger.info("=" * 60)
        
        self.ensure_system_user()
        
        if not self.data_dir.exists():
            logger.warning(f"[WARN] 预设数据目录不存在: {self.data_dir}")
            logger.info("[INFO] 将创建目录结构...")
            self._create_directory_structure()
        
        imported_ids = self.import_from_directory(self.data_dir)
        
        self._print_summary()
        
        return {
            "stats": self.stats,
            "imported_ids": imported_ids
        }
    
    def _create_directory_structure(self):
        """创建预设数据目录结构"""
        dirs = [
            "senior_high/chinese",
            "senior_high/math",
            "senior_high/english",
            "senior_high/physics",
            "senior_high/chemistry",
            "senior_high/biology",
            "senior_high/history",
            "senior_high/geography",
            "senior_high/politics",
            "university/mathematics",
            "university/english",
            "university/computer",
            "exam/gaokao",
            "exam/kaoyan",
            "exam/cet",
            "curriculum"
        ]
        
        for d in dirs:
            dir_path = self.data_dir / d
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[OK] 创建目录结构: {self.data_dir}")
    
    def _print_summary(self):
        """打印导入摘要"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("导入完成摘要")
        logger.info("=" * 60)
        logger.info(f"总条目数: {self.stats['total']}")
        logger.info(f"成功导入: {self.stats['success']}")
        logger.info(f"跳过已存在: {self.stats['skipped']}")
        logger.info(f"导入失败: {self.stats['failed']}")
        logger.info("=" * 60)
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        try:
            res = self.supabase.table("knowledge_items").select(
                "education_level, grade_level, subject, resource_type, vector_status"
            ).eq("visibility", "public").execute()
            
            items = res.data
            
            stats = {
                "total": len(items),
                "by_education": {},
                "by_subject": {},
                "by_status": {
                    "pending": 0,
                    "completed": 0,
                    "failed": 0
                }
            }
            
            for item in items:
                edu = item.get("education_level") or "unknown"
                subject = item.get("subject") or "unknown"
                status = item.get("vector_status") or "pending"
                
                stats["by_education"][edu] = stats["by_education"].get(edu, 0) + 1
                stats["by_subject"][subject] = stats["by_subject"].get(subject, 0) + 1
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"[ERR] 获取统计信息失败: {e}")
            return {}


async def vectorize_pending_items():
    """向量化待处理条目"""
    from service.rag_vector_service import vectorize_knowledge_item
    
    supabase = get_supabase_client()
    
    res = supabase.table("knowledge_items").select(
        "id, name, content"
    ).eq("vector_status", "pending").eq("visibility", "public").execute()
    
    items = res.data
    logger.info(f"[INFO] 发现 {len(items)} 个待向量化条目")
    
    for idx, item in enumerate(items, 1):
        try:
            logger.info(f"[{idx}/{len(items)}] 向量化: {item['name']}...")
            
            result = await vectorize_knowledge_item(
                item_id=item["id"],
                content=item.get("content", ""),
                source_resource=item.get("name", "unknown")
            )
            
            if result["success"]:
                logger.info(f"[OK] 完成: {item['name']} ({result['chunk_count']} 块)")
            else:
                logger.error(f"[ERR] 失败: {item['name']} - {result.get('error')}")
            
            await asyncio.sleep(0.3)
            
        except Exception as e:
            logger.error(f"[ERR] 异常: {item['name']} - {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="预设知识库导入工具")
    parser.add_argument("--import", action="store_true", help="导入预设数据")
    parser.add_argument("--vectorize", action="store_true", help="向量化待处理条目")
    parser.add_argument("--stats", action="store_true", help="查看知识库统计")
    parser.add_argument("--file", type=str, help="导入单个文件")
    parser.add_argument("--dir", type=str, help="导入指定目录")
    
    args = parser.parse_args()
    
    importer = PresetKnowledgeImporter()
    
    if args.stats:
        stats = importer.get_knowledge_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return
    
    if args.file:
        file_path = Path(args.file)
        if file_path.suffix == ".json":
            importer.import_from_json_file(file_path)
        else:
            importer.import_from_txt_file(file_path)
        return
    
    if args.dir:
        importer.import_from_directory(Path(args.dir))
        return
    
    if getattr(args, "import"):
        importer.import_all_preset_data()
        return
    
    if args.vectorize:
        asyncio.run(vectorize_pending_items())
        return
    
    importer.import_all_preset_data()


if __name__ == "__main__":
    main()
