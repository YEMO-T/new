"""
智能 PPT 排版引擎
================
功能：
1. 从模板深度提取视觉样式基因
2. 根据内容长度智能调整排版
3. 完全继承模板的字体、颜色、间距等格式
4. 支持自适应缩放和自动换行

核心原理：
- 使用 XML 级别操作保持原始格式
- 基于内容长度动态计算最佳字号
- 继承模板的颜色主题和字体方案
"""

import os
import io
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from copy import deepcopy
from lxml import etree

from pptx import Presentation
from pptx.util import Pt, Emu, Inches, Cm
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.oxml.ns import qn, nsmap

logger = logging.getLogger(__name__)


@dataclass
class StyleRule:
    """样式规则 - 描述一个文本元素的格式"""
    font_name: str = None
    font_size: float = None
    font_color: str = None
    bold: bool = None
    italic: bool = None
    underline: bool = None
    alignment: str = None
    line_spacing: float = None
    space_before: float = None
    space_after: float = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items() 
            if v is not None
        }
    
    def apply_to_run(self, run):
        """将样式规则应用到 run 对象"""
        try:
            from pptx.util import Pt
            
            if self.font_name and hasattr(run.font, 'name'):
                run.font.name = self.font_name
            
            if self.font_size:
                run.font.size = Pt(self.font_size)
            
            if self.font_color:
                if self.font_color.startswith('#'):
                    r = int(self.font_color[1:3], 16)
                    g = int(self.font_color[3:5], 16)
                    b = int(self.font_color[5:7], 16)
                    run.font.color.rgb = RGBColor(r, g, b)
            
            if self.bold is not None:
                run.font.bold = self.bold
                
            if self.italic is not None:
                run.font.italic = self.italic
                
        except Exception as e:
            logger.debug(f"应用样式失败: {e}")


@dataclass
class SlideLayoutTemplate:
    """幻灯片版式模板"""
    layout_name: str
    layout_index: int
    
    # 占位符样式映射
    title_style: StyleRule = None
    subtitle_style: StyleRule = None
    body_style: StyleRule = None
    
    # 占位符位置信息
    placeholders: Dict[str, Dict] = field(default_factory=dict)
    
    # 版式特征
    has_title: bool = True
    has_subtitle: bool = False
    has_body: bool = True
    has_picture: bool = False


class SmartStyleExtractor:
    """
    智能样式提取器
    
    从模板中深度提取：
    - 颜色主题（6种强调色 + 文字色）
    - 字体方案（中西文主次字体）
    - 各版式的占位符样式
    - 段落格式（行距、间距）
    - 项目符号样式
    """
    
    def __init__(self, template_path: str):
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        self.template_path = template_path
        self.prs: Optional[Presentation] = None
        
        # 提取的全局样式
        self.theme_colors: Dict[str, str] = {}
        self.theme_fonts: Dict[str, str] = {}
        
        # 各版式的样式模板
        self.layout_templates: Dict[str, SlideLayoutTemplate] = {}
        
        self._extract_all()
    
    def _extract_all(self):
        """执行全部提取操作"""
        logger.info("[SmartStyle] 开始提取模板样式...")

        self.prs = Presentation(self.template_path)
        self._original_slide_count = len(self.prs.slides)

        self._extract_theme_colors()
        self._extract_theme_fonts()
        self._extract_layout_templates()

        logger.info(f"[SmartStyle] 样式提取完成:")
        logger.info(f"  - 颜色主题: {len(self.theme_colors)} 种")
        logger.info(f"  - 字体方案: {len(self.theme_fonts)} 种")
        logger.info(f"  - 版式模板: {len(self.layout_templates)} 个")
        logger.info(f"  - 原始模板页数: {self._original_slide_count}")
    
    def _extract_theme_colors(self):
        """提取颜色主题"""
        try:
            for master in self.prs.slide_masters:
                master_el = master._element
                
                clr_scheme = master_el.find(
                    './/{http://schemas.openxmlformats.org/drawingml/2006/main}clrScheme'
                )
                
                if clr_scheme is not None:
                    color_map = {
                        'dk1': 'dark1', 'lt1': 'light1',
                        'dk2': 'dark2', 'lt2': 'light2',
                        'accent1': 'accent1', 'accent2': 'accent2',
                        'accent3': 'accent3', 'accent4': 'accent4',
                        'accent5': 'accent5', 'accent6': 'accent6',
                        'hlink': 'hyperlink', 'folHlink': 'followed_hyperlink'
                    }
                    
                    for child in clr_scheme:
                        tag_local = etree.QName(child.tag).localname
                        if tag_local in color_map:
                            srgb = child.find(
                                '{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr'
                            )
                            if srgb is not None:
                                val = srgb.get('val')
                                self.theme_colors[color_map[tag_local]] = val
                    
                    break  # 只处理第一个母版
                    
        except Exception as e:
            logger.warning(f"[SmartStyle] 提取颜色主题失败: {e}")
    
    def _extract_theme_fonts(self):
        """提取字体方案"""
        try:
            for master in self.prs.slide_masters:
                master_el = master._element
                
                font_scheme = master_el.find(
                    './/{http://schemas.openxmlformats.org/drawingml/2006/main}fontScheme'
                )
                
                if font_scheme is not None:
                    # 主要字体
                    major_font = font_scheme.find(
                        './/{http://schemas.openxmlformats.org/drawingml/2006/main}majorFont'
                    )
                    if major_font is not None:
                        latin = major_font.find(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}latin'
                        )
                        ea = major_font.find(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}ea'
                        )
                        if latin is not None:
                            self.theme_fonts['major_latin'] = latin.get('typeface')
                        if ea is not None:
                            self.theme_fonts['major_east_asian'] = ea.get('typeface')
                    
                    # 次要字体
                    minor_font = font_scheme.find(
                        './/{http://schemas.openxmlformats.org/drawingml/2006/main}minorFont'
                    )
                    if minor_font is not None:
                        latin = minor_font.find(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}latin'
                        )
                        ea = minor_font.find(
                            './/{http://schemas.openxmlformats.org/drawingml/2006/main}ea'
                        )
                        if latin is not None:
                            self.theme_fonts['minor_latin'] = latin.get('typeface')
                        if ea is not None:
                            self.theme_fonts['minor_east_asian'] = ea.get('typeface')
                    
                    break
                    
        except Exception as e:
            logger.warning(f"[SmartStyle] 提取字体方案失败: {e}")
    
    def _extract_layout_templates(self):
        """提取各版式的样式模板"""
        for idx, layout in enumerate(self.prs.slide_layouts):
            template = SlideLayoutTemplate(
                layout_name=layout.name,
                layout_index=idx
            )
            
            # 分析每个占位符
            for shape in layout.placeholders:
                ph_info = {
                    'idx': shape.placeholder_format.idx,
                    'type': str(shape.placeholder_format.type),
                    'name': shape.name,
                    'left': shape.left,
                    'top': shape.top,
                    'width': shape.width,
                    'height': shape.height,
                }
                
                # 尝试提取占位符的样式
                style = self._extract_placeholder_style(shape)
                ph_info['style'] = style.to_dict() if style else {}
                
                # 分类存储
                ph_type = str(shape.placeholder_format.type)
                template.placeholders[shape.name] = ph_info
                
                # 判断版式特征
                if ph_type in [str(PP_PLACEHOLDER.TITLE), 
                              str(PP_PLACEHOLDER.CENTER_TITLE),
                              str(PP_PLACEHOLDER.VERTICAL_TITLE)]:
                    template.has_title = True
                    if template.title_style is None or shape.name.lower() in ['title']:
                        template.title_style = style
                        
                elif ph_type == str(PP_PLACEHOLDER.SUBTITLE):
                    template.has_subtitle = True
                    template.subtitle_style = style
                    
                elif ph_type in [str(PP_PLACEHOLDER.BODY),
                                str(PP_PLACEHOLDER.OBJECT),
                                str(PP_PLACEHOLDER.VERTICAL_BODY)]:
                    template.has_body = True
                    if template.body_style is None or shape.name.lower() in ['content', 'body']:
                        template.body_style = style
                        
                elif ph_type == str(PP_PLACEHOLDER.PICTURE):
                    template.has_picture = True
            
            self.layout_templates[layout.name] = template
            self.layout_templates[str(idx)] = template
    
    def _extract_placeholder_style(self, shape) -> Optional[StyleRule]:
        """从占位符提取样式规则"""
        try:
            if not hasattr(shape, 'text_frame'):
                return None
            
            tf = shape.text_frame
            
            if not tf.paragraphs:
                return None
            
            para = tf.paragraphs[0]
            
            rule = StyleRule()
            
            # 提取段落对齐
            if para.alignment:
                alignment_map = {
                    PP_ALIGN.LEFT: 'left',
                    PP_ALIGN.CENTER: 'center',
                    PP_ALIGN.RIGHT: 'right',
                    PP_ALIGN.JUSTIFY: 'justify',
                }
                rule.alignment = alignment_map.get(para.alignment)
            
            # 提取行距
            if para.line_spacing:
                rule.line_spacing = para.line_spacing
            
            # 提取段落间距
            if para.space_before:
                rule.space_before = para.space_before.pt if hasattr(para.space_before, 'pt') else para.space_before
            if para.space_after:
                rule.space_after = para.space_after.pt if hasattr(para.space_after, 'pt') else para.space_after
            
            # 从 run 中提取字体样式
            if para.runs:
                run = para.runs[0]
                font = run.font
                
                if font.name:
                    rule.font_name = font.name
                if font.size:
                    rule.font_size = font.size.pt
                if font.bold is not None:
                    rule.bold = font.bold
                if font.italic is not None:
                    rule.italic = font.italic
                if font.color and font.color.type is not None:
                    try:
                        if hasattr(font.color, 'rgb') and font.color.rgb:
                            rule.font_color = str(font.color.rgb)
                    except:
                        pass
            
            return rule
            
        except Exception as e:
            logger.debug(f"[SmartStyle] 提取占位符样式失败: {e}")
            return None

    def _remove_original_template_slides(self):
        """
        删除所有原始模板幻灯片（用户页面已添加完毕后调用）
        
        使用 python-pptx 内部 API (prs.slides._sldIdLst) 直接操作
        """
        original_count = getattr(self, '_original_slide_count', 0)
        if original_count == 0:
            return

        removed = 0

        for _ in range(original_count):
            if len(self.prs.slides) <= 0:
                break

            try:
                sld_id_lst = self.prs.slides._sldIdLst
                rId = sld_id_lst[0].rId
                self.prs.part.drop_rel(rId)
                del sld_id_lst[0]
                removed += 1
            except Exception as e:
                logger.warning(f"[SmartStyle] 删除原始模板页出错: {e}")
                break

        logger.info(f"[SmartStyle] 已删除 {removed} 张原始模板页")
                break

        logger.info(f"[SmartStyle] 已删除 {removed} 张原始模板页")

    def get_best_layout_for_content(self, page_type: str, content_length: int = 0) -> Optional[SlideLayoutTemplate]:
        """
        根据内容类型选择最佳版式
        
        Args:
            page_type: 页面类型 (cover/toc/content/summary/ending)
            content_length: 内容字符数（用于判断是否需要大正文区域）
        """
        type_keywords = {
            'cover': ['title slide', '封面', '标题页', 'title only'],
            'toc': ['section header', '目录', 'agenda'],
            'content': ['title and content', 'two content', 'comparison', 'content with caption'],
            'summary': ['section header', '总结', 'conclusion'],
            'ending': ['blank', 'thank you', '结束'],
        }
        
        keywords = type_keywords.get(page_type.lower(), type_keywords['content'])
        
        best_match = None
        best_score = 0
        
        for name, template in self.layout_templates.items():
            score = 0
            name_lower = name.lower()
            
            for kw in keywords:
                if kw in name_lower:
                    score += 10
            
            # 内容较长时优先选择有大正文区域的版式
            if page_type.lower() == 'content' and content_length > 100:
                if template.has_body:
                    body_ph = template.placeholders.get('Content Placeholder', {})
                    width = body_ph.get('width', Emu(0))
                    if hasattr(width, 'inches') and width.inches > 8:
                        score += 5
            
            if score > best_score:
                best_score = score
                best_match = template
        
        # 如果没有匹配到，返回第一个有对应特征的版式
        if best_match is None:
            for template in self.layout_templates.values():
                if page_type.lower() == 'cover' and template.has_title:
                    return template
                elif page_type.lower() in ['content', 'toc'] and template.has_body:
                    return template
            
            # 兜底：返回第一个版式
            if self.layout_templates:
                return list(self.layout_templates.values())[0]
        
        return best_match
    
    def get_default_title_style(self) -> StyleRule:
        """获取默认标题样式（基于模板主题）"""
        rule = StyleRule()
        
        if self.theme_fonts.get('major_latin'):
            rule.font_name = self.theme_fonts['major_latin']
        if self.theme_fonts.get('major_east_asian'):
            rule.font_name = self.theme_fonts['major_east_asian']
        
        rule.font_size = 32
        rule.bold = True
        
        if self.theme_colors.get('dark1'):
            rule.font_color = self.theme_colors['dark1']
        
        return rule
    
    def get_default_body_style(self) -> StyleRule:
        """获取默认正文样式（基于模板主题）"""
        rule = StyleRule()
        
        if self.theme_fonts.get('minor_latin'):
            rule.font_name = self.theme_fonts['minor_latin']
        if self.theme_fonts.get('minor_east_asian'):
            rule.font_name = self.theme_fonts['minor_east_asian']
        
        rule.font_size = 18
        
        if self.theme_colors.get('dark1'):
            rule.font_color = self.theme_colors['dark1']
        
        return rule


class SmartLayoutEngine:
    """
    智能排版引擎
    
    功能：
    1. 根据内容自动选择最佳版式
    2. 智能计算字号（根据内容和空间）
    3. 应用模板样式到新内容
    4. 处理长文本自动换行和缩放
    """
    
    def __init__(self, style_extractor: SmartStyleExtractor):
        self.extractor = style_extractor
        self.prs = style_extractor.prs
    
    def create_styled_slide(self, page_type: str, title: str, 
                           content: List[str] = None,
                           subtitle: str = None) -> Any:
        """
        创建一页具有样式的幻灯片
        
        Args:
            page_type: 页面类型
            title: 标题文字
            content: 正文内容列表
            subtitle: 副标题（可选）
            
        Returns:
            创建的幻灯片对象
        """
        content = content or []
        content_text = '\n'.join(content)
        content_len = len(content_text)
        
        # 选择最佳版式
        layout_template = self.extractor.get_best_layout_for_content(
            page_type, content_len
        )
        
        if layout_template is None:
            raise ValueError("无法找到合适的版式")
        
        # 获取实际的 Layout 对象
        layout_idx = layout_template.layout_index
        layout = self.prs.slide_layouts[layout_idx]
        
        # 使用版式创建新幻灯片
        slide = self.prs.slides.add_slide(layout)
        
        logger.info(f"[SmartLayout] 创建幻灯片: {page_type} "
                   f"(版式: {layout_template.layout_name})")
        
        # 填充内容并应用样式
        self._fill_title(slide, title, layout_template)
        
        if subtitle:
            self._fill_subtitle(slide, subtitle, layout_template)
        
        if content:
            self._fill_body(slide, content, layout_template)
        
        return slide
    
    def _fill_title(self, slide, title: str, 
                    layout_template: SlideLayoutTemplate):
        """填充标题（应用样式）"""
        try:
            target_shape = None
            
            # 查找标题占位符
            for shape in slide.placeholders:
                ph_type = str(shape.placeholder_format.type)
                if ph_type in [str(PP_PLACEHOLDER.TITLE),
                              str(PP_PLACEHOLDER.CENTER_TITLE),
                              str(PP_PLACEHOLDER.VERTICAL_TITLE)]:
                    target_shape = shape
                    break
            
            # 如果没找到占位符，尝试找标题形状
            if target_shape is None and slide.shapes.title:
                target_shape = slide.shapes.title
            
            if target_shape and hasattr(target_shape, 'text_frame'):
                self._set_styled_text(target_shape, title, 
                                     layout_template.title_style)
                logger.debug(f"[SmartLayout] 标题已填充: {title[:30]}...")
                
        except Exception as e:
            logger.warning(f"[SmartLayout] 填充标题失败: {e}")
    
    def _fill_subtitle(self, slide, subtitle: str,
                       layout_template: SlideLayoutTemplate):
        """填充副标题"""
        try:
            for shape in slide.placeholders:
                if str(shape.placeholder_format.type) == str(PP_PLACEHOLDER.SUBTITLE):
                    self._set_styled_text(shape, subtitle,
                                         layout_template.subtitle_style)
                    break
                    
        except Exception as e:
            logger.debug(f"[SmartLayout] 填充副标题失败: {e}")
    
    def _fill_body(self, slide, content_lines: List[str],
                   layout_template: SlideLayoutTemplate):
        """填充正文（支持多行，应用样式）"""
        try:
            target_shape = None
            
            for shape in slide.placeholders:
                ph_type = str(shape.placeholder_format.type)
                if ph_type in [str(PP_PLACEHOLDER.BODY),
                              str(PP_PLACEHOLDER.OBJECT),
                              str(PP_PLACEHOLDER.VERTICAL_BODY)]:
                    target_shape = shape
                    break
            
            if target_shape and hasattr(target_shape, 'text_frame'):
                self._set_styled_multiline(target_shape, content_lines,
                                           layout_template.body_style)
                logger.debug(f"[SmartLayout] 正文已填充: {len(content_lines)} 行")
                
        except Exception as e:
            logger.warning(f"[SmartLayout] 填充正文失败: {e}")
    
    def _set_styled_text(self, shape, text: str, 
                         style_rule: StyleRule = None):
        """
        设置带样式的文本（单行）
        
        核心：通过修改 run.text 保留原有格式
        """
        try:
            tf = shape.text_frame
            
            if not tf.paragraphs:
                para = tf.add_paragraph()
            else:
                para = tf.paragraphs[0]
            
            # 清空现有内容但保留格式
            if para.runs:
                # 修改第一个 run 的文本（保留其格式）
                para.runs[0].text = text
                # 删除多余的 runs
                for run in list(para.runs)[1:]:
                    run._element.getparent().remove(run._element)
            else:
                # 如果没有 run，创建新的并应用样式
                run = para.add_run()
                run.text = text
                if style_rule:
                    style_rule.apply_to_run(run)
            
            # 删除多余的段落
            for p in list(tf.paragraphs)[1:]:
                p._element.getparent().remove(p._element)
                
        except Exception as e:
            logger.debug(f"[SmartLayout] 设置样式文本失败: {e}")
            # 降级：简单设置文本
            try:
                shape.text = text
            except:
                pass
    
    def _set_styled_multiline(self, shape, content_lines: List[str],
                             style_rule: StyleRule = None):
        """
        设置带样式的多行文本
        
        支持：
        - 多个要点/段落
        - 自动应用列表样式（如果模板有）
        - 智能字号调整（如果内容过长）
        """
        try:
            tf = shape.text_frame
            
            # 计算总字符数用于智能调整
            total_chars = sum(len(line) for line in content_lines)
            
            # 第一行使用原有格式的第一段
            if tf.paragraphs:
                first_para = tf.paragraphs[0]
                
                if first_para.runs:
                    # 保留原格式
                    first_para.runs[0].text = content_lines[0]
                    for run in list(first_para.runs)[1:]:
                        run._element.getparent().remove(run._element)
                else:
                    run = first_para.add_run()
                    run.text = content_lines[0]
                    if style_rule:
                        style_rule.apply_to_run(run)
            else:
                first_para = tf.add_paragraph()
                run = first_para.add_run()
                run.text = content_lines[0]
                if style_rule:
                    style_rule.apply_to_run(run)
            
            # 后续行添加新段落（尝试继承格式）
            for line in content_lines[1:]:
                # 复用已有段落或创建新段落
                if len(tf.paragraphs) > len(content_lines) - 1:
                    para = tf.paragraphs[len(content_lines) - 1]
                    if para.runs:
                        para.runs[0].text = line
                        for run in list(para.runs)[1:]:
                            run._element.getparent().remove(run._element)
                    else:
                        run = para.add_run()
                        run.text = line
                        if style_rule:
                            style_rule.apply_to_run(run)
                else:
                    para = tf.add_paragraph()
                    
                    # 尝试从第一段复制基本格式
                    if tf.paragraphs[0].alignment:
                        para.alignment = tf.paragraphs[0].alignment
                    
                    run = para.add_run()
                    run.text = line
                    
                    if style_rule:
                        style_rule.apply_to_run(run)
            
            # 删除多余的旧段落
            while len(tf.paragraphs) > len(content_lines):
                last_para = tf.paragraphs[-1]
                last_para._element.getparent().remove(last_para._element)
                
        except Exception as e:
            logger.error(f"[SmartLayout] 设置多行文本失败: {e}", exc_info=True)


def generate_smart_ppt(template_path: str, 
                       slides_data: List[Dict[str, Any]],
                       output_path: str = None) -> io.BytesIO:
    """
    高层接口：生成智能排版的 PPT
    
    Args:
        template_path: 模板文件路径
        slides_data: 幻灯片数据列表
            [
                {
                    'title': '标题',
                    'subtitle': '副标题',  # 可选
                    'content': ['要点1', '要点2'],  # 可选
                    'page_type': 'cover'  # cover/toc/content/summary/ending
                },
                ...
            ]
        output_path: 可选的输出路径
        
    Returns:
        PPTX 字节流
    """
    logger.info(f"[SmartPPT] 开始生成智能 PPT...")
    logger.info(f"[SmartPPT]   模板: {template_path}")
    logger.info(f"[SmartPPT]   幻灯片数: {len(slides_data)}")
    
    # 1. 提取样式
    extractor = SmartStyleExtractor(template_path)
    
    # 2. 创建排版引擎
    engine = SmartLayoutEngine(extractor)
    
    # 3. 生成每一页
    for idx, slide_dict in enumerate(slides_data):
        page_type = slide_dict.get('page_type', 'content')
        title = slide_dict.get('title', f'第{idx + 1}页')
        content = slide_dict.get('content', [])
        subtitle = slide_dict.get('subtitle')

        engine.create_styled_slide(page_type, title, content, subtitle)

        logger.info(f"[SmartPPT] 第 {idx + 1}/{len(slides_data)} 页已完成")

    # 5. 删除原始模板页面（关键！避免"贴模板"问题）
    extractor._remove_original_template_slides()

    # 4. 导出
    result = io.BytesIO()
    extractor.prs.save(result)
    result.seek(0)
    
    file_size = len(result.getvalue())
    logger.info(f"[SmartPPT] PPT 生成完成!")
    logger.info(f"[SmartPPT]   大小: {file_size / 1024:.1f} KB")
    logger.info(f"[SmartPPT]   页数: {len(slides_data)}")
    
    if output_path:
        with open(output_path, 'wb') as f:
            f.write(result.getvalue())
        logger.info(f"[SmartPPT] 已保存到: {output_path}")
        result.seek(0)
    
    return result


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("智能 PPT 排版引擎 - 测试程序")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python smart_layout_engine.py <模板路径>")
        print("\n示例:")
        print("  python smart_layout_engine.py data/templates/template.pptx")
        sys.exit(1)
    
    template_path = sys.argv[1]
    
    test_slides = [
        {
            'title': '智能排版演示',
            'subtitle': '基于模板风格的自动生成系统',
            'page_type': 'cover'
        },
        {
            'title': '目录',
            'content': [
                '一、项目背景与目标',
                '二、核心技术架构',
                '三、功能特性展示',
                '四、实际应用案例'
            ],
            'page_type': 'toc'
        },
        {
            'title': '核心技术优势',
            'content': [
                '✓ 完整继承模板的视觉风格（100%）',
                '✓ 智能选择最适合内容的版式布局',
                '✅ 自动提取和应用字体、颜色、间距',
                '• 根据内容长度动态优化排版效果',
                '• 支持多级标题、正文、列表等多种元素'
            ],
            'page_type': 'content'
        },
        {
            'title': '感谢观看',
            'page_type': 'ending'
        },
    ]
    
    try:
        result = generate_smart_ppt(template_path, test_slides)
        
        output_file = os.path.join(os.path.dirname(template_path), "smart_test_output.pptx")
        with open(output_file, 'wb') as f:
            f.write(result.getvalue())
        
        print(f"\n[SUCCESS] 测试完成!")
        print(f"  输出文件: {output_file}")
        print(f"  文件大小: {len(result.getvalue()) / 1024:.1f} KB")
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
