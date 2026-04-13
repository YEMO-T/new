"""
PPT模板渲染器 - 完整版
核心功能：保留模板样式、直接修改内容、确保渲染效果
"""

import os
import io
import logging
import copy
from typing import List, Dict, Any, Optional, Union
from pptx import Presentation
from pptx.util import Pt, Inches, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree

from schema.chat_schema import PPTSlide

logger = logging.getLogger(__name__)


class PPTTemplateRenderer:
    """
    完整版PPT模板渲染引擎
    
    核心原理：
    1. 加载模板PPT，保留所有母版和版式
    2. 不清空模板幻灯片，直接修改内容
    3. 保留所有原有样式（背景、颜色、字体）
    4. 只替换文本内容，不改变任何格式
    """
    
    def __init__(self, template_path: str):
        if not os.path.exists(template_path):
            logger.error(f"模板文件不存在: {template_path}")
            raise FileNotFoundError(f"Template not found at {template_path}")
        
        self.template_path = template_path
        self.prs: Optional[Presentation] = None
        self.slide_layouts_info: Dict[str, Any] = {}
        self.original_slide_count = 0
        
        self._load_template()
    
    def _load_template(self):
        """加载模板"""
        try:
            self.prs = Presentation(self.template_path)
            self.original_slide_count = len(self.prs.slides)
            logger.info(f"[Renderer] 加载模板: {self.template_path}")
            logger.info(f"[Renderer] 母版数量: {len(self.prs.slide_masters)}")
            logger.info(f"[Renderer] 版式数量: {len(self.prs.slide_layouts)}")
            logger.info(f"[Renderer] 原有幻灯片: {self.original_slide_count} 张")
            
            self._extract_layouts_info()
            
        except Exception as e:
            logger.error(f"[Renderer] 加载模板失败: {type(e).__name__}: {e}")
            raise
    
    def _extract_layouts_info(self):
        """提取版式信息"""
        for idx, layout in enumerate(self.prs.slide_layouts):
            layout_info = {
                'index': idx,
                'name': layout.name,
                'has_title': False,
                'has_body': False,
                'has_subtitle': False,
            }
            
            for shape in layout.placeholders:
                ph_type = self._get_placeholder_type(shape)
                if ph_type == 'title':
                    layout_info['has_title'] = True
                elif ph_type == 'body':
                    layout_info['has_body'] = True
                elif ph_type == 'subtitle':
                    layout_info['has_subtitle'] = True
            
            self.slide_layouts_info[str(idx)] = layout_info
            self.slide_layouts_info[layout.name] = layout_info
    
    def _get_placeholder_type(self, shape) -> str:
        """获取占位符类型"""
        try:
            ph_type = shape.placeholder_format.type
            type_map = {
                PP_PLACEHOLDER.TITLE: 'title',
                PP_PLACEHOLDER.CENTER_TITLE: 'title',
                PP_PLACEHOLDER.SUBTITLE: 'subtitle',
                PP_PLACEHOLDER.BODY: 'body',
                PP_PLACEHOLDER.OBJECT: 'body',
                PP_PLACEHOLDER.VERTICAL_BODY: 'body',
                PP_PLACEHOLDER.VERTICAL_TITLE: 'title',
                PP_PLACEHOLDER.DATE: 'date',
                PP_PLACEHOLDER.SLIDE_NUMBER: 'slide_number',
                PP_PLACEHOLDER.FOOTER: 'footer',
            }
            return type_map.get(ph_type, 'other')
        except:
            return 'other'
    
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
        """
        替换形状中的文本，保留所有样式
        
        关键：不清空文本框，只替换第一个段落的文本
        """
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
            logger.warning(f"[Renderer] 替换文本失败: {e}")
            try:
                shape.text = new_text
            except:
                pass
    
    def _fill_body_content(self, shape, content: Union[str, List[str]]):
        """
        填充正文内容，保留样式
        
        关键：保留第一个段落的样式，复制到后续段落
        """
        try:
            if isinstance(content, str):
                content = [content] if content else []
            
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
            logger.warning(f"[Renderer] 填充正文失败: {e}")
            try:
                if isinstance(content, list):
                    shape.text = "\n".join(content)
                else:
                    shape.text = str(content)
            except:
                pass
    
    def _extract_paragraph_style(self, paragraph) -> Dict[str, Any]:
        """提取段落样式"""
        style = {
            'font_name': None,
            'font_size': None,
            'font_bold': None,
            'font_italic': None,
            'font_color': None,
            'alignment': None,
        }
        
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
            logger.debug(f"[Renderer] 提取段落样式失败: {e}")
        
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
            logger.debug(f"[Renderer] 应用段落样式失败: {e}")
    
    def fill_slide_content(self, slide, slide_data: PPTSlide):
        """
        填充幻灯片内容，保留所有样式
        
        核心逻辑：
        1. 找到标题占位符，直接替换文本
        2. 找到正文占位符，直接替换文本
        3. 不清空任何内容，保留原有格式
        """
        title = slide_data.title
        content = slide_data.content
        if isinstance(content, str):
            content = [content] if content else []
        
        title_filled = False
        body_filled = False
        
        for shape in slide.placeholders:
            ph_type = self._get_placeholder_type(shape)
            
            if ph_type == 'title' and not title_filled:
                self._replace_text_in_shape(shape, title)
                title_filled = True
                logger.debug(f"[Renderer] 填充标题: {title[:30]}...")
                
            elif ph_type == 'body' and not body_filled:
                self._fill_body_content(shape, content)
                body_filled = True
                logger.debug(f"[Renderer] 填充正文: {len(content)} 条")
        
        if not title_filled and slide.shapes.title:
            self._replace_text_in_shape(slide.shapes.title, title)
            logger.debug(f"[Renderer] 通过shapes.title填充标题")
    
    def render(self, slides_data: List[PPTSlide]) -> io.BytesIO:
        """
        全量渲染 PPT 并返回内存流
        
        策略：
        1. 如果模板有幻灯片，直接修改它们的内容
        2. 如果需要更多幻灯片，基于模板版式添加
        3. 如果模板幻灯片太多，删除多余的
        """
        logger.info(f"[Renderer] 开始渲染 {len(slides_data)} 页幻灯片")
        
        needed_slides = len(slides_data)
        current_slides = len(self.prs.slides)
        
        if current_slides > needed_slides:
            for i in range(current_slides - 1, needed_slides - 1, -1):
                rId = self.prs.slides._sldIdLst[i].rId
                self.prs.part.drop_rel(rId)
                del self.prs.slides._sldIdLst[i]
            logger.info(f"[Renderer] 删除了 {current_slides - needed_slides} 张多余幻灯片")
        
        for idx, slide_data in enumerate(slides_data):
            page_type = slide_data.page_type or 'content'
            
            if idx < current_slides:
                slide = self.prs.slides[idx]
                logger.info(f"[Renderer] 修改第 {idx + 1} 页: {page_type}")
            else:
                layout = self.get_layout_for_type(page_type)
                slide = self.prs.slides.add_slide(layout)
                logger.info(f"[Renderer] 新增第 {idx + 1} 页: {page_type}")
            
            self.fill_slide_content(slide, slide_data)
            logger.info(f"[Renderer] 完成 {page_type} - {slide_data.title[:20]}...")
        
        pptx_io = io.BytesIO()
        self.prs.save(pptx_io)
        pptx_io.seek(0)
        
        logger.info(f"[Renderer] 渲染完成，文件大小: {len(pptx_io.getvalue())} 字节")
        return pptx_io


def render_ppt_with_template(slides: List[PPTSlide], template_id: Optional[str] = None) -> io.BytesIO:
    """
    高层封装函数 - 基于模板渲染PPT
    
    Args:
        slides: PPTSlide 列表
        template_id: 模板ID（可选）
        
    Returns:
        PPTX 文件的字节流
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    template_path = None
    
    if template_id and template_id.strip():
        logger.info(f"[Renderer] 收到模板ID: {template_id}")
        template_path = os.path.join(base_dir, 'data', 'templates', f"{template_id}.pptx")
        if not os.path.exists(template_path):
            logger.info(f"[Renderer] 模板 {template_id} 不存在于本地，尝试从云端下载...")
            template_path = _download_template_from_cloud(template_id)
        else:
            logger.info(f"[Renderer] 使用本地模板: {template_path}")
    else:
        logger.info(f"[Renderer] 未提供模板ID，尝试使用默认模板")
    
    if not template_path:
        default_path = os.path.join(base_dir, 'data', 'templates', "default.pptx")
        if os.path.exists(default_path):
            template_path = default_path
            logger.info(f"[Renderer] 使用默认模板: {default_path}")
    
    if not template_path:
        logger.warning("[Renderer] 未找到任何模板，创建基础PPT")
        return _create_basic_pptx(slides)

    renderer = PPTTemplateRenderer(template_path)
    return renderer.render(slides)


def _download_template_from_cloud(template_id: str) -> Optional[str]:
    """从云端下载模板到本地"""
    try:
        from repository.supabase_client import get_supabase_client
        
        supabase = get_supabase_client()
        
        response = supabase.table('user_templates').select('*').eq('id', template_id).execute()
        
        if not response.data:
            logger.warning(f"[Renderer] 云端未找到模板: {template_id}")
            return None
        
        template_info = response.data[0]
        storage_path = template_info.get('file_path') or template_info.get('storage_path')
        
        if not storage_path:
            logger.warning(f"[Renderer] 模板 {template_id} 没有文件路径")
            return None
        
        bucket_name = template_info.get('file_bucket') or 'ppt-templates'
        
        logger.info(f"[Renderer] 从云端下载模板: bucket={bucket_name}, path={storage_path}")
        
        file_bytes = None
        
        try:
            file_bytes = supabase.storage.from_(bucket_name).download(storage_path)
            logger.info(f"[Renderer] 从 {bucket_name} 下载成功")
        except Exception as e:
            logger.warning(f"[Renderer] 从 {bucket_name} 下载失败: {e}")
            
            try:
                from service.storage_service import get_available_buckets
                available_buckets = get_available_buckets()
                
                for alt_bucket in available_buckets:
                    if alt_bucket == bucket_name:
                        continue
                    try:
                        file_bytes = supabase.storage.from_(alt_bucket).download(storage_path)
                        logger.info(f"[Renderer] 从 {alt_bucket} 下载成功")
                        break
                    except Exception:
                        continue
            except Exception:
                pass
        
        if not file_bytes:
            logger.error(f"[Renderer] 无法从云端下载模板: {template_id}")
            return None
        
        local_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'templates'
        )
        os.makedirs(local_dir, exist_ok=True)
        
        local_path = os.path.join(local_dir, f"{template_id}.pptx")
        
        with open(local_path, 'wb') as f:
            f.write(file_bytes)
        
        logger.info(f"[Renderer] 模板已下载到本地: {local_path}")
        return local_path
        
    except Exception as e:
        logger.error(f"[Renderer] 下载模板失败: {e}")
        return None


def _create_basic_pptx(slides: List[PPTSlide]) -> io.BytesIO:
    """创建基础PPT（无模板时的回退方案）"""
    from pptx import Presentation
    from pptx.util import Pt, Inches
    
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    
    for slide_data in slides:
        slide = prs.slides.add_slide(blank_layout)
        
        title = slide_data.title
        content = slide_data.content
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
