"""
Clean PPT Renderer — 模板渲染，只做一件事：在模板中填字
==========================================================

策略 v2（原地替换，不依赖删除操作）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ 旧策略（add_slide + delete）：
   打开模板 → add_slide 创建新页 → 删除原始页
   问题：删除操作不可靠，原始页残留遮挡用户内容

✅ 新策略（原地替换）：
   打开模板 → 直接在原始页上清空+填入用户内容
   用户页少则删多余、多则追加新页
   完全不存在"删除失败导致内容被遮"的问题

调用方式：
  from utils.clean_renderer import render_ppt_with_template_clean
  result = render_ppt_with_template_clean(slides_data, template_id)
"""

import os
import io
import logging
from typing import List, Dict, Any, Optional

from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn

logger = logging.getLogger(__name__)

TEMPLATE_CACHE_DIR = None


def _get_cache_dir() -> str:
    global TEMPLATE_CACHE_DIR
    if TEMPLATE_CACHE_DIR is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        TEMPLATE_CACHE_DIR = os.path.join(base, 'data', 'templates')
        os.makedirs(TEMPLATE_CACHE_DIR, exist_ok=True)
    return TEMPLATE_CACHE_DIR


def _download_template(template_id: str) -> Optional[str]:
    cache_dir = _get_cache_dir()
    local_path = os.path.join(cache_dir, f"{template_id}.pptx")

    if os.path.exists(local_path):
        file_size = os.path.getsize(local_path)
        logger.info(f"[CleanRender] 使用本地缓存: {local_path} ({file_size} 字节)")
        return local_path

    logger.info(f"[CleanRender] 本地未找到，从云端下载 template_id={template_id}")

    try:
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table('user_templates').select(
            'file_path, file_bucket'
        ).eq('id', template_id).execute()

        if not response.data or len(response.data) == 0:
            logger.warning(f"[CleanRender] 数据库中未找到模板记录: {template_id}")
            return None

        row = response.data[0]
        file_path = row.get('file_path')
        file_bucket = row.get('file_bucket')

        if not file_path or not file_bucket:
            logger.warning(f"[CleanRender] 模板记录缺少路径信息: bucket={file_bucket}, path={file_path}")
            return None

        file_data = supabase.storage.from_(file_bucket).download(file_path)

        if not file_data:
            logger.warning(f"[CleanRender] Storage 返回空数据: bucket={file_bucket}, path={file_path}")
            return None

        with open(local_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"[CleanRender] 下载成功并缓存: {local_path} ({len(file_data)} 字节)")
        return local_path

    except Exception as e:
        logger.error(f"[CleanRender] 下载模板异常: {e}", exc_info=True)
        return None


def _pick_layout(prs: Presentation, page_type: str):
    pt = (page_type or 'content').lower().strip()

    type_keywords = {
        'cover': ['title slide', 'cover', 'blank', 'title only'],
        'toc': ['toc', 'agenda', 'section header', 'two content'],
        'content': ['title and content', 'content', 'two content', 'comparison'],
        'summary': ['summary', 'conclusion', 'key points', 'two content'],
        'ending': ['blank', 'ending', 'thank', 'title only'],
    }

    keywords = type_keywords.get(pt, type_keywords['content'])

    best_layout = None
    best_score = -1

    for layout in prs.slide_layouts:
        name = (layout.name or '').lower()
        score = sum(2 for kw in keywords if kw in name)

        has_title = any(
            str(ph.placeholder_format.type) in (
                str(PP_PLACEHOLDER.TITLE),
                str(PP_PLACEHOLDER.CENTER_TITLE),
                str(PP_PLACEHOLDER.VERTICAL_TITLE),
            )
            for ph in layout.placeholders
        )

        has_body = any(
            str(ph.placeholder_format.type) in (
                str(PP_PLACEHOLDER.BODY),
                str(PP_PLACEHOLDER.OBJECT),
            )
            for ph in layout.placeholders
        )

        if pt == 'cover' and has_title and not has_body:
            score += 5
        elif pt in ('content', 'toc') and has_title and has_body:
            score += 5
        elif pt == 'ending' and has_title and not has_body:
            score += 5

        if score > best_score:
            best_score = score
            best_layout = layout

    if best_layout is None:
        best_layout = prs.slide_layouts[0]

    return best_layout


def _set_text_safe(tf, text: str):
    """安全地向 text_frame 设置文本"""
    try:
        if tf.paragraphs:
            para = tf.paragraphs[0]
            if para.runs:
                para.runs[0].text = text
                for r in list(para.runs)[1:]:
                    r._element.getparent().remove(r._element)
            else:
                run = para.add_run()
                run.text = text
            for p in list(tf.paragraphs)[1:]:
                p._element.getparent().remove(p._element)
        else:
            tf.text = text
    except Exception as e:
        try:
            tf.text = text
        except Exception:
            pass


def _set_body_safe(tf, lines: List[str]):
    """安全地向 text_frame 设置多行正文"""
    try:
        first_level = 0
        first_align = None
        if tf.paragraphs:
            p0 = tf.paragraphs[0]
            first_level = getattr(p0, 'level', 0)
            first_align = p0.alignment

        for old_para in list(tf.paragraphs):
            old_para._element.getparent().remove(old_para._element)

        for i, line in enumerate(lines):
            para = tf.paragraphs[0] if (i == 0 and tf.paragraphs) else tf.add_paragraph()
            para.level = first_level
            if first_align:
                para.alignment = first_align
            run = para.add_run() if not para.runs else para.runs[0]
            run.text = line
    except Exception as e:
        try:
            tf.text = '\n'.join(lines)
        except Exception:
            pass


def _fill_slide_placeholders(slide, title: str, subtitle: str, content: List[str]):
    """
    向幻灯片的占位符填入用户内容
    
    只修改占位符的文本，不改格式。字体/颜色/大小全部继承自模板。
    
    兜底策略：如果没有任何可填充的占位符，则使用页面上的文本框来填充。
    """
    title_filled = False
    subtitle_filled = False
    body_filled = False
    fallback_textboxes = []

    for shape in slide.placeholders:
        try:
            ph_type = str(shape.placeholder_format.type)

            if ph_type in (str(PP_PLACEHOLDER.TITLE), str(PP_PLACEHOLDER.CENTER_TITLE),
                           str(PP_PLACEHOLDER.VERTICAL_TITLE)):
                if title and not title_filled:
                    _set_text_safe(shape.text_frame, title)
                    title_filled = True

            elif ph_type == str(PP_PLACEHOLDER.SUBTITLE):
                if subtitle and not subtitle_filled:
                    _set_text_safe(shape.text_frame, subtitle)
                    subtitle_filled = True

            elif ph_type in (str(PP_PLACEHOLDER.BODY), str(PP_PLACEHOLDER.OBJECT)):
                if content and not body_filled:
                    _set_body_safe(shape.text_frame, content)
                    body_filled = True

        except Exception as e:
            logger.debug(f"[CleanRender] 填充占位符异常: name={shape.name}, err={e}")

    if not title_filled or not body_filled:
        for shape in list(slide.shapes):
            try:
                shape.placeholder_format
                continue
            except Exception:
                pass

            try:
                if not hasattr(shape, 'text_frame') or not shape.has_text_frame:
                    continue

                tf = shape.text_frame
                if not tf.text.strip() and (title_filled and body_filled):
                    continue

                if title and not title_filled:
                    _set_text_safe(tf, title)
                    title_filled = True
                    logger.debug(f"[CleanRender] 兜底填入标题到文本框: {shape.name}")
                    continue

                if subtitle and not subtitle_filled:
                    _set_text_safe(tf, subtitle)
                    subtitle_filled = True
                    continue

                if content and not body_filled:
                    _set_body_safe(tf, content)
                    body_filled = True
                    logger.debug(f"[CleanRender] 兜底填入正文到文本框: {shape.name}")

            except Exception as e:
                logger.debug(f"[CleanRender] 兜底填充异常: {e}")


def _clear_template_content_from_slide(slide):
    cleared_count = 0

    for shape in list(slide.shapes):
        try:
            name = getattr(shape, 'name', '?')
            has_tf = False
            tf_text = ''
            is_real_placeholder = False

            try:
                has_tf = bool(shape.has_text_frame)
                if has_tf:
                    tf_text = shape.text_frame.text[:50]
                ph = shape.placeholder_format
                is_real_placeholder = True
            except Exception:
                pass

            logger.debug(f"[CleanRender-Clear] name={name}, "
                        f"is_ph={is_real_placeholder}, "
                        f"has_tf={has_tf}, text='{tf_text}'")

            if not is_real_placeholder and has_tf and tf_text.strip():
                _clear_all_text(shape.text_frame)
                cleared_count += 1
                logger.info(f"[CleanRender-Clear] ✅ 已清空: {name}")

        except Exception as e:
            logger.debug(f"[CleanRender-Clear] 异常: {e}")

    if cleared_count > 0:
        logger.info(f"[CleanRender] 已清除 {cleared_count} 个文本框的模板残留内容")
    else:
        logger.warning(f"[CleanRender] ⚠️ 未清除任何文本框")


def _clear_all_text(tf):
    """彻底清空 text_frame 的所有文本"""
    try:
        for para in list(tf.paragraphs):
            for run in list(para.runs):
                run.text = ''
            if para.text:
                try:
                    para._element.getparent().remove(para._element)
                except Exception:
                    pass
        if tf.paragraphs and tf.text.strip():
            p = tf.add_paragraph() if not tf.paragraphs else tf.paragraphs[0]
            for r in list(p.runs):
                r.text = ''
    except Exception:
        pass


def _replace_slide_content(slide, title: str, subtitle: str, content: List[str]):
    """
    核心函数：原地替换一页幻灯片的全部内容
    
    策略：
    1. 先清除所有非占位符的示例文字（避免残留）
    2. 再向占位符填入用户内容（标题/副标题/正文）
       如果没有可用占位符，则使用文本框作为兜底
    
    这样既保留了模板的格式样式，又确保没有残留文字。
    """
    _clear_template_content_from_slide(slide)
    _fill_slide_placeholders(slide, title, subtitle, content)


def _remove_trailing_slides(prs: Presentation, keep_count: int):
    """
    从末尾删除多余的幻灯片
    
    比"从头删除"更安全——不会影响前面已填充的用户页面。
    只在用户页面少于模板页面时调用。
    """
    current = len(prs.slides)
    to_remove = current - keep_count

    if to_remove <= 0:
        return

    removed = 0
    for _ in range(to_remove):
        try:
            sld_id_lst = prs.slides._sldIdLst
            last_idx = len(sld_id_lst) - 1
            rId = sld_id_lst[last_idx].rId
            prs.part.drop_rel(rId)
            del sld_id_lst[last_idx]
            removed += 1
        except Exception as e:
            logger.warning(f"[CleanRender] 删除末尾多余页出错: {e}")
            break

    logger.info(f"[CleanRender] 已删除末尾 {removed} 张多余页 (保留 {keep_count})")


def render_ppt_with_template_clean(
    slides_data: List[Dict[str, Any]],
    template_id: Optional[str] = None,
    template_path: Optional[str] = None
) -> bytes:
    """
    主入口：根据模板渲染 PPT — 原地替换策略
    
    Args:
        slides_data: 幻灯片数据列表
        template_id: Supabase user_templates 表中的 UUID
        template_path: 直接指定本地模板路径（优先于 template_id）
    
    Returns:
        PPTX 文件的 bytes
    """
    if not slides_data:
        raise ValueError("slides_data 为空，无法渲染")

    actual_path = template_path

    if not actual_path and template_id:
        actual_path = _download_template(template_id)

    if not actual_path or not os.path.exists(actual_path):
        raise FileNotFoundError(
            f"模板不可用: template_id={template_id}, path={actual_path}"
        )

    user_count = len(slides_data)

    logger.info(f"[CleanRender] 开始渲染 | 模板: {actual_path} | 用户页数: {user_count}")

    prs = Presentation(actual_path)
    original_count = len(prs.slides)

    logger.info(f"[CleanRender] 模板已加载 | 版式数: {len(prs.slide_layouts)} "
               f"| 原始模板页数: {original_count}")

    reuse_count = min(original_count, user_count)

    logger.info(f"[CleanRender] 策略: 复用前 {reuse_count} 页原始模板页")

    for idx in range(reuse_count):
        sd = slides_data[idx]
        title = sd.get('title', '') or f'第{idx + 1}页'
        subtitle = sd.get('subtitle', '') or ''
        raw_content = sd.get('content', [])

        if isinstance(raw_content, str):
            content_lines = [raw_content] if raw_content.strip() else []
        elif isinstance(raw_content, list):
            content_lines = [str(c) for c in raw_content if c]
        else:
            content_lines = []

        page_type = sd.get('page_type') or sd.get('type') or 'content'

        slide = prs.slides[idx]
        _replace_slide_content(slide, title, subtitle, content_lines)

        logger.info(f"[CleanRender] 第 {idx + 1}/{user_count} 页 [原地替换]: "
                   f"{title[:30]}... [{page_type}]")

    if user_count > original_count:
        extra_count = user_count - original_count
        logger.info(f"[CleanRender] 追加 {extra_count} 页新幻灯片...")

        for idx in range(original_count, user_count):
            sd = slides_data[idx]
            title = sd.get('title', '') or f'第{idx + 1}页'
            subtitle = sd.get('subtitle', '') or ''
            raw_content = sd.get('content', [])

            if isinstance(raw_content, str):
                content_lines = [raw_content] if raw_content.strip() else []
            elif isinstance(raw_content, list):
                content_lines = [str(c) for c in raw_content if c]
            else:
                content_lines = []

            page_type = sd.get('page_type') or sd.get('type') or 'content'

            layout = _pick_layout(prs, page_type)
            slide = prs.slides.add_slide(layout)
            _fill_slide_placeholders(slide, title, subtitle, content_lines)

            logger.info(f"[CleanRender] 第 {idx + 1}/{user_count} 页 [新增]: "
                       f"{title[:30]}... [{page_type}]")

    elif user_count < original_count:
        remove_count = original_count - user_count
        logger.info(f"[CleanRender] 删除末尾 {remove_count} 张多余模板页...")
        _remove_trailing_slides(prs, user_count)

    output = io.BytesIO()
    prs.save(output)
    result_bytes = output.getvalue()

    final_count = len(prs.slides)
    logger.info(f"[CleanRender] 渲染完成 | 输出: {len(result_bytes) / 1024:.1f} KB "
               f"| 最终页数: {final_count} (全部为用户内容)")

    return result_bytes
