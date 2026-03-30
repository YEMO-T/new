"""
知识库数据导入脚本 - 快速喂入数据
支持：本地文件导入、示例数据导入、批量向量化
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import uuid
import logging

# 添加backend目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from repository.supabase_client import get_supabase_client
from service.vector_service import vectorize_knowledge_item
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KnowledgeImporter:
    """知识库导入器"""
    
    def __init__(self):
        self.supabase = get_supabase_client()
        self.user_id = None  # 将使用系统用户或指定用户
    
    def get_or_create_system_user(self) -> str:
        """获取或创建系统用户"""
        try:
            # 查询是否存在系统用户
            res = self.supabase.table("users").select("id").eq("email", "system@teacher.local").execute()
            
            if res.data:
                logger.info(f"✅ 使用现有系统用户: {res.data[0]['id']}")
                return res.data[0]['id']
            
            # 创建系统用户
            system_user_id = str(uuid.uuid4())
            user_data = {
                "id": system_user_id,
                "email": "system@teacher.local",
                "username": "system",
                "hashed_password": "system_user",
                "role": "admin"
            }
            res = self.supabase.table("users").insert(user_data).execute()
            logger.info(f"✅ 创建系统用户: {system_user_id}")
            return system_user_id
            
        except Exception as e:
            logger.error(f"❌ 获取/创建系统用户失败: {e}")
            raise
    
    def import_from_file(self, file_path: str, name: str = None, grade: str = None, subject: str = None) -> str:
        """
        从本地文件导入知识库条目
        
        Args:
            file_path: 文件路径 (.txt, .md, .pdf等)
            name: 资源名称（默认使用文件名）
            grade: 年级
            subject: 学科
        
        Returns:
            知识库条目ID
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                raise ValueError(f"文件为空: {file_path}")
            
            # 获取文件大小
            file_size = file_path.stat().st_size
            
            # 准备数据
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
                "vector_status": "pending",
                "is_public": True
            }
            
            # 插入数据库
            res = self.supabase.table("knowledge_items").insert(item_data).execute()
            item_id = res.data[0]['id']
            
            logger.info(f"✅ 导入成功: {item_name} (ID: {item_id})")
            return item_id
            
        except Exception as e:
            logger.error(f"❌ 导入文件失败: {e}")
            raise
    
    def import_sample_data(self) -> List[str]:
        """导入示例数据"""
        sample_data = [
            {
                "name": "小学三年级数学 - 三角形面积",
                "grade": "小学三年级",
                "subject": "数学",
                "content": """
三角形面积计算方法

1. 基本公式
   面积 = (底 × 高) ÷ 2
   
2. 已知三边长度（海伦公式）
   设三边长为 a, b, c
   半周长 s = (a + b + c) ÷ 2
   面积 = √[s(s-a)(s-b)(s-c)]

3. 已知两边和夹角
   面积 = (a × b × sin(C)) ÷ 2
   其中 C 是两边的夹角

4. 特殊三角形
   - 等边三角形：面积 = (√3 × a²) ÷ 4
   - 直角三角形：面积 = (直角边1 × 直角边2) ÷ 2
   - 等腰三角形：面积 = (底 × 高) ÷ 2

5. 实际应用
   - 测量地块面积
   - 建筑设计
   - 工程计算
                """
            },
            {
                "name": "初中一年级英语 - 现在进行时",
                "grade": "初中一年级",
                "subject": "英语",
                "content": """
现在进行时 (Present Continuous Tense)

1. 定义
   表示现在正在进行的动作或现阶段正在进行的动作

2. 构成
   am/is/are + -ing形式的动词
   - I am studying
   - He is playing
   - They are reading

3. 用法
   - 现在正在进行的动作：I am writing a letter.
   - 现阶段正在进行的动作：She is learning English.
   - 表示将来的计划：We are going to the cinema tomorrow.

4. 动词-ing形式的变化规则
   - 一般加-ing：play → playing
   - 以e结尾去e加-ing：make → making
   - 重读闭音节双写末尾字母加-ing：run → running

5. 否定形式
   am/is/are + not + -ing
   I am not studying.

6. 疑问形式
   Am/Is/Are + 主语 + -ing?
   Are you studying?
                """
            },
            {
                "name": "高中一年级物理 - 牛顿第二定律",
                "grade": "高中一年级",
                "subject": "物理",
                "content": """
牛顿第二定律 (Newton's Second Law)

1. 定义
   物体的加速度与所受合力成正比，与物体的质量成反比

2. 数学表达式
   F = ma
   其中：
   - F 是合力（单位：牛顿 N）
   - m 是物体质量（单位：千克 kg）
   - a 是加速度（单位：米/秒² m/s²）

3. 矢量形式
   F⃗ = ma⃗
   合力的方向与加速度的方向相同

4. 应用
   - 计算物体的加速度：a = F/m
   - 计算物体所受的合力：F = ma
   - 计算物体的质量：m = F/a

5. 常见题型
   - 水平面上的物体运动
   - 斜面上的物体运动
   - 竖直方向的运动
   - 圆周运动

6. 注意事项
   - F 是合力，不是单个力
   - 需要建立坐标系
   - 注意力的矢量性
                """
            }
        ]
        
        imported_ids = []
        for data in sample_data:
            try:
                item_data = {
                    "user_id": self.user_id,
                    "name": data["name"],
                    "type": "txt",
                    "size": f"{len(data['content']) / 1024:.2f} KB",
                    "content": data["content"],
                    "tags": [data["grade"], data["subject"]],
                    "grade_level": data["grade"],
                    "subject": data["subject"],
                    "vector_status": "pending",
                    "is_public": True
                }
                
                res = self.supabase.table("knowledge_items").insert(item_data).execute()
                item_id = res.data[0]['id']
                imported_ids.append(item_id)
                logger.info(f"✅ 导入示例数据: {data['name']} (ID: {item_id})")
                
            except Exception as e:
                logger.error(f"❌ 导入示例数据失败: {data['name']} - {e}")
        
        return imported_ids
    
    async def vectorize_all_pending(self) -> Dict[str, Any]:
        """
        对所有待向量化的条目进行向量化处理
        
        Returns:
            处理统计信息
        """
        try:
            # 查询所有待处理的条目
            res = self.supabase.table("knowledge_items").select(
                "id, name, content"
            ).eq("vector_status", "pending").execute()
            
            items = res.data
            logger.info(f"📋 发现 {len(items)} 个待处理条目")
            
            stats = {
                "total": len(items),
                "success": 0,
                "failed": 0,
                "details": []
            }
            
            for idx, item in enumerate(items, 1):
                try:
                    logger.info(f"🔄 处理 [{idx}/{len(items)}] {item['name']}...")
                    
                    result = await vectorize_knowledge_item(
                        item_id=item["id"],
                        content=item.get("content", ""),
                        source_resource=item.get("name", "unknown")
                    )
                    
                    if result["success"]:
                        stats["success"] += 1
                        logger.info(f"✅ 完成: {item['name']} ({result['chunk_count']} 块)")
                        stats["details"].append({
                            "name": item["name"],
                            "status": "success",
                            "chunk_count": result["chunk_count"]
                        })
                    else:
                        stats["failed"] += 1
                        logger.error(f"❌ 失败: {item['name']} - {result.get('error')}")
                        stats["details"].append({
                            "name": item["name"],
                            "status": "failed",
                            "error": result.get("error")
                        })
                    
                    # 避免过快请求
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"❌ 异常: {item['name']} - {e}")
                    stats["details"].append({
                        "name": item["name"],
                        "status": "error",
                        "error": str(e)
                    })
            
            logger.info(f"\n📊 处理完成统计:")
            logger.info(f"   总数: {stats['total']}")
            logger.info(f"   成功: {stats['success']}")
            logger.info(f"   失败: {stats['failed']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ 批量向量化异常: {e}")
            return {"total": 0, "success": 0, "failed": 0, "error": str(e)}


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="知识库数据导入工具")
    parser.add_argument("--mode", choices=["sample", "file", "vectorize", "all"], 
                       default="all", help="导入模式")
    parser.add_argument("--file", type=str, help="文件路径（file模式时必需）")
    parser.add_argument("--name", type=str, help="资源名称")
    parser.add_argument("--grade", type=str, help="年级")
    parser.add_argument("--subject", type=str, help="学科")
    
    args = parser.parse_args()
    
    importer = KnowledgeImporter()
    
    # 获取或创建系统用户
    importer.user_id = importer.get_or_create_system_user()
    
    try:
        if args.mode in ["sample", "all"]:
            logger.info("🚀 开始导入示例数据...")
            importer.import_sample_data()
        
        if args.mode == "file":
            if not args.file:
                logger.error("❌ file模式需要指定--file参数")
                return
            logger.info(f"🚀 开始导入文件: {args.file}")
            importer.import_from_file(args.file, args.name, args.grade, args.subject)
        
        if args.mode in ["vectorize", "all"]:
            logger.info("🚀 开始向量化处理...")
            await importer.vectorize_all_pending()
        
        logger.info("✅ 所有操作完成！")
        
    except Exception as e:
        logger.error(f"❌ 导入失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
