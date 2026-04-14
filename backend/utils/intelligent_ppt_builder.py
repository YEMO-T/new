"""
智能 PPT 构建器 v4.0 — 原生模板继承版
========================================

顶层入口，整合：
  1. 模板下载/缓存（Supabase 或 本地）
  2. SmartStyleExtractor v3.0 全量样式提取
  3. NativePPTEngine v4.0 原生PPT生成（零图片化）
  4. 输出标准可编辑 .pptx 文件

核心变化（vs v3.1）：
- 引擎从 FullStyleEngine(v3.1) 升级为 NativePPTEngine(v4.0)
- 新增装饰图形保护机制
- 新增原始幻灯片自动清理
- 内容结构化映射（支持多级列表/嵌套要点）
- 12种占位符类型全覆盖
"""

import os
import io
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class IntelligentPPTBuilder:
    """
    智能 PPT 构建器 v4.0
    
    完整流水线：
      模板解析 → 样式提取 → 原生PPT生成 → 输出文件
    
    六条铁律保证：
      ① 禁止图片化模板
      ② 原生占位符智能识别
      ③ 内容结构化映射
      ④ 零手动文本框
      ⑤ 视觉效果完整继承
      ⑥ 可编辑标准PPT输出
    """

    def __init__(self):
        self._style_cache: Dict[str, Dict[str, Any]] = {}
        self._template_cache_dir: Optional[str] = None

    def _get_cache_dir(self) -> str:
        if self._template_cache_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._template_cache_dir = os.path.join(base, 'data', 'templates')
            os.makedirs(self._template_cache_dir, exist_ok=True)
        return self._template_cache_dir

    def build(
        self,
        slides_data: List[Dict[str, Any]],
        template_id: Optional[str] = None,
        template_path: Optional[str] = None,
        title: str = "未命名演示",
    ) -> bytes:
        """
        构建完整的 PPT 文件（v4.0 — 原生模板继承版）

        【铁律1强制】template_path 或 template_id 必须提供其一，
        最终必须解析出有效的本地模板文件路径。

        Args:
            slides_data: 幻灯片数据列表
            template_id: Supabase 模板 ID（用于下载）
            template_path: 本地路径（优先使用）
            title: 标题

        Returns:
            PPTX bytes（标准可编辑格式）

        Raises:
            ValueError: 无法获取模板路径
            FileNotFoundError: 模板文件不存在
        """
        if not slides_data:
            raise ValueError("slides_data 不能为空")

        logger.info(
            f"[Builder-v4.0] 开始 | 标题={title} 页数={len(slides_data)} "
            f"tpl_id={template_id or '无'} tpl_path={'有' if template_path else '无'}"
        )

        actual_tpl_path = template_path

        if not actual_tpl_path and template_id:
            actual_tpl_path = self._resolve_template(template_id)

        if not actual_tpl_path:
            raise ValueError(
                "[铁律1违规] 无法获取模板路径。"
                "必须提供 template_path（本地文件路径）或 "
                "template_id（用于从模板库下载）。"
                "禁止创建空白PPT或使用图片化模板。"
            )

        if not os.path.exists(actual_tpl_path):
            raise FileNotFoundError(
                f"[铁律1违规] 模板文件不存在: {actual_tpl_path}"
            )

        normalized = [self._normalize_slide(sd) for sd in slides_data]

        style_dict = self._extract_or_get_style(actual_tpl_path, template_id)

        from utils.native_ppt_engine import generate_native_ppt

        ppt_stream = generate_native_ppt(
            slides_data=normalized,
            style_profile=style_dict,
            template_path=actual_tpl_path,
        )

        result_bytes = ppt_stream.getvalue()
        logger.info(f"[Builder-v4.0] 完成 | 大小={len(result_bytes)/1024:.1f}KB")
        return result_bytes

    def _resolve_template(self, template_id: str) -> Optional[str]:
        """解析模板路径（本地缓存 → 云端下载）"""
        cache_dir = self._get_cache_dir()
        local_path = os.path.join(cache_dir, f"{template_id}.pptx")

        if os.path.exists(local_path):
            logger.info(f"[Builder-v4.0] 缓存命中: {local_path}")
            return local_path

        logger.info(f"[Builder-v4.0] 从云端下载模板: {template_id}")

        try:
            from repository.supabase_client import get_supabase_client
            supabase = get_supabase_client()

            row = supabase.table('user_templates').select(
                'file_path,file_bucket,style_gene'
            ).eq('id', template_id).execute()

            if not row.data or len(row.data) == 0:
                logger.warning(f"[Builder-v4.0] 数据库无此模板: {template_id}")
                return None

            r = row[0]

            cached_sg = r.get('style_gene')
            if isinstance(cached_sg, dict):
                self._style_cache[template_id] = cached_sg

            fp, fb = r.get('file_path'), r.get('file_bucket')
            if not fp or not fb or fb == 'local':
                return local_path if os.path.exists(local_path) else None

            file_data = supabase.storage.from_(fb).download(fp)
            if file_data:
                with open(local_path, 'wb') as f:
                    f.write(file_data)
                logger.info(f"[Builder-v4.0] 下载完成: {local_path}")
                return local_path

        except Exception as e:
            logger.error(f"[Builder-v4.0] 下载失败: {e}")

        return None

    def _normalize_slide(self, slide: Dict[str, Any]) -> Dict[str, Any]:
        """标准化单页数据格式"""
        d = dict(slide) if isinstance(slide, dict) else {}
        d.setdefault('title', '未命名')
        d.setdefault('subtitle', '')
        d.setdefault('page_type', 'content')

        content = d.get('content', [])
        if isinstance(content, str):
            content = [c.strip() for c in content.split('\n') if c.strip()]
        elif not isinstance(content, list):
            content = []
        d['content'] = content

        pt = d.get('page_type', 'content').lower()
        if pt not in ('cover', 'content', 'toc', 'summary', 'ending'):
            pt = 'content'
        d['page_type'] = pt

        return d

    def _extract_or_get_style(
        self, tpl_path: Optional[str], tpl_id: Optional[str]
    ) -> Dict[str, Any]:
        """获取样式配置（优先缓存 → 实时提取 → 默认兜底）"""
        if tpl_id and tpl_id in self._style_cache:
            logger.info(f"[Builder-v4.0] 使用缓存样式: {tpl_id}")
            return self._style_cache[tpl_id]

        if not tpl_path or not os.path.exists(tpl_path):
            logger.info("[Builder-v4.0] 无可用模板，使用默认样式")
            return self._default_style()

        try:
            from utils.smart_style_extractor import SmartStyleExtractor
            extractor = SmartStyleExtractor()
            profile = extractor.extract(tpl_path, tpl_id or "")
            sd = profile.to_dict()
            if tpl_id:
                self._style_cache[tpl_id] = sd
            return sd
        except Exception as e:
            logger.error(f"[Builder-v4.0] 样式提取失败: {e}，使用默认样式")
            return self._default_style()

    def _default_style(self) -> Dict[str, Any]:
        """默认样式配置（当无法提取时使用）"""
        return {
            'colors': {
                'accent1': '#4A90D9',
                'accent2': '#5BA3EC',
                'dark1': '#2C3E50',
                'light1': '#FFFFFF',
                'dark2': '#34495E',
                'light2': '#ECF0F1',
            },
            'fonts': {
                'major_east_asian': '微软雅黑',
                'minor_east_asian': '微软雅黑',
                'major_latin': 'Arial',
                'minor_latin': 'Arial',
            },
            'master': {
                'width_inches': 13.33,
                'height_inches': 7.5,
                'background': {'bg_type': 'solid', 'color': '#FFFFFF'},
            },
            'layouts': [
                {
                    'index': 0,
                    'name': 'Title Slide',
                    'layout_type': 'cover',
                    'has_title': True,
                    'has_body': False,
                    'placeholders': [{
                        'idx': 0,
                        'ph_type': 'title',
                        'text_style': {
                            'font_name': '微软雅黑',
                            'font_size_pt': 44.0,
                            'font_color': '#2C3E50',
                            'bold': True,
                            'align': 'center',
                        },
                    }],
                },
                {
                    'index': 1,
                    'name': 'Title and Content',
                    'layout_type': 'content',
                    'has_title': True,
                    'has_body': True,
                    'placeholders': [
                        {
                            'idx': 0,
                            'ph_type': 'title',
                            'text_style': {
                                'font_name': '微软雅黑',
                                'font_size_pt': 32.0,
                                'font_color': '#2C3E50',
                                'bold': True,
                                'align': 'left',
                            },
                        },
                        {
                            'idx': 1,
                            'ph_type': 'body',
                            'text_style': {
                                'font_name': '微软雅黑',
                                'font_size_pt': 18.0,
                                'font_color': '#34495E',
                                'bold': False,
                                'align': 'left',
                                'line_spacing': 1.35,
                            },
                        },
                    ],
                },
            ],
            'title_levels': [
                {
                    'level': 'h1',
                    'used_for': 'cover_title',
                    'style': {
                        'font_name': '微软雅黑',
                        'font_size_pt': 44.0,
                        'font_color': '#2C3E50',
                        'bold': True,
                        'align': 'center',
                    },
                },
                {
                    'level': 'h2',
                    'used_for': 'content_title',
                    'style': {
                        'font_name': '微软雅黑',
                        'font_size_pt': 28.0,
                        'font_color': '#2C3E50',
                        'bold': True,
                        'align': 'left',
                    },
                },
            ],
            'shape_defaults': {},
            'chart_rules': {},
            'effects': {},
        }

    def build_with_fallback(
        self,
        slides_data: List[Dict[str, Any]],
        template_id: Optional[str] = None,
        template_path: Optional[str] = None,
        title: str = "未命名演示",
    ) -> tuple:
        """
        带降级的构建方法（兼容旧版调用方）
        
        优先使用 v4.0 原生引擎，失败时自动降级到 clean_renderer。
        
        Returns:
            (result_bytes: bytes, engine_name: str)
        """
        try:
            result = self.build(slides_data, template_id, template_path, title)
            return result, 'native_v4'
        except Exception as e:
            logger.warning(f"[Builder-v4.0] 主引擎失败: {e}，降级中...")
            try:
                from utils.clean_renderer import render_ppt_with_template_clean
                norm = [self._normalize_slide(s) for s in slides_data]
                rb = render_ppt_with_template_clean(norm, template_id, template_path)
                return rb, 'clean_renderer_fallback'
            except Exception as e2:
                logger.error(f"[Builder-v4.0] 降级也失败: {e2}")
                raise


def build_intelligent_ppt(
    slides_data: List[Dict[str, Any]],
    template_id: Optional[str] = None,
    template_path: Optional[str] = None,
    title: str = "未命名演示",
) -> bytes:
    """便捷入口函数"""
    builder = IntelligentPPTBuilder()
    return builder.build(slides_data, template_id, template_path, title)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("  智能PPT构建器 v4.0 — 测试")
    print("=" * 60)

    tpl = sys.argv[1] if len(sys.argv) > 1 else ""
    if not tpl or not os.path.exists(tpl):
        print("\n❌ 用法: python intelligent_ppt_builder.py <模板.pptx>")
        sys.exit(1)

    demo = [
        {"page_type": "cover", "title": "v4.0构建器测试", "subtitle": "原生引擎驱动"},
        {"page_type": "content", "title": "测试页", "content": ["• 要点1", "• 要点2"]},
    ]

    result = build_intelligent_ppt(demo, template_path=tpl)

    out = "test_builder_v4_output.pptx"
    with open(out, 'wb') as f:
        f.write(result)

    print(f"\n✅ 输出: {out} ({len(result)/1024:.1f} KB)")
