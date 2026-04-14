"""
PPT增强版模板渲染器
支持：图片占位符、表格填充、图表生成、模板变量替换
"""

import os
import io
import re
import logging
import base64
import tempfile
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum
from pptx import Presentation
from pptx.util import Pt, Inches, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.chart.data import CategoryChartData, ChartData
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree
import requests

logger = logging.getLogger(__name__)


class PlaceholderType(Enum):
    TITLE = "title"
    BODY = "body"
    PICTURE = "picture"
    TABLE = "table"
    CHART = "chart"
    SUBTITLE = "subtitle"
    OTHER = "other"


class ChartType(Enum):
    COLUMN_CLUSTERED = "column_clustered"
    COLUMN_STACKED = "column_stacked"
    BAR_CLUSTERED = "bar_clustered"
    BAR_STACKED = "bar_stacked"
    LINE = "line"
    LINE_MARKERS = "line_markers"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    AREA = "area"
    SCATTER = "scatter"


CHART_TYPE_MAP = {
    ChartType.COLUMN_CLUSTERED: XL_CHART_TYPE.COLUMN_CLUSTERED,
    ChartType.COLUMN_STACKED: XL_CHART_TYPE.COLUMN_STACKED,
    ChartType.BAR_CLUSTERED: XL_CHART_TYPE.BAR_CLUSTERED,
    ChartType.BAR_STACKED: XL_CHART_TYPE.BAR_STACKED,
    ChartType.LINE: XL_CHART_TYPE.LINE,
    ChartType.LINE_MARKERS: XL_CHART_TYPE.LINE_MARKERS,
    ChartType.PIE: XL_CHART_TYPE.PIE,
    ChartType.DOUGHNUT: XL_CHART_TYPE.DOUGHNUT,
    ChartType.AREA: XL_CHART_TYPE.AREA,
    ChartType.SCATTER: XL_CHART_TYPE.XY_SCATTER,
}


class ImagePlaceholder:
    """图片占位符数据"""
    def __init__(
        self,
        name: str,
        source: str,
        source_type: str = "url",
        width: Optional[float] = None,
        height: Optional[float] = None,
        fit: str = "contain"
    ):
        self.name = name
        self.source = source
        self.source_type = source_type
        self.width = width
        self.height = height
        self.fit = fit


class TableData:
    """表格数据"""
    def __init__(
        self,
        name: str,
        headers: List[str],
        rows: List[List[Any]],
        style: Optional[str] = None
    ):
        self.name = name
        self.headers = headers
        self.rows = rows
        self.style = style


class ChartDataModel:
    """图表数据"""
    def __init__(
        self,
        name: str,
        chart_type: ChartType,
        categories: List[str],
        series: List[Dict[str, Any]],
        title: Optional[str] = None,
        show_legend: bool = True,
        legend_position: str = "bottom"
    ):
        self.name = name
        self.chart_type = chart_type
        self.categories = categories
        self.series = series
        self.title = title
        self.show_legend = show_legend
        self.legend_position = legend_position


class EnhancedSlideData:
    """增强版幻灯片数据"""
    def __init__(
        self,
        title: str = "",
        content: Union[str, List[str]] = "",
        page_type: str = "content",
        variables: Optional[Dict[str, Any]] = None,
        images: Optional[List[ImagePlaceholder]] = None,
        tables: Optional[List[TableData]] = None,
        charts: Optional[List[ChartDataModel]] = None,
    ):
        self.title = title
        self.content = content if isinstance(content, list) else [content] if content else []
        self.page_type = page_type
        self.variables = variables or {}
        self.images = images or []
        self.tables = tables or []
        self.charts = charts or []


class EnhancedPPTRenderer:
    """
    增强版PPT模板渲染引擎
    
    功能：
    1. 图片占位符 - 支持URL、Base64、本地文件
    2. 表格填充 - 动态生成表格
    3. 图表生成 - 支持多种图表类型
    4. 模板变量替换 - {{变量名}} 格式
    """
    
    def __init__(self, template_path: str):
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        self.template_path = template_path
        self.prs: Optional[Presentation] = None
        self.slide_layouts_info: Dict[str, Any] = {}
        self.original_slide_count = 0
        self._temp_files: List[str] = []
        
        self._load_template()
    
    def _load_template(self):
        """加载模板"""
        try:
            self.prs = Presentation(self.template_path)
            self.original_slide_count = len(self.prs.slides)
            logger.info(f"[EnhancedRenderer] 加载模板: {self.template_path}")
            logger.info(f"[EnhancedRenderer] 母版数量: {len(self.prs.slide_masters)}")
            logger.info(f"[EnhancedRenderer] 版式数量: {len(self.prs.slide_layouts)}")
            logger.info(f"[EnhancedRenderer] 原有幻灯片: {self.original_slide_count} 张")
            
            self._extract_layouts_info()
            
        except Exception as e:
            logger.error(f"[EnhancedRenderer] 加载模板失败: {e}")
            raise
    
    def _extract_layouts_info(self):
        """提取版式信息"""
        for idx, layout in enumerate(self.prs.slide_layouts):
            layout_info = {
                'index': idx,
                'name': layout.name,
                'has_title': False,
                'has_body': False,
                'placeholders': []
            }
            
            for shape in layout.placeholders:
                ph_type = self._get_placeholder_type(shape)
                layout_info['placeholders'].append({
                    'idx': shape.placeholder_format.idx,
                    'type': ph_type.value,
                    'name': shape.name
                })
                
                if ph_type == PlaceholderType.TITLE:
                    layout_info['has_title'] = True
                elif ph_type == PlaceholderType.BODY:
                    layout_info['has_body'] = True
            
            self.slide_layouts_info[str(idx)] = layout_info
            self.slide_layouts_info[layout.name] = layout_info
    
    def _get_placeholder_type(self, shape) -> PlaceholderType:
        """获取占位符类型"""
        try:
            ph_type = shape.placeholder_format.type
            type_map = {
                PP_PLACEHOLDER.TITLE: PlaceholderType.TITLE,
                PP_PLACEHOLDER.CENTER_TITLE: PlaceholderType.TITLE,
                PP_PLACEHOLDER.SUBTITLE: PlaceholderType.SUBTITLE,
                PP_PLACEHOLDER.BODY: PlaceholderType.BODY,
                PP_PLACEHOLDER.OBJECT: PlaceholderType.BODY,
                PP_PLACEHOLDER.VERTICAL_BODY: PlaceholderType.BODY,
                PP_PLACEHOLDER.VERTICAL_TITLE: PlaceholderType.TITLE,
                PP_PLACEHOLDER.PICTURE: PlaceholderType.PICTURE,
            }
            return type_map.get(ph_type, PlaceholderType.OTHER)
        except:
            return PlaceholderType.OTHER
    
    def get_layout_for_type(self, page_type: str) -> Any:
        """根据页面类型智能选择布局"""
        page_type = (page_type or 'content').lower()
        
        type_keywords = {
            'cover': ['title slide', '封面', '标题页', 'title', 'cover', '封面页'],
            'toc': ['toc', 'agenda', '目录', '目录页'],
            'content': ['title and content', '正文', '标题和内容', 'content', 'two content', '内容'],
            'summary': ['section header', '总结', '结束', 'summary', 'closing'],
            'ending': ['blank', '空白', 'ending', 'closing', 'thank', '致谢', '感谢'],
        }
        
        keywords = type_keywords.get(page_type, type_keywords['content'])
        
        for idx, layout in enumerate(self.prs.slide_layouts):
            layout_name_lower = layout.name.lower()
            for keyword in keywords:
                if keyword in layout_name_lower:
                    return layout
        
        if page_type == 'cover':
            for idx, layout in enumerate(self.prs.slide_layouts):
                info = self.slide_layouts_info.get(str(idx), {})
                if info.get('has_title') and not info.get('has_body'):
                    return layout
        else:
            for idx, layout in enumerate(self.prs.slide_layouts):
                info = self.slide_layouts_info.get(str(idx), {})
                if info.get('has_title') and info.get('has_body'):
                    return layout
        
        return self.prs.slide_layouts[min(1, len(self.prs.slide_layouts) - 1)]
    
    def _replace_text_in_shape(self, shape, new_text: str):
        """替换形状中的文本，保留所有样式"""
        try:
            if not hasattr(shape, 'text_frame'):
                return
            
            tf = shape.text_frame
            
            if tf.paragraphs and len(tf.paragraphs) > 0:
                p = tf.paragraphs[0]
                p.text = new_text
                
                for i in range(len(tf.paragraphs) - 1, 0, -1):
                    p_remove = tf.paragraphs[i]
                    p_element = p_remove._p
                    p_element.getparent().remove(p_element)
            else:
                tf.text = new_text
                
        except Exception as e:
            logger.warning(f"[EnhancedRenderer] 替换文本失败: {e}")
            try:
                shape.text = new_text
            except:
                pass
    
    def _replace_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """替换模板变量 {{变量名}}"""
        if not text or not variables:
            return text
        
        def replace_match(match):
            var_name = match.group(1).strip()
            value = variables.get(var_name, match.group(0))
            return str(value)
        
        return re.sub(r'\{\{(\w+)\}\}', replace_match, text)
    
    def _apply_variables_to_shape(self, shape, variables: Dict[str, Any]):
        """对形状中的文本应用变量替换"""
        try:
            if not hasattr(shape, 'text_frame'):
                return
            
            tf = shape.text_frame
            for paragraph in tf.paragraphs:
                for run in paragraph.runs:
                    if run.text:
                        run.text = self._replace_variables(run.text, variables)
        except Exception as e:
            logger.debug(f"[EnhancedRenderer] 应用变量失败: {e}")
    
    def _download_image(self, source: str, source_type: str) -> Optional[bytes]:
        """下载或获取图片数据"""
        try:
            if source_type == "url":
                if not source or not source.startswith(('http://', 'https://')):
                    logger.warning(f"[EnhancedRenderer] 无效的图片URL: {source[:50]}")
                    return None
                response = requests.get(source, timeout=10, stream=True)
                response.raise_for_status()
                return response.content
            
            elif source_type == "base64":
                if "," in source:
                    source = source.split(",")[1]
                return base64.b64decode(source)
            
            elif source_type == "file":
                if not os.path.exists(source):
                    logger.warning(f"[EnhancedRenderer] 图片文件不存在: {source}")
                    return None
                with open(source, "rb") as f:
                    return f.read()
            
            else:
                logger.warning(f"[EnhancedRenderer] 不支持的图片源类型: {source_type}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"[EnhancedRenderer] 图片下载超时: {source[:50]}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"[EnhancedRenderer] 图片下载失败: {e}")
            return None
        except Exception as e:
            logger.error(f"[EnhancedRenderer] 获取图片异常: {e}")
            return None
    
    def _fill_image_placeholder(self, slide, image_data: ImagePlaceholder) -> bool:
        """填充图片占位符"""
        try:
            image_bytes = self._download_image(image_data.source, image_data.source_type)
            if not image_bytes:
                return False
            
            target_shape = None
            for shape in slide.shapes:
                shape_name_lower = shape.name.lower()
                if (image_data.name.lower() in shape_name_lower or
                    shape_name_lower in image_data.name.lower() or
                    shape.name == image_data.name):
                    target_shape = shape
                    break
            
            if not target_shape:
                for shape in slide.placeholders:
                    ph_type = self._get_placeholder_type(shape)
                    if ph_type == PlaceholderType.PICTURE:
                        target_shape = shape
                        break
            
            if target_shape:
                left = target_shape.left
                top = target_shape.top
                width = target_shape.width
                height = target_shape.height
                
                sp = target_shape._element
                sp.getparent().remove(sp)
                
                image_stream = io.BytesIO(image_bytes)
                
                if image_data.fit == "fill":
                    slide.shapes.add_picture(image_stream, left, top, width, height)
                elif image_data.fit == "cover":
                    slide.shapes.add_picture(image_stream, left, top, width, height)
                else:
                    slide.shapes.add_picture(image_stream, left, top)
                
                logger.info(f"[EnhancedRenderer] 图片填充成功: {image_data.name}")
                return True
            else:
                left = Inches(1)
                top = Inches(2)
                image_stream = io.BytesIO(image_bytes)
                slide.shapes.add_picture(image_stream, left, top)
                logger.info(f"[EnhancedRenderer] 图片添加到默认位置: {image_data.name}")
                return True
                
        except Exception as e:
            logger.error(f"[EnhancedRenderer] 填充图片失败: {e}")
            return False
    
    def _fill_table(self, slide, table_data: TableData) -> bool:
        """填充表格"""
        try:
            target_shape = None
            for shape in slide.shapes:
                if shape.has_table:
                    if table_data.name.lower() in shape.name.lower():
                        target_shape = shape
                        break
            
            if not target_shape:
                for shape in slide.shapes:
                    if shape.has_table:
                        target_shape = shape
                        break
            
            if target_shape:
                table = target_shape.table
                
                rows_needed = len(table_data.rows) + 1
                cols_needed = len(table_data.headers)
                
                current_rows = len(table.rows)
                current_cols = len(table.columns)
                
                for col_idx, header in enumerate(table_data.headers):
                    if col_idx < current_cols:
                        cell = table.cell(0, col_idx)
                        cell.text = str(header)
                        self._style_table_header_cell(cell)
                
                for row_idx, row_data in enumerate(table_data.rows):
                    actual_row = row_idx + 1
                    
                    if actual_row >= current_rows:
                        continue
                    
                    for col_idx, cell_data in enumerate(row_data):
                        if col_idx < current_cols:
                            cell = table.cell(actual_row, col_idx)
                            cell.text = str(cell_data)
                
                logger.info(f"[EnhancedRenderer] 表格填充成功: {table_data.name}")
                return True
            else:
                rows = len(table_data.rows) + 1
                cols = len(table_data.headers)
                
                left = Inches(0.5)
                top = Inches(2)
                width = Inches(12)
                height = Inches(0.5 * rows)
                
                table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
                table = table_shape.table
                
                for col_idx, header in enumerate(table_data.headers):
                    cell = table.cell(0, col_idx)
                    cell.text = str(header)
                    self._style_table_header_cell(cell)
                
                for row_idx, row_data in enumerate(table_data.rows):
                    for col_idx, cell_data in enumerate(row_data):
                        cell = table.cell(row_idx + 1, col_idx)
                        cell.text = str(cell_data)
                
                logger.info(f"[EnhancedRenderer] 新建表格成功: {table_data.name}")
                return True
                
        except Exception as e:
            logger.error(f"[EnhancedRenderer] 填充表格失败: {e}")
            return False
    
    def _style_table_header_cell(self, cell):
        """设置表头单元格样式"""
        try:
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0x4F, 0x81, 0xBD)
            
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.bold = True
                paragraph.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                paragraph.alignment = PP_ALIGN.CENTER
        except Exception as e:
            logger.debug(f"[EnhancedRenderer] 设置表头样式失败: {e}")
    
    def _fill_chart(self, slide, chart_data: ChartDataModel) -> bool:
        """填充图表"""
        try:
            target_shape = None
            for shape in slide.shapes:
                if shape.has_chart:
                    if chart_data.name.lower() in shape.name.lower():
                        target_shape = shape
                        break
            
            chart_type = CHART_TYPE_MAP.get(chart_data.chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)
            
            data = CategoryChartData()
            data.categories = chart_data.categories
            
            for series in chart_data.series:
                series_name = series.get('name', '')
                series_values = series.get('values', [])
                data.add_series(series_name, series_values)
            
            if target_shape:
                chart = target_shape.chart
                
                left = target_shape.left
                top = target_shape.top
                width = target_shape.width
                height = target_shape.height
                
                sp = target_shape._element
                sp.getparent().remove(sp)
                
                chart_shape = slide.shapes.add_chart(
                    chart_type, left, top, width, height, data
                )
                chart = chart_shape.chart
                
            else:
                left = Inches(1)
                top = Inches(2)
                width = Inches(10)
                height = Inches(5)
                
                chart_shape = slide.shapes.add_chart(
                    chart_type, left, top, width, height, data
                )
                chart = chart_shape.chart
            
            if chart_data.title:
                chart.has_title = True
                chart.chart_title.text_frame.text = chart_data.title
            
            if chart_data.show_legend:
                chart.has_legend = True
                legend_positions = {
                    "bottom": XL_LEGEND_POSITION.BOTTOM,
                    "top": XL_LEGEND_POSITION.TOP,
                    "left": XL_LEGEND_POSITION.LEFT,
                    "right": XL_LEGEND_POSITION.RIGHT,
                }
                chart.legend.position = legend_positions.get(
                    chart_data.legend_position, XL_LEGEND_POSITION.BOTTOM
                )
            
            logger.info(f"[EnhancedRenderer] 图表填充成功: {chart_data.name}")
            return True
            
        except Exception as e:
            logger.error(f"[EnhancedRenderer] 填充图表失败: {e}")
            return False
    
    def _fill_body_content(self, shape, content: List[str]):
        """填充正文内容，保留样式"""
        try:
            if not content:
                return
            
            tf = shape.text_frame
            
            if tf.paragraphs and len(tf.paragraphs) > 0:
                first_p = tf.paragraphs[0]
                style_info = self._extract_paragraph_style(first_p)
                first_p.text = str(content[0])
                
                for i in range(len(tf.paragraphs) - 1, 0, -1):
                    p_element = tf.paragraphs[i]._p
                    p_element.getparent().remove(p_element)
                
                for i, text in enumerate(content[1:], 1):
                    new_p = tf.add_paragraph()
                    new_p.text = str(text)
                    new_p.level = 0
                    self._apply_paragraph_style(new_p, style_info)
            else:
                for i, text in enumerate(content):
                    if i == 0:
                        p = tf.paragraphs[0] if tf.paragraphs else tf.add_paragraph()
                    else:
                        p = tf.add_paragraph()
                    p.text = str(text)
                    
        except Exception as e:
            logger.warning(f"[EnhancedRenderer] 填充正文失败: {e}")
            try:
                shape.text = "\n".join(content)
            except:
                pass
    
    def _extract_paragraph_style(self, paragraph) -> Dict[str, Any]:
        """提取段落样式"""
        style = {}
        try:
            if paragraph.font.name:
                style['font_name'] = paragraph.font.name
            if paragraph.font.size:
                style['font_size'] = paragraph.font.size
            if paragraph.font.bold is not None:
                style['font_bold'] = paragraph.font.bold
            if paragraph.font.italic is not None:
                style['font_italic'] = paragraph.font.italic
            try:
                if paragraph.font.color.rgb:
                    style['font_color'] = paragraph.font.color.rgb
            except:
                pass
            if paragraph.alignment is not None:
                style['alignment'] = paragraph.alignment
        except Exception as e:
            logger.debug(f"[EnhancedRenderer] 提取段落样式失败: {e}")
        return style
    
    def _apply_paragraph_style(self, paragraph, style: Dict[str, Any]):
        """应用段落样式"""
        try:
            if style.get('font_name'):
                paragraph.font.name = style['font_name']
            if style.get('font_size'):
                paragraph.font.size = style['font_size']
            if style.get('font_bold') is not None:
                paragraph.font.bold = style['font_bold']
            if style.get('font_italic') is not None:
                paragraph.font.italic = style['font_italic']
            if style.get('font_color'):
                try:
                    paragraph.font.color.rgb = style['font_color']
                except:
                    pass
            if style.get('alignment') is not None:
                paragraph.alignment = style['alignment']
        except Exception as e:
            logger.debug(f"[EnhancedRenderer] 应用段落样式失败: {e}")
    
    def fill_slide_content(self, slide, slide_data: EnhancedSlideData):
        """填充幻灯片内容（增强版 - 支持占位符和普通文本框）"""
        try:
            title = self._replace_variables(slide_data.title, slide_data.variables or {})
            content = [
                self._replace_variables(c, slide_data.variables or {}) 
                for c in slide_data.content
            ]
            
            title_filled = False
            body_filled = False
            
            for shape in slide.placeholders:
                try:
                    ph_type = self._get_placeholder_type(shape)
                    
                    if ph_type == PlaceholderType.TITLE and not title_filled:
                        self._replace_text_in_shape(shape, title)
                        title_filled = True
                        
                    elif ph_type == PlaceholderType.BODY and not body_filled:
                        self._fill_body_content(shape, content)
                        body_filled = True
                except Exception as e:
                    logger.warning(f"[EnhancedRenderer] 处理占位符失败: {e}")
                    continue
            
            if not title_filled and slide.shapes.title:
                try:
                    self._replace_text_in_shape(slide.shapes.title, title)
                    title_filled = True
                except Exception as e:
                    logger.debug(f"[EnhancedRenderer] 填充shapes.title失败: {e}")
            
            if not title_filled or not body_filled:
                text_shapes = []
                for shape in slide.shapes:
                    if hasattr(shape, 'text_frame') and shape.text_frame:
                        shape_name_lower = (shape.name or '').lower()
                        is_title_box = any(kw in shape_name_lower for kw in ['title', '标题', 'headline'])
                        is_content_box = any(kw in shape_name_lower for kw in ['content', '正文', 'body', 'text', '文本'])
                        
                        if is_title_box and not title_filled:
                            text_shapes.insert(0, ('title', shape))
                        elif is_content_box and not body_filled:
                            text_shapes.append(('content', shape))
                
                for stype, shape in text_shapes:
                    try:
                        if stype == 'title' and not title_filled:
                            self._replace_text_in_shape(shape, title)
                            title_filled = True
                            logger.info(f"[EnhancedRenderer] 通过文本框填充标题: {shape.name}")
                        elif stype == 'content' and not body_filled:
                            self._fill_body_content(shape, content)
                            body_filled = True
                            logger.info(f"[EnhancedRenderer] 通过文本框填充内容: {shape.name}")
                    except Exception as e:
                        logger.debug(f"[EnhancedRenderer] 填充文本框失败: {e}")
            
            if (not title_filled or not body_filled) and len(slide.shapes) <= 2:
                try:
                    from pptx.util import Inches, Pt
                    
                    if not title_filled:
                        left = Inches(0.5)
                        top = Inches(0.3)
                        width = Inches(12.333)
                        height = Inches(1.0)
                        title_box = slide.shapes.add_textbox(left, top, width, height)
                        tf = title_box.text_frame
                        tf.word_wrap = True
                        p = tf.paragraphs[0]
                        p.text = title
                        p.font.size = Pt(36)
                        p.font.bold = True
                        title_filled = True
                        logger.info("[EnhancedRenderer] 创建新标题框")
                    
                    if not body_filled and content:
                        left = Inches(0.5)
                        top = Inches(1.6)
                        width = Inches(12.333)
                        height = Inches(5.4)
                        body_box = slide.shapes.add_textbox(left, top, width, height)
                        tf = body_box.text_frame
                        tf.word_wrap = True
                        
                        for i, text in enumerate(content):
                            if i == 0:
                                p = tf.paragraphs[0]
                            else:
                                p = tf.add_paragraph()
                            p.text = str(text)
                            p.font.size = Pt(18)
                            p.space_after = Pt(12)
                        body_filled = True
                        logger.info("[EnhancedRenderer] 创建新内容框")
                        
                except Exception as create_err:
                    logger.error(f"[EnhancedRenderer] 创建文本框失败: {create_err}")
            
            for shape in slide.shapes:
                try:
                    if hasattr(shape, 'text_frame'):
                        self._apply_variables_to_shape(shape, slide_data.variables or {})
                except Exception as e:
                    logger.debug(f"[EnhancedRenderer] 应用变量失败: {e}")
                    continue
            
            for image_data in slide_data.images:
                try:
                    self._fill_image_placeholder(slide, image_data)
                except Exception as e:
                    logger.warning(f"[EnhancedRenderer] 填充图片失败: {e}")
                    continue
            
            for table_data in slide_data.tables:
                try:
                    self._fill_table(slide, table_data)
                except Exception as e:
                    logger.warning(f"[EnhancedRenderer] 填充表格失败: {e}")
                    continue
            
            for chart_data in slide_data.charts:
                try:
                    self._fill_chart(slide, chart_data)
                except Exception as e:
                    logger.warning(f"[EnhancedRenderer] 填充图表失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"[EnhancedRenderer] fill_slide_content 异常: {e}")
            raise
    
    def render(self, slides_data: List[EnhancedSlideData]) -> io.BytesIO:
        """渲染PPT（Add-then-Clean 策略：先添加用户页面，再删除所有原始模板页）"""
        logger.info(f"[EnhancedRenderer] 开始渲染 {len(slides_data)} 页幻灯片")

        for idx, slide_data in enumerate(slides_data):
            try:
                page_type = slide_data.page_type or 'content'
                layout = self.get_layout_for_type(page_type)
                slide = self.prs.slides.add_slide(layout)
                logger.info(f"[EnhancedRenderer] 新增第 {idx + 1} 页: {page_type}")

                self.fill_slide_content(slide, slide_data)
            except Exception as e:
                logger.error(f"[EnhancedRenderer] 渲染第 {idx + 1} 页失败: {e}")
                continue

        self._remove_original_template_slides()

        pptx_io = io.BytesIO()
        self.prs.save(pptx_io)
        pptx_io.seek(0)

        self._cleanup_temp_files()

        logger.info(f"[EnhancedRenderer] 渲染完成，文件大小: {len(pptx_io.getvalue())} 字节")
        return pptx_io

    def _remove_original_template_slides(self):
        """
        删除所有原始模板幻灯片
        
        使用 python-pptx 内部 API (prs.slides._sldIdLst) 直接操作
        """
        original_count = getattr(self, 'original_slide_count', 0)
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
                logger.warning(f"[EnhancedRenderer] 删除原始模板页出错: {e}")
                break

        logger.info(f"[EnhancedRenderer] 已删除 {removed} 张原始模板页")
    
    def _cleanup_temp_files(self):
        """清理临时文件"""
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.debug(f"[EnhancedRenderer] 清理临时文件失败: {e}")
        self._temp_files = []


def render_enhanced_ppt(
    slides: List[Dict[str, Any]],
    template_id: Optional[str] = None,
    template_path: Optional[str] = None
) -> io.BytesIO:
    """
    高层封装函数 - 增强版PPT渲染
    
    Args:
        slides: 幻灯片数据列表，支持以下字段：
            - title: 标题
            - content: 内容（字符串或列表）
            - page_type: 页面类型
            - variables: 变量字典 {"变量名": 值}
            - images: 图片列表 [{"name": "图片名", "source": "URL", "source_type": "url"}]
            - tables: 表格列表 [{"name": "表格名", "headers": [], "rows": [[]]}]
            - charts: 图表列表 [{"name": "图表名", "chart_type": "column_clustered", "categories": [], "series": []}]
        template_id: 模板ID
        template_path: 模板路径（优先使用）
        
    Returns:
        PPTX 文件的字节流
    """
    actual_template_path = template_path
    
    if not actual_template_path and template_id:
        actual_template_path = _resolve_template_path(template_id)
    
    if not actual_template_path:
        return _create_basic_pptx(slides)
    
    renderer = EnhancedPPTRenderer(actual_template_path)
    
    enhanced_slides = []
    for slide_dict in slides:
        enhanced_slide = _dict_to_enhanced_slide(slide_dict)
        enhanced_slides.append(enhanced_slide)
    
    return renderer.render(enhanced_slides)


def _resolve_template_path(template_id: str, timeout: int = 30) -> Optional[str]:
    """解析模板路径（支持本地文件 + Supabase 云端下载）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    local_path = os.path.join(base_dir, 'data', 'templates', f"{template_id}.pptx")
    if os.path.exists(local_path):
        logger.info(f"[EnhancedRenderer] 使用本地缓存: {local_path}")
        return local_path

    logger.info(f"[EnhancedRenderer] 本地未找到，尝试从云端下载 template_id={template_id}")

    try:
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table('user_templates').select(
            'id, file_path, file_bucket'
        ).eq('id', template_id).execute()

        if not response.data or len(response.data) == 0:
            logger.warning(f"[EnhancedRenderer] 数据库中未找到模板记录: {template_id}")
            return None

        template_info = response.data[0]
        storage_path = template_info.get('file_path')
        bucket_name = template_info.get('file_bucket', 'ppt-templates')

        if not storage_path:
            logger.warning(f"[EnhancedRenderer] 模板记录缺少 file_path: {template_info}")
            return None

        from service.storage_service import download_template_file

        file_bytes = download_template_file(bucket_name, storage_path)

        if not file_bytes:
            logger.warning(f"[EnhancedRenderer] 从 Storage 下载失败: bucket={bucket_name}, path={storage_path}")
            return None

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(file_bytes)

        logger.info(f"[EnhancedRenderer] 模板已下载并缓存: {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"[EnhancedRenderer] 下载模板异常: {e}", exc_info=True)
        return None


def _dict_to_enhanced_slide(slide_dict: Dict[str, Any]) -> EnhancedSlideData:
    """将字典转换为增强版幻灯片数据"""
    title = slide_dict.get('title', '')
    content = slide_dict.get('content', '')
    if isinstance(content, str):
        content = [content] if content else []
    page_type = slide_dict.get('page_type') or slide_dict.get('type', 'content')
    variables = slide_dict.get('variables') or {}
    
    images = []
    for img in slide_dict.get('images') or []:
        images.append(ImagePlaceholder(
            name=img.get('name', ''),
            source=img.get('source', ''),
            source_type=img.get('source_type', 'url'),
            width=img.get('width'),
            height=img.get('height'),
            fit=img.get('fit', 'contain')
        ))
    
    tables = []
    for tbl in slide_dict.get('tables') or []:
        tables.append(TableData(
            name=tbl.get('name', ''),
            headers=tbl.get('headers', []),
            rows=tbl.get('rows', []),
            style=tbl.get('style')
        ))
    
    charts = []
    for chart in slide_dict.get('charts') or []:
        chart_type_str = chart.get('chart_type', 'column_clustered')
        try:
            chart_type = ChartType(chart_type_str)
        except ValueError:
            chart_type = ChartType.COLUMN_CLUSTERED
        
        charts.append(ChartDataModel(
            name=chart.get('name', ''),
            chart_type=chart_type,
            categories=chart.get('categories', []),
            series=chart.get('series', []),
            title=chart.get('title'),
            show_legend=chart.get('show_legend', True),
            legend_position=chart.get('legend_position', 'bottom')
        ))
    
    return EnhancedSlideData(
        title=title,
        content=content,
        page_type=page_type,
        variables=variables,
        images=images,
        tables=tables,
        charts=charts
    )


def _create_basic_pptx(slides: List[Dict[str, Any]]) -> io.BytesIO:
    """创建基础PPT（无模板时的回退方案）"""
    from pptx import Presentation
    from pptx.util import Pt, Inches
    
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    
    for slide_data in slides:
        slide = prs.slides.add_slide(blank_layout)
        
        title = slide_data.get('title', '')
        content = slide_data.get('content', '')
        if isinstance(content, str):
            content = [content] if content else []
        
        left = Inches(0.5)
        top = Inches(0.5)
        width = Inches(12.333)
        height = Inches(1)
        
        title_box = slide.shapes.add_textbox(left, top, width, height)
        title_frame = title_box.text_frame
        title_frame.text = title
        if title_frame.paragraphs:
            title_frame.paragraphs[0].font.size = Pt(36)
            title_frame.paragraphs[0].font.bold = True
        
        if content:
            body_top = Inches(1.8)
            body_height = Inches(5)
            body_box = slide.shapes.add_textbox(left, body_top, width, body_height)
            body_frame = body_box.text_frame
            
            for i, text in enumerate(content):
                if i == 0:
                    p = body_frame.paragraphs[0]
                else:
                    p = body_frame.add_paragraph()
                p.text = str(text)
                p.font.size = Pt(18)
    
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output
