"""
独立测试：验证 Clean Renderer v2（原地替换策略）

不依赖后端服务、不依赖 Supabase、不依赖前端。
自己创建一个带示例内容的模板 → 渲染用户数据 → 验证输出只有用户内容

v2 策略：不复用 add_slide + delete，而是直接在原始页上替换内容
"""

import os
import sys
import io
import tempfile
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pptx import Presentation
from pptx.util import Inches, Pt
from utils.clean_renderer import (
    render_ppt_with_template_clean,
    _replace_slide_content,
)


def create_test_template(output_path: str, original_slide_count: int = 3):
    """
    创建一个带原始示例内容的测试模板
    
    模拟真实模板的样子：
    - 第1页: "点击添加标题" / "点击添加副标题"
    - 第2页: "标题文字" / "正文占位符"
    - 第3页: 更多示例内容
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]
    content_layout = None
    for layout in prs.slide_layouts:
        if layout.name and 'title' in layout.name.lower() and 'content' in layout.name.lower():
            content_layout = layout
            break
    if not content_layout:
        content_layout = prs.slide_layouts[0]

    sample_slides = [
        {
            'title': '点击添加标题',
            'subtitle': '点击添加副标题',
            'body_lines': ['这是模板的原始示例内容', '不应该出现在最终输出中'],
        },
        {
            'title': '调研背景与目标',
            'body_lines': ['这是模板第2页的示例', '用户的内容应该替换这些'],
        },
        {
            'title': '方法论',
            'body_lines': ['模板第3页', '更多示例文字'],
        },
    ]

    for i, sample in enumerate(sample_slides[:original_slide_count]):
        if i == 0:
            slide = prs.slides.add_slide(title_layout)
        else:
            slide = prs.slides.add_slide(content_layout)

        left = Inches(0.5)
        top = Inches(0.3)
        width = Inches(12.333)

        title_box = slide.shapes.add_textbox(left, top, width, Inches(1))
        tf = title_box.text_frame
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = sample['title']
        run.font.size = Pt(36)
        run.font.bold = True

        if sample.get('subtitle'):
            sub_top = Inches(1.5)
            sub_box = slide.shapes.add_textbox(left, sub_top, width, Inches(0.6))
            tf2 = sub_box.text_frame
            p2 = tf2.paragraphs[0]
            r2 = p2.add_run()
            r2.text = sample['subtitle']
            r2.font.size = Pt(20)

        if sample.get('body_lines'):
            body_top = Inches(2.3) if sample.get('subtitle') else Inches(1.8)
            body_box = slide.shapes.add_textbox(left, body_top, width, Inches(4.5))
            tf3 = body_box.text_frame
            for j, line in enumerate(sample['body_lines']):
                if j == 0:
                    pj = tf3.paragraphs[0]
                else:
                    pj = tf3.add_paragraph()
                rj = pj.add_run()
                rj.text = line
                rj.font.size = Pt(18)

    prs.save(output_path)
    logger.info(f"[TEST] 测试模板已创建: {output_path} ({original_slide_count} 页原始内容)")
    return output_path


def test_render_with_clean_renderer(template_path: str):
    """用 clean renderer 渲染用户数据"""
    user_slides = [
        {
            'title': '《琵琶行》教学课件',
            'subtitle': '高一语文 · 白居易',
            'content': ['教学目标', '文本赏析', '课堂讨论'],
            'page_type': 'cover',
        },
        {
            'title': '作者简介',
            'content': [
                '白居易（772-846），字乐天，号香山居士',
                '唐代伟大的现实主义诗人',
                '代表作：《长恨歌》《琵琶行》',
            ],
            'page_type': 'content',
        },
        {
            'title': '诗歌全文',
            'content': [
                '浔阳江头夜送客，枫叶荻花秋瑟瑟。',
                '主人下马客在船，举酒欲饮无管弦。',
                '醉不成欢惨将别，别时茫茫江浸月。',
            ],
            'page_type': 'content',
        },
        {
            'title': '课堂总结',
            'content': ['理解诗歌主旨', '掌握写作手法', '感受艺术魅力'],
            'page_type': 'summary',
        },
    ]

    logger.info(f"[TEST] 开始渲染 {len(user_slides)} 页用户内容...")

    result_bytes = render_ppt_with_template_clean(
        slides_data=user_slides,
        template_path=template_path,
    )

    logger.info(f"[TEST] 渲染完成！输出大小: {len(result_bytes) / 1024:.1f} KB")

    return result_bytes


def verify_output(pptx_bytes: bytes, expected_user_count: int, template_original_count: int):
    """
    验证输出 PPT 是否只包含用户页面（不含原始模板内容）
    
    v2 验证逻辑：
    1. 页数必须等于用户请求的页数
    2. 每一页都不应包含模板的原始示例文字
    3. 每一页都应包含用户的实际内容
    """
    logger.info("=" * 60)
    logger.info("[VERIFY] 开始验证输出...")
    
    prs = Presentation(io.BytesIO(pptx_bytes))
    total_slides = len(prs.slides)
    
    logger.info(f"[VERIFY] 输出总页数: {total_slides}")
    logger.info(f"[VERIFY] 期望用户页数: {expected_user_count}")
    logger.info(f"[VERIFY] 原始模板页数: {template_original_count}")
    
    if total_slides != expected_user_count:
        logger.error(f"[VERIFY] ❌ 页数不匹配! 期望 {expected_user_count}, 实际 {total_slides}")
        return False
    
    logger.info(f"[VERIFY] ✅ 页数匹配: {total_slides} = 用户 {expected_user_count} 页")
    
    template_keywords = [
        '点击添加标题',
        '点击添加副标题',
        '这是模板的原始示例内容',
        '不应该出现在最终输出中',
        '模板第2页的示例',
        '模板第3页',
        '更多示例文字',
    ]
    
    user_keywords = [
        ('琵琶行', '第1页'),
        ('作者简介', '第2页'),
        ('诗歌全文', '第3页'),
        ('课堂总结', '第4页'),
    ]
    
    found_template_content = False
    all_ok = True
    
    for idx, slide in enumerate(prs.slides):
        all_text = ""
        for shape in slide.shapes:
            if hasattr(shape, 'text') and shape.text:
                all_text += shape.text + " "
        
        all_text = all_text.strip()
        title_preview = all_text[:70].replace('\n', ' ')
        
        for keyword in template_keywords:
            if keyword in all_text:
                logger.error(f"[VERIFY] ❌ 第{idx+1}页发现模板残留!")
                logger.error(f"[VERIFY]    关键词: '{keyword}'")
                logger.error(f"[VERIFY]    文本: '{title_preview}...'")
                found_template_content = True
        
        expected_keyword, page_label = user_keywords[idx]
        if expected_keyword in all_text:
            logger.info(f"[VERIFY] 第{idx+1}页 ({page_label}): '{title_preview}...' ✅")
        else:
            logger.warning(f"[VERIFY] ⚠️ 第{idx+1}页 ({page_label}): 未找到预期关键词 '{expected_keyword}'")
            logger.warning(f"[VERIFY]    实际文本: '{title_preview}...'")
            all_ok = False
    
    if found_template_content:
        logger.error("")
        logger.error("[VERIFY] ❌❌❌ 验证失败: 输出中包含模板原始内容!")
        logger.error("[VERIFY]     结论: 原地替换策略未正确清除模板示例文字")
        return False
    
    if not all_ok:
        logger.warning("")
        logger.warning("[VERIFY] ⚠️ 部分验证未通过: 用户内容可能未正确填充")
        return False
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("[VERIFY] ✅✅✅ 全部通过!")
    logger.info(f"[VERIFY]   - 页数正确: {total_slides} 页 (全是用户页面)")
    logger.info("[VERIFY]   - 无模板残留: 所有原始示例内容已被清除/替换")
    logger.info("[VERIFY]   - 用户内容正确: 每页均包含预期的用户数据")
    logger.info("[VERIFY]   - 结论: 原地替换策略工作正常")
    logger.info("=" * 60)
    return True


def main():
    logger.info("=" * 60)
    logger.info("Clean Renderer v2 独立测试 (原地替换策略)")
    logger.info("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        template_path = os.path.join(tmpdir, "test_template.pptx")
        output_path = os.path.join(tmpdir, "test_output.pptx")

        original_count = 3

        logger.info(f"\n[STEP 1] 创建测试模板 (含 {original_count} 页原始示例内容)")
        create_test_template(template_path, original_count)

        logger.info(f"\n[STEP 2] 用 clean_renderer v2 渲染 4 页用户内容 (原地替换前3页 + 追加1页)")
        result_bytes = test_render_with_clean_renderer(template_path)

        with open(output_path, 'wb') as f:
            f.write(result_bytes)
        logger.info(f"[TEST] 输出已保存: {output_path}")

        logger.info(f"\n[STEP 3] 验证输出 (检查是否有模板残留)")
        success = verify_output(result_bytes, expected_user_count=4, template_original_count=original_count)

        if success:
            logger.info("\n🎉 测试全部通过! 原地替换策略工作正常.")
            logger.info("   重启后端服务即可生效。")
            return 0
        else:
            logger.error("\n💥 测试失败! 需要修复渲染引擎。")
            return 1


if __name__ == '__main__':
    sys.exit(main())
