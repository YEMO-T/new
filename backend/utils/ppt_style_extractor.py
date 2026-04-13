"""
PPT 样式元数据提取器
从 PPT 模板中提取可复用的样式信息，用于后续生成同风格 PPT
"""
import io
import logging
from typing import Dict, Any, List, Optional, Tuple
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.dml.color import RGBColor

logger = logging.getLogger(__name__)


def extract_ppt_style_metadata(ppt_bytes: bytes) -> Dict[str, Any]:
    """
    从 PPT 文件字节流提取样式元数据
    
    Args:
        ppt_bytes: PPT 文件的二进制数据
        
    Returns:
        JSON 格式的样式数据，包含：
        - title_font: 标题字体样式
        - body_font: 正文字体样式
        - theme_colors: 主题颜色
        - slide_layouts: 幻灯片布局信息
        - background_styles: 背景样式
        - slide_master_info: 母版信息
    """
    result = {
        "success": False,
        "title_font": {},
        "body_font": {},
        "theme_colors": {},
        "slide_layouts": [],
        "background_styles": [],
        "slide_master_info": {},
        "extracted_styles": {},
        "error": None
    }
    
    try:
        prs = Presentation(io.BytesIO(ppt_bytes))
        
        result["slide_master_info"] = _extract_slide_master_info(prs)
        
        result["theme_colors"] = _extract_theme_colors(prs)
        
        title_font, body_font = _extract_fonts_from_slides(prs)
        result["title_font"] = title_font
        result["body_font"] = body_font
        
        result["slide_layouts"] = _extract_slide_layouts(prs)
        
        result["background_styles"] = _extract_background_styles(prs)
        
        result["extracted_styles"] = _extract_usable_styles(prs)
        
        result["success"] = True
        
    except Exception as e:
        logger.error(f"提取 PPT 样式失败: {e}")
        result["error"] = str(e)
    
    return result


def _extract_slide_master_info(prs: Presentation) -> Dict[str, Any]:
    """提取幻灯片母版信息"""
    master_info = {
        "name": "",
        "slide_count": 0,
        "layout_count": 0,
        "width": 0,
        "height": 0
    }
    
    try:
        if prs.slide_masters:
            master = prs.slide_masters[0]
            master_info["name"] = getattr(master, 'name', 'Unknown')
            master_info["layout_count"] = len(prs.slide_layouts)
            
        master_info["slide_count"] = len(prs.slides)
        master_info["width"] = prs.slide_width.inches if prs.slide_width else 13.333
        master_info["height"] = prs.slide_height.inches if prs.slide_height else 7.5
        
    except Exception as e:
        logger.warning(f"提取母版信息失败: {e}")
    
    return master_info


def _extract_theme_colors(prs: Presentation) -> Dict[str, Any]:
    """提取主题颜色"""
    colors = {
        "background": "#FFFFFF",
        "accent_colors": [],
        "text_colors": {
            "title": "#000000",
            "body": "#333333"
        }
    }
    
    try:
        if prs.slide_masters:
            master = prs.slide_masters[0]
            
            try:
                theme = master.part.slide_master.theme
                if theme and hasattr(theme, 'color_map'):
                    color_map = theme.color_map
                    
                    color_names = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 
                                   'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink']
                    
                    for name in color_names:
                        try:
                            color = getattr(color_map, name, None)
                            if color:
                                rgb = _get_rgb_from_color(color)
                                if rgb:
                                    if name == 'lt1':
                                        colors["background"] = rgb
                                    elif name.startswith('accent'):
                                        colors["accent_colors"].append(rgb)
                                    elif name == 'dk1':
                                        colors["text_colors"]["title"] = rgb
                                    elif name == 'dk2':
                                        colors["text_colors"]["body"] = rgb
                        except:
                            pass
            except Exception as e:
                logger.debug(f"提取主题颜色映射失败: {e}")
        
        if prs.slides:
            for slide in prs.slides[:3]:
                bg_color = _extract_slide_background_color(slide)
                if bg_color and bg_color != "#FFFFFF":
                    colors["background"] = bg_color
                    break
                    
    except Exception as e:
        logger.warning(f"提取主题颜色失败: {e}")
    
    if not colors["accent_colors"]:
        colors["accent_colors"] = ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47"]
    
    return colors


def _extract_slide_background_color(slide) -> Optional[str]:
    """提取幻灯片背景颜色"""
    try:
        if hasattr(slide, 'background'):
            bg = slide.background
            if hasattr(bg, 'fill'):
                fill = bg.fill
                if fill.type is not None:
                    if hasattr(fill, 'fore_color') and fill.fore_color:
                        return _get_rgb_from_color(fill.fore_color)
    except:
        pass
    return None


def _extract_fonts_from_slides(prs: Presentation) -> Tuple[Dict, Dict]:
    """从幻灯片中提取标题和正文字体样式"""
    title_font = {
        "name": "微软雅黑",
        "size": 32,
        "color": "#000000",
        "bold": True,
        "italic": False
    }
    
    body_font = {
        "name": "微软雅黑",
        "size": 18,
        "color": "#333333",
        "bold": False,
        "italic": False
    }
    
    try:
        title_fonts = []
        body_fonts = []
        
        for slide in prs.slides:
            for shape in slide.shapes:
                if not hasattr(shape, 'text_frame'):
                    continue
                    
                is_title = _is_title_shape(shape)
                font_info = _extract_font_from_shape(shape)
                
                if font_info:
                    if is_title:
                        title_fonts.append(font_info)
                    else:
                        body_fonts.append(font_info)
        
        if title_fonts:
            title_font = _merge_font_infos(title_fonts, title_font)
        if body_fonts:
            body_font = _merge_font_infos(body_fonts, body_font)
            
    except Exception as e:
        logger.warning(f"提取字体样式失败: {e}")
    
    return title_font, body_font


def _is_title_shape(shape) -> bool:
    """判断形状是否为标题"""
    try:
        if hasattr(shape, 'placeholder_format'):
            ph_type = shape.placeholder_format.type
            title_types = [
                PP_PLACEHOLDER.TITLE,
                PP_PLACEHOLDER.CENTER_TITLE,
                PP_PLACEHOLDER.VERTICAL_TITLE
            ]
            if ph_type in title_types:
                return True
        
        if hasattr(shape, 'name'):
            name_lower = shape.name.lower()
            if 'title' in name_lower or '标题' in name_lower:
                return True
                
        if hasattr(shape, 'text_frame'):
            text = shape.text_frame.text.strip()
            if text and len(text) < 50:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.font.bold or (run.font.size and run.font.size.pt >= 24):
                            return True
    except:
        pass
    
    return False


def _extract_font_from_shape(shape) -> Optional[Dict[str, Any]]:
    """从形状中提取字体信息"""
    font_info = {}
    
    try:
        if not hasattr(shape, 'text_frame'):
            return None
            
        text_frame = shape.text_frame
        if not text_frame.text.strip():
            return None
        
        fonts_found = []
        sizes_found = []
        colors_found = []
        bold_count = 0
        italic_count = 0
        run_count = 0
        
        for paragraph in text_frame.paragraphs:
            for run in paragraph.runs:
                if not run.text.strip():
                    continue
                    
                run_count += 1
                font = run.font
                
                if font.name:
                    fonts_found.append(font.name)
                    
                if font.size:
                    sizes_found.append(font.size.pt)
                    
                color = _get_rgb_from_font(font)
                if color:
                    colors_found.append(color)
                    
                if font.bold:
                    bold_count += 1
                if font.italic:
                    italic_count += 1
        
        if not run_count:
            return None
        
        from collections import Counter
        
        if fonts_found:
            font_info["name"] = Counter(fonts_found).most_common(1)[0][0]
        if sizes_found:
            font_info["size"] = round(sum(sizes_found) / len(sizes_found))
        if colors_found:
            font_info["color"] = Counter(colors_found).most_common(1)[0][0]
            
        font_info["bold"] = bold_count > run_count / 2
        font_info["italic"] = italic_count > run_count / 2
        
    except Exception as e:
        logger.debug(f"提取形状字体失败: {e}")
        return None
    
    return font_info if font_info else None


def _merge_font_infos(font_infos: List[Dict], default: Dict) -> Dict:
    """合并多个字体信息，取最常见值"""
    from collections import Counter
    
    result = default.copy()
    
    if not font_infos:
        return result
    
    names = [f["name"] for f in font_infos if f.get("name")]
    sizes = [f["size"] for f in font_infos if f.get("size")]
    colors = [f["color"] for f in font_infos if f.get("color")]
    bolds = [f["bold"] for f in font_infos if "bold" in f]
    italics = [f["italic"] for f in font_infos if "italic" in f]
    
    if names:
        result["name"] = Counter(names).most_common(1)[0][0]
    if sizes:
        result["size"] = round(sum(sizes) / len(sizes))
    if colors:
        result["color"] = Counter(colors).most_common(1)[0][0]
    if bolds:
        result["bold"] = sum(bolds) > len(bolds) / 2
    if italics:
        result["italic"] = sum(italics) > len(italics) / 2
    
    return result


def _extract_slide_layouts(prs: Presentation) -> List[Dict[str, Any]]:
    """提取幻灯片布局信息"""
    layouts = []
    
    try:
        for i, layout in enumerate(prs.slide_layouts):
            layout_info = {
                "index": i,
                "name": getattr(layout, 'name', f'Layout_{i}'),
                "placeholder_count": 0,
                "placeholders": []
            }
            
            try:
                for ph in layout.placeholders:
                    ph_info = {
                        "idx": ph.placeholder_format.idx if hasattr(ph, 'placeholder_format') else -1,
                        "type": str(ph.placeholder_format.type) if hasattr(ph, 'placeholder_format') else "unknown",
                        "name": getattr(ph, 'name', ''),
                        "left": ph.left.inches if ph.left else 0,
                        "top": ph.top.inches if ph.top else 0,
                        "width": ph.width.inches if ph.width else 0,
                        "height": ph.height.inches if ph.height else 0
                    }
                    layout_info["placeholders"].append(ph_info)
                    
                layout_info["placeholder_count"] = len(layout_info["placeholders"])
            except Exception as e:
                logger.debug(f"提取布局占位符失败: {e}")
            
            layouts.append(layout_info)
            
    except Exception as e:
        logger.warning(f"提取幻灯片布局失败: {e}")
    
    return layouts


def _extract_background_styles(prs: Presentation) -> List[Dict[str, Any]]:
    """提取背景样式"""
    backgrounds = []
    
    try:
        for i, slide in enumerate(prs.slides[:10]):
            bg_info = {
                "slide_index": i,
                "type": "solid",
                "color": "#FFFFFF",
                "has_image": False
            }
            
            try:
                if hasattr(slide, 'background'):
                    bg = slide.background
                    
                    if hasattr(bg, 'fill'):
                        fill = bg.fill
                        
                        if fill.type == 1:
                            bg_info["type"] = "solid"
                            if hasattr(fill, 'fore_color'):
                                bg_info["color"] = _get_rgb_from_color(fill.fore_color) or "#FFFFFF"
                        elif fill.type == 2:
                            bg_info["type"] = "gradient"
                            bg_info["gradient_info"] = _extract_gradient_info(fill)
                        elif fill.type == 3:
                            bg_info["type"] = "pattern"
                        elif fill.type == 4:
                            bg_info["type"] = "picture"
                            bg_info["has_image"] = True
                            
            except Exception as e:
                logger.debug(f"提取幻灯片 {i} 背景失败: {e}")
            
            backgrounds.append(bg_info)
            
    except Exception as e:
        logger.warning(f"提取背景样式失败: {e}")
    
    return backgrounds


def _extract_gradient_info(fill) -> Dict[str, Any]:
    """提取渐变信息"""
    gradient = {
        "angle": 0,
        "stops": []
    }
    
    try:
        if hasattr(fill, 'gradient_angle'):
            gradient["angle"] = fill.gradient_angle or 0
            
        if hasattr(fill, 'gradient_stops'):
            for stop in fill.gradient_stops:
                stop_info = {
                    "position": getattr(stop, 'position', 0),
                    "color": _get_rgb_from_color(stop.color) if hasattr(stop, 'color') else "#FFFFFF"
                }
                gradient["stops"].append(stop_info)
                
    except Exception as e:
        logger.debug(f"提取渐变信息失败: {e}")
    
    return gradient


def _extract_usable_styles(prs: Presentation) -> Dict[str, Any]:
    """提取可直接用于生成 PPT 的样式"""
    styles = {
        "fonts": {
            "title": {"name": "微软雅黑", "size": 32, "color": "#000000", "bold": True},
            "body": {"name": "微软雅黑", "size": 18, "color": "#333333", "bold": False},
            "subtitle": {"name": "微软雅黑", "size": 24, "color": "#666666", "bold": False}
        },
        "colors": {
            "primary": "#4472C4",
            "secondary": "#ED7D31",
            "background": "#FFFFFF",
            "text": "#333333",
            "accent": "#4472C4"
        },
        "spacing": {
            "title_top": 0.5,
            "body_left": 0.5,
            "body_right": 0.5,
            "line_spacing": 1.5
        },
        "sizes": {
            "slide_width": 13.333,
            "slide_height": 7.5,
            "title_height": 1.0,
            "content_height": 5.5
        }
    }
    
    try:
        title_font, body_font = _extract_fonts_from_slides(prs)
        
        if title_font.get("name"):
            styles["fonts"]["title"]["name"] = title_font["name"]
        if title_font.get("size"):
            styles["fonts"]["title"]["size"] = title_font["size"]
        if title_font.get("color"):
            styles["fonts"]["title"]["color"] = title_font["color"]
        if "bold" in title_font:
            styles["fonts"]["title"]["bold"] = title_font["bold"]
            
        if body_font.get("name"):
            styles["fonts"]["body"]["name"] = body_font["name"]
            styles["fonts"]["subtitle"]["name"] = body_font["name"]
        if body_font.get("size"):
            styles["fonts"]["body"]["size"] = body_font["size"]
            styles["fonts"]["subtitle"]["size"] = round(body_font["size"] * 1.2)
        if body_font.get("color"):
            styles["fonts"]["body"]["color"] = body_font["color"]
            styles["fonts"]["subtitle"]["color"] = body_font["color"]
        
        theme_colors = _extract_theme_colors(prs)
        
        if theme_colors.get("background"):
            styles["colors"]["background"] = theme_colors["background"]
        if theme_colors.get("accent_colors"):
            styles["colors"]["primary"] = theme_colors["accent_colors"][0]
            styles["colors"]["accent"] = theme_colors["accent_colors"][0]
            if len(theme_colors["accent_colors"]) > 1:
                styles["colors"]["secondary"] = theme_colors["accent_colors"][1]
        if theme_colors.get("text_colors", {}).get("title"):
            styles["colors"]["text"] = theme_colors["text_colors"]["body"]
            
        styles["sizes"]["slide_width"] = prs.slide_width.inches if prs.slide_width else 13.333
        styles["sizes"]["slide_height"] = prs.slide_height.inches if prs.slide_height else 7.5
        
    except Exception as e:
        logger.warning(f"提取可用样式失败: {e}")
    
    return styles


def _get_rgb_from_color(color) -> Optional[str]:
    """从颜色对象获取 RGB 十六进制值"""
    try:
        if hasattr(color, 'rgb') and color.rgb:
            rgb = color.rgb
            if isinstance(rgb, str):
                return f"#{rgb}"
            else:
                return f"#{str(rgb)}"
        elif hasattr(color, 'theme_color'):
            return None
    except:
        pass
    return None


def _get_rgb_from_font(font) -> Optional[str]:
    """从字体对象获取颜色"""
    try:
        if hasattr(font, 'color') and font.color:
            return _get_rgb_from_color(font.color)
    except:
        pass
    return None


def apply_style_to_presentation(prs: Presentation, style_metadata: Dict[str, Any]) -> Presentation:
    """
    将提取的样式应用到新的 Presentation 对象
    
    Args:
        prs: 要应用样式的 Presentation 对象
        style_metadata: extract_ppt_style_metadata 返回的样式数据
        
    Returns:
        应用了样式的 Presentation 对象
    """
    try:
        styles = style_metadata.get("extracted_styles", {})
        
        if not styles:
            return prs
            
        for slide in prs.slides:
            for shape in slide.shapes:
                if not hasattr(shape, 'text_frame'):
                    continue
                    
                is_title = _is_title_shape(shape)
                font_style = styles.get("fonts", {}).get("title" if is_title else "body", {})
                
                if font_style:
                    _apply_font_style(shape, font_style)
                    
    except Exception as e:
        logger.warning(f"应用样式失败: {e}")
    
    return prs


def _apply_font_style(shape, font_style: Dict[str, Any]):
    """应用字体样式到形状"""
    try:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                font = run.font
                
                if font_style.get("name"):
                    font.name = font_style["name"]
                    try:
                        run.element.rPr.set('asciiFont', font_style["name"])
                        run.element.rPr.set('hAnsiFont', font_style["name"])
                        run.element.rPr.set('eastAsiaFont', font_style["name"])
                    except:
                        pass
                        
                if font_style.get("size"):
                    font.size = Pt(font_style["size"])
                    
                if font_style.get("bold") is not None:
                    font.bold = font_style["bold"]
                    
                if font_style.get("italic") is not None:
                    font.italic = font_style["italic"]
                    
                if font_style.get("color"):
                    try:
                        color_hex = font_style["color"].lstrip('#')
                        font.color.rgb = RGBColor(
                            int(color_hex[0:2], 16),
                            int(color_hex[2:4], 16),
                            int(color_hex[4:6], 16)
                        )
                    except:
                        pass
                        
    except Exception as e:
        logger.debug(f"应用字体样式失败: {e}")
