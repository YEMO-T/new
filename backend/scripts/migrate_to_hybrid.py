"""
数据迁移脚本 - 为现有知识库补充存储信息
注意: 此脚本仅更新数据库字段，无法恢复原始文件
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_existing_items():
    """
    为现有知识库条目补充存储信息
    注意: 原始文件无法恢复，仅更新标记字段
    """
    supabase = get_supabase_client()
    
    logger.info("[INFO] 开始迁移现有知识库数据...")
    
    res = supabase.table("knowledge_items").select(
        "id, name, type, content, file_original_name"
    ).is_("file_path", "null").execute()
    
    items = res.data
    logger.info(f"[INFO] 发现 {len(items)} 个需要迁移的条目")
    
    success_count = 0
    failed_count = 0
    
    for idx, item in enumerate(items, 1):
        try:
            content = item.get("content", "")
            file_size = len(content.encode('utf-8')) if content else 0
            
            supabase.table("knowledge_items").update({
                "has_original_file": False,
                "file_size_bytes": file_size
            }).eq("id", item["id"]).execute()
            
            success_count += 1
            logger.info(f"[{idx}/{len(items)}] 迁移完成: {item['name']}")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"[{idx}/{len(items)}] 迁移失败: {item['name']} - {e}")
    
    logger.info(f"[DONE] 迁移完成: 成功 {success_count}, 失败 {failed_count}")
    
    return {
        "total": len(items),
        "success": success_count,
        "failed": failed_count
    }


async def verify_migration():
    """
    验证迁移结果
    """
    supabase = get_supabase_client()
    
    logger.info("[INFO] 验证迁移结果...")
    
    total_res = supabase.table("knowledge_items").select("id", count="exact").execute()
    total_count = total_res.count if hasattr(total_res, 'count') else len(total_res.data)
    
    migrated_res = supabase.table("knowledge_items").select("id", count="exact").not_.is_("file_path", "null").execute()
    migrated_count = migrated_res.count if hasattr(migrated_res, 'count') else len(migrated_res.data)
    
    no_file_res = supabase.table("knowledge_items").select("id", count="exact").eq("has_original_file", False).execute()
    no_file_count = no_file_res.count if hasattr(no_file_res, 'count') else len(no_file_res.data)
    
    logger.info(f"[RESULT] 总条目: {total_count}")
    logger.info(f"[RESULT] 有原始文件: {migrated_count}")
    logger.info(f"[RESULT] 无原始文件: {no_file_count}")
    
    return {
        "total": total_count,
        "with_file": migrated_count,
        "without_file": no_file_count
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库数据迁移脚本")
    parser.add_argument("--verify", action="store_true", help="仅验证迁移结果")
    args = parser.parse_args()
    
    if args.verify:
        asyncio.run(verify_migration())
    else:
        asyncio.run(migrate_existing_items())
