"""
知识库数据导入脚本 - 支持预设数据初始化
支持：本地文件导入、预设数据导入、批量向量化
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import uuid
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
from service.rag_vector_service import vectorize_knowledge_item
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KnowledgeImporter:
    """知识库导入器"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.user_id = None
    
    def get_or_create_system_user(self) -> str:
        """获取或创建系统用户"""
        try:
            res = self.supabase.table("users").select("id").eq("email", "system@teacher.local").execute()
            
            if res.data:
                logger.info(f"[OK] 使用现有系统用户: {res.data[0]['id']}")
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
    
    def import_from_file(self, file_path: str, name: str = None, grade: str = None, subject: str = None) -> str:
        """从本地文件导入知识库条目"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                raise ValueError(f"文件为空: {file_path}")
            
            file_size = file_path.stat().st_size
            
            item_name = name or file_path.stem
            item_data = {
                "user_id": self.user_id,
                "name": item_name,
                "type": "txt",
                "size": f"{file_size / 1024:.2f} KB",
                "content": content,
                "tags": [grade or "未分类", subject or "通用"],
                "grade_level": grade,
                "subject": subject,
                "visibility": "public",
                "vector_status": "pending"
            }
            
            res = self.supabase.table("knowledge_items").insert(item_data).execute()
            item_id = res.data[0]['id']
            
            logger.info(f"[OK] 导入成功: {item_name} (ID: {item_id})")
            return item_id
            
        except Exception as e:
            logger.error(f"[ERR] 导入文件失败: {e}")
            raise
    
    def import_preset_data(self) -> List[str]:
        """导入预设知识库数据"""
        preset_file = Path(__file__).parent.parent / "data" / "preset_knowledge.json"
        
        if not preset_file.exists():
            logger.error(f"[ERR] 预设数据文件不存在: {preset_file}")
            return []
        
        with open(preset_file, 'r', encoding='utf-8') as f:
            preset_data = json.load(f)
        
        logger.info(f"[INFO] 发现 {len(preset_data)} 条预设数据")
        
        imported_ids = []
        for data in preset_data:
            try:
                existing = self.supabase.table("knowledge_items").select("id").eq("name", data["name"]).execute()
                
                if existing.data:
                    logger.info(f"[SKIP] 已存在: {data['name']}")
                    continue
                
                item_data = {
                    "user_id": self.user_id,
                    "name": data["name"],
                    "type": "txt",
                    "size": f"{len(data['content']) / 1024:.2f} KB",
                    "content": data["content"],
                    "tags": [data.get("grade_level", "通用"), data.get("subject", "通用")],
                    "grade_level": data.get("grade_level"),
                    "subject": data.get("subject"),
                    "visibility": data.get("visibility", "public"),
                    "education_level": data.get("education_level"),
                    "resource_type": data.get("resource_type"),
                    "difficulty": data.get("difficulty"),
                    "semester": data.get("semester"),
                    "chapter": data.get("chapter"),
                    "vector_status": "pending"
                }
                
                res = self.supabase.table("knowledge_items").insert(item_data).execute()
                item_id = res.data[0]['id']
                imported_ids.append(item_id)
                logger.info(f"[OK] 导入预设数据: {data['name']} (ID: {item_id})")
                
            except Exception as e:
                logger.error(f"[ERR] 导入预设数据失败: {data['name']} - {e}")
        
        return imported_ids
    
    async def vectorize_all_pending(self) -> Dict[str, Any]:
        """对所有待向量化的条目进行向量化处理"""
        try:
            res = self.supabase.table("knowledge_items").select(
                "id, name, content"
            ).eq("vector_status", "pending").execute()
            
            items = res.data
            logger.info(f"[INFO] 发现 {len(items)} 个待处理条目")
            
            stats = {
                "total": len(items),
                "success": 0,
                "failed": 0,
                "details": []
            }
            
            for idx, item in enumerate(items, 1):
                try:
                    logger.info(f"[{idx}/{len(items)}] 处理: {item['name']}...")
                    
                    result = await vectorize_knowledge_item(
                        item_id=item["id"],
                        content=item.get("content", ""),
                        source_resource=item.get("name", "unknown")
                    )
                    
                    if result["success"]:
                        stats["success"] += 1
                        logger.info(f"[OK] 完成: {item['name']} ({result['chunk_count']} 块)")
                        stats["details"].append({
                            "name": item["name"],
                            "status": "success",
                            "chunk_count": result["chunk_count"]
                        })
                    else:
                        stats["failed"] += 1
                        logger.error(f"[ERR] 失败: {item['name']} - {result.get('error')}")
                        stats["details"].append({
                            "name": item["name"],
                            "status": "failed",
                            "error": result.get("error")
                        })
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"[ERR] 异常: {item['name']} - {e}")
                    stats["details"].append({
                        "name": item["name"],
                        "status": "error",
                        "error": str(e)
                    })
            
            logger.info(f"\n[统计] 处理完成:")
            logger.info(f"   总数: {stats['total']}")
            logger.info(f"   成功: {stats['success']}")
            logger.info(f"   失败: {stats['failed']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"[ERR] 批量向量化异常: {e}")
            return {"total": 0, "success": 0, "failed": 0, "error": str(e)}


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库数据导入工具")
    parser.add_argument("--mode", choices=["preset", "file", "vectorize", "all"], 
                       default="all", help="导入模式: preset(预设数据), file(单文件), vectorize(向量化), all(全部)")
    parser.add_argument("--file", type=str, help="文件路径（file模式时必需）")
    parser.add_argument("--name", type=str, help="资源名称")
    parser.add_argument("--grade", type=str, help="年级")
    parser.add_argument("--subject", type=str, help="学科")
    
    args = parser.parse_args()
    
    importer = KnowledgeImporter()
    
    importer.user_id = importer.get_or_create_system_user()
    
    try:
        if args.mode in ["preset", "all"]:
            logger.info("[START] 开始导入预设数据...")
            importer.import_preset_data()
        
        if args.mode == "file":
            if not args.file:
                logger.error("[ERR] file模式需要指定--file参数")
                return
            logger.info(f"[START] 开始导入文件: {args.file}")
            importer.import_from_file(args.file, args.name, args.grade, args.subject)
        
        if args.mode in ["vectorize", "all"]:
            logger.info("[START] 开始向量化处理...")
            await importer.vectorize_all_pending()
        
        logger.info("[DONE] 所有操作完成！")
        
    except Exception as e:
        logger.error(f"[ERR] 导入失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
