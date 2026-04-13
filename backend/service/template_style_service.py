"""
模板样式基因提取服务
====================
功能：
1. 上传模板时自动提取样式基因（母版/版式/占位符/颜色主题/字体规则）
2. 将样式信息结构化存储到数据库
3. 生成PPT时根据模板ID加载并应用对应样式

集成 TemplateStyleCloner 实现深度样式分析
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from utils.ppt_template_style_cloner import (
    TemplateStyleCloner,
    ThemeGene,
    LayoutGene,
    PlaceholderGene,
    PageType
)

logger = logging.getLogger(__name__)


@dataclass
class TemplateStyleGene:
    """
    模板样式基因 - 数据库存储格式
    
    包含从模板中提取的所有视觉风格信息，
    用于在生成新PPT时完整复制模板风格
    """
    # 基础信息
    template_id: str = ""
    template_name: str = ""
    
    # 主题基因
    theme: Dict[str, Any] = None
    
    # 版式列表
    layouts: List[Dict[str, Any]] = None
    
    # 统计信息
    total_layouts: int = 0
    total_placeholders: int = 0
    
    # 提取时间戳
    extracted_at: str = ""
    
    def __post_init__(self):
        if self.theme is None:
            self.theme = {}
        if self.layouts is None:
            self.layouts = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于JSON序列化）"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TemplateStyleGene':
        """从字典创建实例"""
        return cls(**data)


class TemplateStyleExtractor:
    """
    模板样式提取器
    
    职责：
    1. 接收模板文件路径
    2. 使用 TemplateStyleCloner 深度解析模板
    3. 提取并结构化样式基因
    4. 返回可存储的 TemplateStyleGene 对象
    """
    
    def __init__(self):
        self.cloner: Optional[TemplateStyleCloner] = None
        self.style_gene: Optional[TemplateStyleGene] = None
    
    def extract_from_file(self, template_path: str, template_id: str = "", template_name: str = "") -> TemplateStyleGene:
        """
        从模板文件提取样式基因
        
        Args:
            template_path: 模板 PPT 文件路径
            template_id: 模板ID（用于关联）
            template_name: 模板名称
            
        Returns:
            TemplateStyleGene 样式基因对象
        """
        from datetime import datetime
        
        logger.info(f"[StyleExtractor] 开始提取样式: {template_path}")
        
        try:
            # 使用 TemplateStyleCloner 解析模板
            self.cloner = TemplateStyleCloner(template_path)
            
            # 提取模板基本信息
            info = self.cloner.get_template_info()
            
            # 构建样式基因对象
            self.style_gene = TemplateStyleGene(
                template_id=template_id,
                template_name=template_name or os.path.basename(template_path),
                theme=self._serialize_theme(),
                layouts=self._serialize_layouts(),
                total_layouts=len(info.get('layouts', [])),
                total_placeholders=sum(
                    len(layout.get('placeholders', [])) 
                    for layout in info.get('layouts', [])
                ),
                extracted_at=datetime.now().isoformat()
            )
            
            logger.info(f"[StyleExtractor] 样式提取完成:")
            logger.info(f"  - 版式数量: {self.style_gene.total_layouts}")
            logger.info(f"  - 占位符总数: {self.style_gene.total_placeholders}")
            logger.info(f"  - 主字体: {self.style_gene.theme.get('major_font', 'N/A')}")
            
            return self.style_gene
            
        except Exception as e:
            logger.error(f"[StyleExtractor] 样式提取失败: {e}", exc_info=True)
            raise
    
    def _serialize_theme(self) -> Dict[str, Any]:
        """序列化主题基因"""
        if not self.cloner or not self.cloner.theme_gene:
            return {}
        
        theme = self.cloner.theme_gene
        
        return {
            'colors': {
                'accent1': theme.accent1,
                'accent2': theme.accent2,
                'accent3': theme.accent3,
                'accent4': theme.accent4,
                'accent5': theme.accent5,
                'accent6': theme.accent6,
                'dark1': theme.dark1,
                'light1': theme.light1,
                'hyperlink': theme.hyperlink,
                'followed_hyperlink': theme.followed_hyperlink,
            },
            'fonts': {
                'major_latin': theme.major_font,
                'minor_latin': theme.minor_font,
                'major_east_asian': theme.major_font_east_asian,
                'minor_east_asian': theme.minor_font_east_asian,
            },
            'color_scheme': theme.color_scheme if hasattr(theme, 'color_scheme') else {},
            'font_scheme': theme.font_scheme if hasattr(theme, 'font_scheme') else {},
        }
    
    def _serialize_layouts(self) -> List[Dict[str, Any]]:
        """序列化版式基因"""
        if not self.cloner:
            return []
        
        layouts_data = []
        
        for gene in self.cloner.layout_genes:
            layout_dict = {
                'index': gene.index,
                'name': gene.name,
                'has_title': gene.has_title,
                'has_body': gene.has_body,
                'has_picture': gene.has_picture,
                'has_chart': gene.has_chart,
                'has_table': gene.has_table,
                'placeholder_count': len(gene.placeholders),
                'placeholders': [
                    {
                        'idx': ph.idx,
                        'type': ph.ph_type,
                        'name': ph.name,
                        'has_text_frame': ph.has_text_frame,
                    }
                    for ph in gene.placeholders
                ]
            }
            layouts_data.append(layout_dict)
        
        return layouts_data


def extract_and_save_template_style(
    template_path: str,
    template_id: str,
    template_name: str = "",
    supabase_client=None
) -> bool:
    """
    提取模板样式并保存到数据库（高层封装函数）
    
    Args:
        template_path: 模板文件路径
        template_id: 模板ID
        template_name: 模板名称
        supabase_client: 可选的 Supabase 客户端
        
    Returns:
        是否成功
    """
    try:
        extractor = TemplateStyleExtractor()
        style_gene = extractor.extract_from_file(template_path, template_id, template_name)
        
        style_json = style_gene.to_dict()
        
        if supabase_client is None:
            from repository.supabase_client import get_supabase_client
            supabase_client = get_supabase_client()
        
        result = supabase_client.table('user_templates').update({
            'style_gene': style_json,
            'style_extracted': True,
            'style_extracted_at': style_gene.extracted_at
        }).eq('id', template_id).execute()
        
        if result.data:
            logger.info(f"[StyleExtractor] 样式已保存到数据库: template_id={template_id}")
            return True
        else:
            logger.warning(f"[StyleExtractor] 样式保存失败: template_id={template_id}")
            return False
            
    except Exception as e:
        logger.error(f"[StyleExtractor] 提取并保存样式失败: {e}")
        return False


def load_template_style_from_db(
    template_id: str,
    supabase_client=None
) -> Optional[TemplateStyleGene]:
    """
    从数据库加载模板样式基因
    
    Args:
        template_id: 模板ID
        supabase_client: 可选的 Supabase 客户端
        
    Returns:
        TemplateStyleGene 对象，如果不存在则返回 None
    """
    try:
        if supabase_client is None:
            from repository.supabase_client import get_supabase_client
            supabase_client = get_supabase_client()
        
        response = supabase_client.table('user_templates').select(
            'style_gene, style_extracted'
        ).eq('id', template_id).execute()
        
        if not response.data:
            return None
        
        template_record = response.data[0]
        style_data = template_record.get('style_gene')
        
        if not style_data:
            logger.warning(f"[StyleExtractor] 模板无样式数据: template_id={template_id}")
            return None
        
        return TemplateStyleGene.from_dict(style_data)
        
    except Exception as e:
        logger.error(f"[StyleExtractor] 加载样式失败: {e}")
        return None


def generate_ppt_with_template_style(
    template_id: str,
    slides_content: List[Dict[str, Any]],
    output_path: Optional[str] = None,
    supabase_client=None
):
    """
    根据模板ID生成风格一致的PPT（核心业务函数）
    
    流程：
    1. 从数据库获取模板文件路径
    2. 加载模板样式基因（可选，用于日志）
    3. 使用 TemplateStyleCloner 克隆风格
    4. 添加幻灯片内容
    5. 返回 PPTX 字节流
    
    Args:
        template_id: 模板ID
        slides_content: 幻灯片内容列表
        output_path: 可选的输出路径
        supabase_client: 可选的 Supabase 客户端
        
    Returns:
        PPTX 字节流 (io.BytesIO)
    """
    import io
    from utils.ppt_template_style_cloner import (
        create_styled_ppt_from_template,
        SlideContentData,
        PageType
    )
    
    try:
        # 1. 获取模板路径
        if supabase_client is None:
            from repository.supabase_client import get_supabase_client
            supabase_client = get_supabase_client()
        
        response = supabase_client.table('user_templates').select(
            'id, title, file_path, file_bucket'
        ).eq('id', template_id).execute()
        
        if not response.data:
            raise ValueError(f"模板不存在: {template_id}")
        
        template = response.data[0]
        
        # 确定本地模板路径
        local_template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'templates'
        )
        local_template_path = os.path.join(local_template_dir, f"{template_id}.pptx")
        
        if not os.path.exists(local_template_path):
            # 尝试从 Storage 下载
            try:
                from service.storage_service import download_template_file
                file_data = download_template_file(template['file_bucket'], template['file_path'])
                
                os.makedirs(local_template_dir, exist_ok=True)
                with open(local_template_path, 'wb') as f:
                    f.write(file_data)
                    
                logger.info(f"[StyleGenerator] 模板已下载: {local_template_path}")
            except Exception as e:
                logger.error(f"[StyleGenerator] 无法获取模板文件: {e}")
                raise ValueError("模板文件不可用")
        
        # 2. 加载样式信息（用于日志）
        style_gene = load_template_style_from_db(template_id, supabase_client)
        if style_gene:
            logger.info(f"[StyleGenerator] 已加载样式基因: "
                       f"版式数={style_gene.total_layouts}, "
                       f"主字体={style_gene.theme.get('major_font', 'N/A')}")
        
        # 3. 转换内容格式
        converted_slides = []
        for slide_dict in slides_content:
            page_type_str = slide_dict.get('page_type', 'content').lower()
            try:
                page_type = PageType(page_type_str)
            except ValueError:
                page_type = PageType.CONTENT
            
            content = slide_dict.get('content', [])
            if isinstance(content, str):
                content = [content] if content.strip() else []
            elif not isinstance(content, list):
                content = []
            
            slide_content = SlideContentData(
                title=slide_dict.get('title', ''),
                subtitle=slide_dict.get('subtitle', ''),
                content=content,
                page_type=page_type,
                notes=slide_dict.get('notes', '')
            )
            converted_slides.append(slide_content)
        
        # 4. 生成PPT
        pptx_bytes = create_styled_ppt_from_template(
            template_path=local_template_path,
            slides_content=converted_slides,
            output_path=output_path
        )
        
        # 5. 更新使用统计
        try:
            supabase_client.table('user_templates').update({
                'usage_count': getattr(supabase_client.table('user_templates')
                                     .select('usage_count')
                                     .eq('id', template_id)
                                     .execute()
                                     .data[0], 'usage_count', 0) + 1
            }).eq('id', template_id).execute()
        except Exception as e:
            logger.debug(f"[StyleGenerator] 更新使用统计失败: {e}")
        
        logger.info(f"[StyleGenerator] PPT生成成功: "
                   f"template={template.get('title')}, "
                   f"slides={len(converted_slides)}, "
                   f"size={len(pptx_bytes.getvalue()) / 1024:.1f}KB")
        
        return pptx_bytes
        
    except Exception as e:
        logger.error(f"[StyleGenerator] 生成PPT失败: {e}", exc_info=True)
        raise


# ============================================================
# 批量处理工具函数
# ============================================================

def batch_extract_styles_for_templates(
    template_ids: List[str],
    base_template_dir: str = None
) -> Dict[str, Any]:
    """
    批量提取多个模板的样式基因
    
    用于：
    - 初始化时处理历史模板
    - 定期任务更新样式缓存
    
    Args:
        template_ids: 模板ID列表
        base_template_dir: 模板基础目录
        
    Returns:
        处理结果统计
    """
    if base_template_dir is None:
        base_template_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'templates'
        )
    
    results = {
        'total': len(template_ids),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }
    
    for template_id in template_ids:
        try:
            local_path = os.path.join(base_template_dir, f"{template_id}.pptx")
            
            if not os.path.exists(local_path):
                results['skipped'] += 1
                results['details'].append({
                    'template_id': template_id,
                    'status': 'skipped',
                    'reason': 'file_not_found'
                })
                continue
            
            success = extract_and_save_template_style(
                template_path=local_path,
                template_id=template_id
            )
            
            if success:
                results['success'] += 1
                results['details'].append({
                    'template_id': template_id,
                    'status': 'success'
                })
            else:
                results['failed'] += 1
                results['details'].append({
                    'template_id': template_id,
                    'status': 'failed',
                    'reason': 'save_failed'
                })
                
        except Exception as e:
            results['failed'] += 1
            results['details'].append({
                'template_id': template_id,
                'status': 'error',
                'error': str(e)
            })
    
    logger.info(f"[StyleExtractor] 批量提取完成: "
               f"成功={results['success']}, 失败={results['failed']}, 跳过={results['skipped']}")
    
    return results


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("模板样式提取服务 - 测试程序")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python template_style_service.py <模板路径> [模板ID]")
        print("\n示例:")
        print("  python template_style_service.py data/templates/xxx.pptx uuid-xxx")
        sys.exit(1)
    
    template_path = sys.argv[1]
    template_id = sys.argv[2] if len(sys.argv) > 2 else "test-template-id"
    
    try:
        extractor = TemplateStyleExtractor()
        style_gene = extractor.extract_from_file(template_path, template_id)
        
        print(f"\n[SUCCESS] 样式提取完成!")
        print(f"\n--- 样式基因摘要 ---")
        print(json.dumps(style_gene.to_dict(), indent=2, ensure_ascii=False, default=str))
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
