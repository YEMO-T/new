"""
PPT 模板风格克隆器 - 基于模板生成风格完全一致的 PPT

核心功能：
1. 解析模板 PPT，提取样式基因（母版/版式/占位符/颜色主题/字体规则）
2. 新建 PPT，完整克隆模板的母版和全部版式，不使用系统默认样式
3. 根据内容选择对应版式，向占位符填充内容，自动继承样式
4. 不手动创建字体、颜色、布局，全部继承模板
5. 最终 PPT 只改变内容，不改变任何视觉风格

使用 python-pptx 实现
"""

import os
import io
import copy
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from lxml import etree

from pptx import Presentation
from pptx.util import Pt, Inches, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn, nsmap
from pptx.oxml import parse_xml
from copy import deepcopy

logger = logging.getLogger(__name__)


class PageType(Enum):
    """页面类型枚举"""
    COVER = "cover"
    TOC = "toc"
    SECTION = "section"
    CONTENT = "content"
    TWO_CONTENT = "two_content"
    COMPARISON = "comparison"
    IMAGE = "image"
    QUOTE = "quote"
    CHART = "chart"
    TABLE = "table"
    SUMMARY = "summary"
    ENDING = "ending"
    BLANK = "blank"


@dataclass
class PlaceholderGene:
    """占位符基因信息"""
    idx: int
    ph_type: str  # title, body, picture, etc.
    name: str
    left: Emu
    top: Emu
    width: Emu
    height: Emu
    has_text_frame: bool


@dataclass
class LayoutGene:
    """版式基因信息"""
    index: int
    name: str
    placeholders: List[PlaceholderGene] = field(default_factory=list)
    has_title: bool = False
    has_body: bool = False
    has_picture: bool = False
    has_chart: bool = False
    has_table: bool = False
    
    def get_title_placeholder(self) -> Optional[PlaceholderGene]:
        for ph in self.placeholders:
            if ph.ph_type == 'title':
                return ph
        return None
    
    def get_body_placeholder(self) -> Optional[PlaceholderGene]:
        for ph in self.placeholders:
            if ph.ph_type == 'body':
                return ph
        return None


@dataclass
class ThemeGene:
    """主题基因信息"""
    color_scheme: Dict[str, str] = field(default_factory=dict)
    font_scheme: Dict[str, str] = field(default_factory=dict)
    effect_scheme: Dict[str, Any] = field(default_factory=dict)
    
    # 主要颜色
    accent1: Optional[str] = None
    accent2: Optional[str] = None
    accent3: Optional[str] = None
    accent4: Optional[str] = None
    accent5: Optional[str] = None
    accent6: Optional[str] = None
    dark1: Optional[str] = None
    light1: Optional[str] = None
    hyperlink: Optional[str] = None
    followed_hyperlink: Optional[str] = None
    
    # 字体设置
    major_font: Optional[str] = None
    minor_font: Optional[str] = None
    major_font_east_asian: Optional[str] = None
    minor_font_east_asian: Optional[str] = None


@dataclass
class SlideContentData:
    """幻灯片内容数据"""
    title: str = ""
    subtitle: str = ""
    content: List[str] = field(default_factory=list)
    page_type: PageType = PageType.CONTENT
    notes: str = ""
    
    # 可选的高级内容
    image_path: Optional[str] = None
    table_data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    quote_text: Optional[str] = None
    quote_author: Optional[str] = None


class TemplateStyleCloner:
    """
    PPT 模板风格克隆器
    
    核心原理：
    1. 深度解析模板 XML 结构，提取所有样式基因
    2. 通过 XML 级别复制，完整克隆母版和版式
    3. 使用模板原生版式创建新幻灯片
    4. 仅修改占位符内容，保留所有视觉样式
    """
    
    # 版式名称关键词映射（用于智能匹配）
    LAYOUT_KEYWORD_MAP = {
        PageType.COVER: [
            'title slide', '封面', '标题页', 'title only', 
            'cover', '封面页', '标题幻灯片', 'blank'
        ],
        PageType.TOC: [
            'toc', 'agenda', '目录', '目录页', 'content with table',
            'section header', '节标题'
        ],
        PageType.SECTION: [
            'section header', '章节', '节', 'section',
            'section title', 'divider'
        ],
        PageType.CONTENT: [
            'title and content', '正文', '标题和内容', 'content',
            'two content', '内容', 'bullet', 'text'
        ],
        PageType.TWO_CONTENT: [
            'two content', '两栏', '双栏', 'comparison',
            '2 content', 'dual', '并排'
        ],
        PageType.COMPARISON: [
            'comparison', '对比', 'compare',
            'before after', 'versus'
        ],
        PageType.IMAGE: [
            'picture with caption', '图片', 'image',
            'photo', 'full page', 'picture'
        ],
        PageType.QUOTE: [
            'quote', '引用', 'citation', '名言'
        ],
        PageType.CHART: [
            'chart', '图表', 'graph', 'data'
        ],
        PageType.TABLE: [
            'table', '表格', 'grid', 'matrix'
        ],
        PageType.SUMMARY: [
            'summary', '总结', 'conclusion', '结束',
            'closing', 'key points', '要点'
        ],
        PageType.ENDING: [
            'blank', '空白', 'ending', 'closing', 'thank',
            '致谢', '感谢', 'thank you', 'end'
        ],
        PageType.BLANK: [
            'blank', '空白', 'empty', 'clear'
        ]
    }
    
    def __init__(self, template_path: str):
        """
        初始化模板风格克隆器
        
        Args:
            template_path: 模板 PPT 文件路径
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        self.template_path = template_path
        self.template_prs: Optional[Presentation] = None
        
        # 提取的样式基因
        self.theme_gene: Optional[ThemeGene] = None
        self.layout_genes: List[LayoutGene] = []
        self.master_xml_element = None
        self._original_slide_count = 0
        
        # 新建的演示文稿
        self.new_prs: Optional[Presentation] = None
        
        self._load_and_extract()
    
    def _load_and_extract(self):
        """加载模板并提取样式基因"""
        logger.info(f"[StyleCloner] 开始加载模板: {self.template_path}")
        
        try:
            self.template_prs = Presentation(self.template_path)
            self._original_slide_count = len(self.template_prs.slides)
            
            # 提取主题基因
            self._extract_theme_gene()
            
            # 提取版式基因
            self._extract_layout_genes()
            
            # 保存母版 XML 元素（用于后续克隆）
            self._extract_master_xml()
            
            logger.info(f"[StyleCloner] 模板加载完成:")
            logger.info(f"  - 母版数量: {len(self.template_prs.slide_masters)}")
            logger.info(f"  - 版式数量: {len(self.layout_genes)}")
            logger.info(f"  - 原始幻灯片: {self._original_slide_count} 张")
            
            if self.theme_gene:
                logger.info(f"  - 主色调: {self.theme_gene.accent1 or 'N/A'}")
                logger.info(f"  - 主字体: {self.theme_gene.major_font or 'N/A'}")
                
        except Exception as e:
            logger.error(f"[StyleCloner] 加载模板失败: {e}", exc_info=True)
            raise
    
    def _extract_theme_gene(self):
        """提取主题基因（颜色方案、字体方案等）"""
        try:
            self.theme_gene = ThemeGene()
            
            # 获取主题部分
            theme_part = self.template_prs.part
            if hasattr(theme_part, '_element'):
                theme_el = theme_part._element
                
                # 尝试从演示文稿的主题中提取
                pass
            
            # 从幻灯片母版提取主题信息
            for master in self.template_prs.slide_masters:
                master_el = master._element
                
                # 提取颜色方案
                clr_scheme = master_el.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}clrScheme')
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
                            attr_name = color_map[tag_local]
                            srgb_child = child.find('{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
                            if srgb_child is not None:
                                val = srgb_child.get('val')
                                setattr(self.theme_gene, attr_name, val)
                                self.theme_gene.color_scheme[attr_name] = val
                
                # 提取字体方案
                font_scheme = master_el.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}fontScheme')
                if font_scheme is not None:
                    major_font = font_scheme.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}majorFont')
                    minor_font = font_scheme.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}minorFont')
                    
                    if major_font is not None:
                        latin = major_font.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}latin')
                        ea = major_font.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}ea')
                        if latin is not None:
                            self.theme_gene.major_font = latin.get('typeface')
                            self.theme_gene.font_scheme['major_latin'] = latin.get('typeface')
                        if ea is not None:
                            self.theme_gene.major_font_east_asian = ea.get('typeface')
                            self.theme_gene.font_scheme['major_ea'] = ea.get('typeface')
                    
                    if minor_font is not None:
                        latin = minor_font.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}latin')
                        ea = minor_font.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}ea')
                        if latin is not None:
                            self.theme_gene.minor_font = latin.get('typeface')
                            self.theme_gene.font_scheme['minor_latin'] = latin.get('typeface')
                        if ea is not None:
                            self.theme_gene.minor_font_east_asian = ea.get('typeface')
                            self.theme_gene.font_scheme['minor_ea'] = ea.get('typeface')
                
                break  # 只处理第一个母版
                
        except Exception as e:
            logger.warning(f"[StyleCloner] 提取主题基因失败: {e}")
            self.theme_gene = ThemeGene()
    
    def _extract_layout_genes(self):
        """提取版式基因"""
        self.layout_genes = []
        
        for idx, layout in enumerate(self.template_prs.slide_layouts):
            gene = LayoutGene(
                index=idx,
                name=layout.name,
                placeholders=[]
            )
            
            # 分析每个占位符
            for shape in layout.placeholders:
                try:
                    ph_type = self._classify_placeholder(shape)
                    ph_gene = PlaceholderGene(
                        idx=shape.placeholder_format.idx,
                        ph_type=ph_type,
                        name=shape.name,
                        left=shape.left,
                        top=shape.top,
                        width=shape.width,
                        height=shape.height,
                        has_text_frame=hasattr(shape, 'text_frame')
                    )
                    gene.placeholders.append(ph_gene)
                    
                    # 更新标志
                    if ph_type == 'title':
                        gene.has_title = True
                    elif ph_type == 'body':
                        gene.has_body = True
                    elif ph_type == 'picture':
                        gene.has_picture = True
                    elif ph_type == 'chart':
                        gene.has_chart = True
                    elif ph_type == 'table':
                        gene.has_table = True
                        
                except Exception as e:
                    logger.debug(f"[StyleCloner] 处理占位符失败: {e}")
            
            self.layout_genes.append(gene)
            logger.debug(f"[StyleCloner] 版式 [{idx}] {layout.name}: "
                        f"{len(gene.placeholders)} 个占位符, "
                        f"title={gene.has_title}, body={gene.has_body}")
    
    def _extract_master_xml(self):
        """提取母版 XML 元素用于克隆"""
        try:
            if self.template_prs.slide_masters:
                master = self.template_prs.slide_masters[0]
                self.master_xml_element = deepcopy(master._element)
                logger.debug("[StyleCloner] 母版 XML 已提取")
        except Exception as e:
            logger.warning(f"[StyleCloner] 提取母版XML失败: {e}")
    
    def _classify_placeholder(self, shape) -> str:
        """分类占位符类型"""
        try:
            ph_type = shape.placeholder_format.type
            type_mapping = {
                PP_PLACEHOLDER.TITLE: 'title',
                PP_PLACEHOLDER.CENTER_TITLE: 'title',
                PP_PLACEHOLDER.SUBTITLE: 'subtitle',
                PP_PLACEHOLDER.BODY: 'body',
                PP_PLACEHOLDER.OBJECT: 'body',
                PP_PLACEHOLDER.CONTENT: 'body',
                PP_PLACEHOLDER.VERTICAL_BODY: 'body',
                PP_PLACEHOLDER.VERTICAL_TITLE: 'title',
                PP_PLACEHOLDER.PICTURE: 'picture',
                PP_PLACEHOLDER.CHART: 'chart',
                PP_PLACEHOLDER.TABLE: 'table',
                PP_PLACEHOLDER.CLIP_ART: 'picture',
                PP_PLACEHOLDER.MEDIA: 'media',
                PP_PLACEHOLDER.DATE: 'date',
                PP_PLACEHOLDER.SLIDE_NUMBER: 'slide_number',
                PP_PLACEHOLDER.FOOTER: 'footer',
                PP_PLACEHOLDER.HEADER: 'header',
            }
            return type_mapping.get(ph_type, 'other')
        except Exception:
            return 'other'
    
    def clone_style_to_new_presentation(self) -> Presentation:
        """
        创建新演示文稿并完整克隆模板风格
        
        Returns:
            克隆了模板风格的新 Presentation 对象
        """
        logger.info("[StyleCloner] 开始克隆模板风格到新演示文稿...")
        
        # 方法：基于模板创建副本，然后清除幻灯片内容但保留母版和版式
        # 这是 python-pptx 最可靠的方式
        
        # 将模板加载到内存
        template_bytes = io.BytesIO()
        self.template_prs.save(template_bytes)
        template_bytes.seek(0)
        
        # 从模板字节流创建新的演示文稿
        self.new_prs = Presentation(template_bytes)
        
        # 清除原有幻灯片（但保留母版和版式）
        slides_to_remove = list(self.new_prs.slides)
        removed_count = 0
        
        for slide in slides_to_remove:
            try:
                rId = slide._element.get(qn('r:id'))
                
                # 获取 sldIdLst 元素（幻灯片ID列表）
                sld_id_lst = self.new_prs.part._element.find(qn('p:sldIdLst'))
                
                if sld_id_lst is not None:
                    # 找到对应的 sldId 元素并移除
                    for sld_id in list(sld_id_lst):
                        if sld_id.get(qn('r:id')) == rId:
                            sld_id_lst.remove(sld_id)
                            removed_count += 1
                            break
                
                # 清理关系文件
                try:
                    if rId and hasattr(self.new_prs.part, 'part_rels'):
                        rel = self.new_prs.part.part_rels.get(rId)
                        if rel is not None:
                            rel._target = None
                except Exception:
                    pass
                    
            except Exception as e:
                logger.debug(f"[StyleCloner] 移除幻灯片时出错: {e}")
                continue
        
        logger.info(f"[StyleCloner] 风格克隆完成:")
        logger.info(f"  - 新演示文稿已创建（继承模板风格）")
        logger.info(f"  - 清除了 {removed_count}/{len(slides_to_remove)} 张原始幻灯片")
        logger.info(f"  - 保留了 {len(self.new_prs.slide_layouts)} 个版式")
        logger.info(f"  - 保留了 {len(self.new_prs.slide_masters)} 个母版")
        
        return self.new_prs
    
    def select_best_layout(self, page_type: PageType) -> Tuple[Any, LayoutGene]:
        """
        根据页面类型智能选择最佳版式
        
        Args:
            page_type: 页面类型枚举
            
        Returns:
            (layout对象, layout基因信息) 元组
        """
        keywords = self.LAYOUT_KEYWORD_MAP.get(page_type, self.LAYOUT_KEYWORD_MAP[PageType.CONTENT])
        
        best_match = None
        best_score = 0
        best_gene = None
        
        for idx, layout in enumerate(self.new_prs.slide_layouts):
            gene = self.layout_genes[idx] if idx < len(self.layout_genes) else None
            if gene is None:
                continue
            
            layout_name_lower = layout.name.lower()
            score = 0
            
            # 关键词匹配评分
            for keyword in keywords:
                if keyword.lower() in layout_name_lower:
                    score += 10
                    if score > best_score:
                        best_score = score
                        best_match = layout
                        best_gene = gene
            
            # 特殊需求匹配加分
            if page_type == PageType.COVER and gene.has_title and not gene.has_body:
                score += 5
            elif page_type in [PageType.CONTENT, PageType.TWO_CONTENT] and gene.has_title and gene.has_body:
                score += 5
            elif page_type == PageType.IMAGE and gene.has_picture:
                score += 8
            elif page_type == PageType.TABLE and gene.has_table:
                score += 8
            elif page_type == PageType.CHART and gene.has_chart:
                score += 8
            
            if score > best_score:
                best_score = score
                best_match = layout
                best_gene = gene
        
        # 如果没有找到好的匹配，使用默认策略
        if best_match is None:
            # 尝试找有标题和内容的版式
            for idx, layout in enumerate(self.new_prs.slide_layouts):
                gene = self.layout_genes[idx] if idx < len(self.layout_genes) else None
                if gene and gene.has_title and gene.has_body:
                    return layout, gene
            
            # 最后使用第一个可用版式
            if self.new_prs.slide_layouts:
                return self.new_prs.slide_layouts[0], self.layout_genes[0]
        
        logger.debug(f"[StyleCloner] 选择版式: {best_match.name} (score={best_score}) for {page_type.value}")
        return best_match, best_gene
    
    def add_styled_slide(self, content_data: SlideContentData) -> Any:
        """
        添加一页风格一致的幻灯片
        
        Args:
            content_data: 幻灯片内容数据
            
        Returns:
            新创建的幻灯片对象
        """
        if self.new_prs is None:
            self.clone_style_to_new_presentation()
        
        # 选择最佳版式
        layout, layout_gene = self.select_best_layout(content_data.page_type)
        
        # 使用选定版式创建新幻灯片（自动继承模板风格）
        slide = self.new_prs.slides.add_slide(layout)
        
        # 填充内容到占位符（保持样式）
        self._fill_slide_content(slide, content_data, layout_gene)
        
        logger.info(f"[StyleCloner] 添加幻灯片: {content_data.title or content_data.page_type.value}"
                   f" (版式: {layout.name})")
        
        return slide
    
    def _fill_slide_content(self, slide, content_data: SlideContentData, layout_gene: LayoutGene):
        """
        向幻灯片填充内容（保持模板样式）
        
        核心：只修改占位符的文本内容，不改变任何格式属性
        """
        try:
            # 1. 填充标题
            if content_data.title and layout_gene.has_title:
                title_ph = layout_gene.get_title_placeholder()
                if title_ph:
                    self._set_placeholder_text(slide, title_ph.idx, content_data.title)
            
            # 2. 填充副标题
            if content_data.subtitle:
                for ph in layout_gene.placeholders:
                    if ph.ph_type == 'subtitle':
                        self._set_placeholder_text(slide, ph.idx, content_data.subtitle)
                        break
            
            # 3. 填充正文内容
            if content_data.content and layout_gene.has_body:
                body_ph = layout_gene.get_body_placeholder()
                if body_ph:
                    self._set_body_content(slide, body_ph.idx, content_data.content)
            
            # 4. 填充其他特殊内容
            if content_data.quote_text:
                self._fill_quote_content(slide, content_data)
            
            # 5. 添加备注
            if content_data.notes:
                try:
                    notes_slide = slide.notes_slide
                    notes_slide.notes_text_frame.text = content_data.notes
                except Exception as e:
                    logger.debug(f"[StyleCloner] 添加备注失败: {e}")
                    
        except Exception as e:
            logger.error(f"[StyleCloner] 填充幻灯片内容失败: {e}", exc_info=True)
    
    def _set_placeholder_text(self, slide, placeholder_idx: int, text: str):
        """
        设置占位符文本（保持原有样式）
        
        重要：只替换 run.text，不修改任何格式属性
        """
        try:
            target_shape = None
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == placeholder_idx:
                    target_shape = shape
                    break
            
            if target_shape and hasattr(target_shape, 'text_frame'):
                tf = target_shape.text_frame
                
                # 方法：清空现有段落，只保留第一段，然后设置文本
                # 这样可以保留段落的格式属性
                
                # 获取或创建第一个段落
                if tf.paragraphs:
                    para = tf.paragraphs[0]
                else:
                    para = tf.add_paragraph()
                
                # 如果有 runs，修改第一个 run 的文本；否则添加新 run
                if para.runs:
                    para.runs[0].text = text
                    # 删除多余的 runs
                    for run in list(para.runs)[1:]:
                        run._element.getparent().remove(run._element)
                else:
                    run = para.add_run()
                    run.text = text
                
                # 删除多余的段落（如果有）
                for p in list(tf.paragraphs)[1:]:
                    p._element.getparent().remove(p._element)
                
                logger.debug(f"[StyleCloner] 占位符[{placeholder_idx}] 文本已设置: {text[:30]}...")
                
        except Exception as e:
            logger.warning(f"[StyleCloner] 设置占位符文本失败: {e}")
    
    def _set_body_content(self, slide, placeholder_idx: int, content_lines: List[str]):
        """
        设置正文内容（支持多行/多要点）
        
        保持模板的列表样式（项目符号、缩进等）
        """
        try:
            target_shape = None
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == placeholder_idx:
                    target_shape = shape
                    break
            
            if target_shape and hasattr(target_shape, 'text_frame'):
                tf = target_shape.text_frame
                
                # 记录第一段的格式属性（用于复用）
                first_para_style = None
                if tf.paragraphs:
                    first_para = tf.paragraphs[0]
                    first_para_style = {
                        'level': first_para.level,
                        'alignment': first_para.alignment,
                        'space_before': first_para.space_before,
                        'space_after': first_para.space_after,
                    }
                
                # 清空现有内容
                for p in list(tf.paragraphs):
                    p._element.getparent().remove(p._element)
                
                # 添加新内容（每行一个段落）
                for i, line in enumerate(content_lines):
                    if i == 0:
                        para = tf.paragraphs[0] if tf.paragraphs else tf.add_paragraph()
                    else:
                        para = tf.add_paragraph()
                    
                    # 应用原始段落样式
                    if first_para_style:
                        para.level = first_para_style.get('level', 0)
                        if first_para_style.get('alignment'):
                            para.alignment = first_para_style['alignment']
                    
                    run = para.add_run()
                    run.text = line
                    
                    # 不设置 font 属性，让模板样式生效
                
                logger.debug(f"[StyleCloner] 正文占位符[{placeholder_idx}] 已填充 {len(content_lines)} 行")
                
        except Exception as e:
            logger.warning(f"[StyleCloner] 设置正文内容失败: {e}")
    
    def _fill_quote_content(self, slide, content_data: SlideContentData):
        """填充引用内容"""
        try:
            # 尝试找到正文占位符来放置引用
            for shape in slide.shapes:
                if hasattr(shape, 'text_frame') and shape.has_text_frame:
                    tf = shape.text_frame
                    if tf.paragraphs:
                        quote_text = content_data.quote_text or ""
                        if content_data.quote_author:
                            quote_text += f"\n— {content_data.quote_author}"
                        
                        if tf.paragraphs[0].runs:
                            tf.paragraphs[0].runs[0].text = quote_text
                        break
        except Exception as e:
            logger.debug(f"[StyleCloner] 填充引用内容失败: {e}")
    
    def generate_output(self, output_path: Optional[str] = None) -> io.BytesIO:
        """
        生成最终输出
        
        Args:
            output_path: 可选的保存路径
            
        Returns:
            PPTX 字节流
        """
        if self.new_prs is None:
            raise RuntimeError("请先调用 clone_style_to_new_presentation() 或 add_styled_slide()")
        
        pptx_io = io.BytesIO()
        self.new_prs.save(pptx_io)
        pptx_io.seek(0)
        
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(pptx_io.getvalue())
            logger.info(f"[StyleCloner] 文件已保存: {output_path}")
        
        file_size = len(pptx_io.getvalue())
        slide_count = len(self.new_prs.slides)
        logger.info(f"[StyleCloner] 生成完成: {file_size} 字节, {slide_count} 张幻灯片")
        
        return pptx_io
    
    def get_template_info(self) -> Dict[str, Any]:
        """获取模板信息摘要"""
        return {
            'template_path': self.template_path,
            'theme': {
                'major_font': self.theme_gene.major_font if self.theme_gene else None,
                'minor_font': self.theme_gene.minor_font if self.theme_gene else None,
                'accent1': self.theme_gene.accent1 if self.theme_gene else None,
                'color_count': len(self.theme_gene.color_scheme) if self.theme_gene else 0,
            } if self.theme_gene else {},
            'layouts': [
                {
                    'index': g.index,
                    'name': g.name,
                    'placeholders': len(g.placeholders),
                    'has_title': g.has_title,
                    'has_body': g.has_body,
                }
                for g in self.layout_genes
            ],
            'original_slides': self._original_slide_count
        }


# ============================================================
# 高层封装函数 - 方便外部调用
# ============================================================

def create_styled_ppt_from_template(
    template_path: str,
    slides_content: List[SlideContentData],
    output_path: Optional[str] = None
) -> io.BytesIO:
    """
    基于模板生成风格一致的高层函数
    
    Args:
        template_path: 模板 PPT 文件路径
        slides_content: 幻灯片内容列表
        output_path: 可选的输出路径
        
    Returns:
        生成的 PPTX 字节流
        
    Example:
        >>> slides = [
        ...     SlideContentData(
        ...         title="我的演示文稿",
        ...         subtitle="副标题",
        ...         page_type=PageType.COVER
        ...     ),
        ...     SlideContentData(
        ...         title="第一章",
        ...         content=["要点1", "要点2", "要点3"],
        ...         page_type=PageType.CONTENT
        ...     ),
        ...     SlideContentData(
        ...         title="谢谢",
        ...         page_type=PageType.ENDING
        ...     )
        ... ]
        >>> pptx_bytes = create_styled_ppt_from_template("template.pptx", slides)
    """
    cloner = TemplateStyleCloner(template_path)
    cloner.clone_style_to_new_presentation()
    
    for content in slides_content:
        cloner.add_styled_slide(content)
    
    return cloner.generate_output(output_path)


def render_with_template_style(
    template_path: str,
    slides_data: List[Dict[str, Any]],
    output_path: Optional[str] = None
) -> io.BytesIO:
    """
    兼容字典格式的渲染函数
    
    Args:
        template_path: 模板路径
        slides_data: 幻灯片字典列表，每项包含:
            - title: 标题
            - content: 内容列表
            - page_type: 页面类型字符串 ('cover', 'content', 'ending' 等)
            - subtitle: 副标题（可选）
        output_path: 输出路径（可选）
        
    Returns:
        PPTX 字节流
    """
    slides_content = []
    
    for slide_dict in slides_data:
        page_type_str = slide_dict.get('page_type', 'content').lower()
        try:
            page_type = PageType(page_type_str)
        except ValueError:
            page_type = PageType.CONTENT
        
        content = SlideContentData(
            title=slide_dict.get('title', ''),
            subtitle=slide_dict.get('subtitle', ''),
            content=slide_dict.get('content', []) if isinstance(slide_dict.get('content'), list) 
                  else [slide_dict.get('content', '')],
            page_type=page_type,
            notes=slide_dict.get('notes', '')
        )
        slides_content.append(content)
    
    return create_styled_ppt_from_template(template_path, slides_content, output_path)


# ============================================================
# 测试代码
# ============================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("PPT 模板风格克隆器 - 测试程序")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("用法: python ppt_template_style_cloner.py <模板路径>")
        print("示例: python ppt_template_style_cloner.py template.pptx")
        sys.exit(1)
    
    template_path = sys.argv[1]
    
    if not os.path.exists(template_path):
        print(f"错误: 模板文件不存在: {template_path}")
        sys.exit(1)
    
    try:
        # 1. 创建克隆器
        print("\n[1] 加载模板...")
        cloner = TemplateStyleCloner(template_path)
        
        # 2. 显示模板信息
        print("\n[2] 模板信息:")
        info = cloner.get_template_info()
        print(f"  主题字体: {info['theme'].get('major_font', 'N/A')}")
        print(f"  强调色1: {info['theme'].get('accent1', 'N/A')}")
        print(f"  版式数量: {len(info['layouts'])}")
        for layout in info['layouts']:
            print(f"    [{layout['index']}] {layout['name']} "
                  f"(占位符:{layout['placeholders']}, "
                  f"标题:{layout['has_title']}, "
                  f"正文:{layout['has_body']})")
        
        # 3. 克隆风格并添加测试内容
        print("\n[3] 生成测试幻灯片...")
        cloner.clone_style_to_new_presentation()
        
        test_slides = [
            SlideContentData(
                title="风格克隆测试",
                subtitle="基于模板生成的演示文稿",
                page_type=PageType.COVER
            ),
            SlideContentData(
                title="功能特点",
                content=[
                    "✓ 完整克隆模板母版和版式",
                    "✓ 继承所有颜色主题和字体规则",
                    "✓ 智能匹配最佳版式",
                    "✓ 只改内容，不改样式"
                ],
                page_type=PageType.CONTENT
            ),
            SlideContentData(
                title="技术实现",
                content=[
                    "• Python-pptx 底层 XML 操作",
                    "• 深拷贝母版元素结构",
                    "• 占位符文本精确替换",
                    "• 样式属性零干预"
                ],
                page_type=PageType.CONTENT
            ),
            SlideContentData(
                title="谢谢观看",
                page_type=PageType.ENDING
            ),
        ]
        
        for slide_data in test_slides:
            cloner.add_styled_slide(slide_data)
        
        # 4. 输出结果
        print("\n[4] 生成输出文件...")
        output_file = os.path.join(os.path.dirname(template_path), "styled_output.pptx")
        result = cloner.generate_output(output_file)
        
        print(f"\n{'=' * 60}")
        print("[SUCCESS] 风格克隆完成!")
        print(f"  输出文件: {output_file}")
        print(f"  文件大小: {len(result.getvalue()) / 1024:.1f} KB")
        print(f"  幻灯片数: {len(cloner.new_prs.slides)}")
        print(f"{'=' * 60}")
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
