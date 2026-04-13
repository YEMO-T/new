"""
PPT模板标准化工具 - 清理格式，保留原始样式
只做必要的格式清理，不覆盖模板原有的字体、颜色、背景
"""

import io
import logging
from typing import Optional
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml

logger = logging.getLogger(__name__)

MIN_SHAPE_SIZE_EMU = Emu(91440)


def make_qualified_ppt_template(original_bytes: bytes) -> bytes:
    """
    将原始PPT字节流转换为系统合格PPT模板
    
    合格标准（保留原始样式）:
        1. 格式标准：必须是标准可解析的pptx，无损坏、无异常元素
        2. 清理标准：删除空文本框、空白形状、冗余无用元素
        3. 结构标准：保留有效内容和布局
        4. 样式保留：保留原始字体、颜色、背景、主题
        5. 兼容标准：保证 python-pptx 100% 正常解析，无崩溃
    
    Args:
        original_bytes: 原始PPT文件的字节流
        
    Returns:
        合格后的PPT字节流
    """
    if not original_bytes or len(original_bytes) < 100:
        logger.warning("[Standardizer] 输入字节流为空或过小，返回原始数据")
        return original_bytes
    
    try:
        prs = _load_presentation(original_bytes)
        if prs is None:
            logger.warning("[Standardizer] 无法加载PPT，返回原始数据")
            return original_bytes
        
        total_slides = len(prs.slides)
        logger.info(f"[Standardizer] 开始清理PPT，共 {total_slides} 页（保留原始样式）")
        
        _clean_empty_elements(prs)
        
        _ensure_slide_layouts_valid(prs)
        
        output_bytes = _save_presentation(prs)
        
        if output_bytes and len(output_bytes) > 100:
            logger.info(f"[Standardizer] 清理完成，输出大小: {len(output_bytes)} 字节")
            return output_bytes
        else:
            logger.warning("[Standardizer] 输出无效，返回原始数据")
            return original_bytes
            
    except Exception as e:
        logger.error(f"[Standardizer] 清理过程异常: {type(e).__name__}: {e}", exc_info=True)
        return original_bytes


def _load_presentation(file_bytes: bytes):
    """安全加载PPT文件"""
    try:
        prs = Presentation(io.BytesIO(file_bytes))
        logger.info(f"[Standardizer] 加载PPT成功，母版数: {len(prs.slide_masters)}, 版式数: {len(prs.slide_layouts)}")
        return prs
    except Exception as e:
        logger.error(f"[Standardizer] 加载PPT失败: {e}")
        return None


def _save_presentation(prs: Presentation) -> Optional[bytes]:
    """安全保存PPT文件"""
    try:
        output = io.BytesIO()
        prs.save(output)
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        logger.error(f"[Standardizer] 保存PPT失败: {e}")
        return None


def _clean_empty_elements(prs: Presentation):
    """清理所有空元素"""
    total_removed = 0
    
    for slide_idx, slide in enumerate(prs.slides):
        shapes_to_remove = []
        
        for shape in slide.shapes:
            try:
                if _is_empty_shape(shape):
                    shapes_to_remove.append(shape)
            except Exception:
                pass
        
        for shape in shapes_to_remove:
            try:
                sp = shape._element
                sp.getparent().remove(sp)
                total_removed += 1
            except Exception:
                pass
        
        if shapes_to_remove:
            logger.debug(f"[Standardizer] 第 {slide_idx + 1} 页清理了 {len(shapes_to_remove)} 个空元素")
    
    if total_removed > 0:
        logger.info(f"[Standardizer] 共清理 {total_removed} 个空元素")


def _ensure_slide_layouts_valid(prs: Presentation):
    """确保幻灯片版式有效"""
    try:
        if len(prs.slide_layouts) == 0:
            logger.warning("[Standardizer] 模板没有版式，这可能导致问题")
    except Exception as e:
        logger.warning(f"[Standardizer] 检查版式失败: {e}")


def _is_empty_shape(shape) -> bool:
    """判断是否为空形状（需要删除）"""
    try:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return False
        
        if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            return False
        
        if shape.shape_type == MSO_SHAPE_TYPE.CHART:
            return False
        
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            return False
        
        if hasattr(shape, 'width') and hasattr(shape, 'height'):
            if shape.width is not None and shape.height is not None:
                if shape.width < MIN_SHAPE_SIZE_EMU or shape.height < MIN_SHAPE_SIZE_EMU:
                    return True
        
        if hasattr(shape, 'text_frame') and shape.text_frame:
            text = ""
            try:
                text = shape.text_frame.text.strip() if shape.text_frame.text else ""
            except Exception:
                pass
            
            if text:
                return False
            
            if shape.shape_type in [MSO_SHAPE_TYPE.TEXT_BOX, MSO_SHAPE_TYPE.AUTO_SHAPE]:
                if hasattr(shape, 'fill'):
                    try:
                        fill = shape.fill
                        if fill.type is not None:
                            return False
                    except Exception:
                        pass
                return True
        
        return False
        
    except Exception:
        return False


def clean_ppt_template(file_bytes: bytes) -> bytes:
    """
    清理PPT模板（便捷函数）
    
    只做格式清理，保留原始样式
    """
    return make_qualified_ppt_template(file_bytes)
