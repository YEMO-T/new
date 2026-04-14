"""
全量样式提取器 (Smart Style Extractor v3.0)
============================================

强制提取 PPT 模板的全部视觉样式，不遗漏任何维度。

提取清单（6大维度）：
  1. 母版样式：全局主题、默认字体方案、全局配色(12色)、效果方案
  2. 版式结构：封面/目录/正文/结尾页布局、占位符位置(x/y/w/h)/大小/类型
  3. 文本样式：字体/字号/颜色/加粗/倾斜/下划线/段落间距/缩进/对齐
  4. 背景样式：纯色/渐变(角度+色标)/图片/纹理 背景
  5. 形状&图表样式：默认填充/边框/阴影/图表配色规则
  6. 标题层级：H1/H2/H3 固定标题样式(textStyles)

技术路线：
- python-pptx 打开文件获取基础结构
- lxml 直接解析 XML 获取深层样式属性
- 双轨并行确保数据完整性
"""

import os
import zipfile
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

NS_MAP = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'p14': 'http://schemas.microsoft.com/office/powerpoint/2010/main',
    'p15': 'http://schemas.microsoft.com/office/powerpoint/2012/main',
}


def _ns(tag: str, ns: str = 'a') -> str:
    return f'{{{NS_MAP[ns]}}}{tag}'


def _local(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


# ============================================================
# 数据模型 — 全部6个维度
# ============================================================

@dataclass
class ColorScheme:
    """全局配色方案（12色 + 超链接）"""
    dark1: str = "#000000"
    light1: str = "#FFFFFF"
    dark2: str = ""
    light2: str = ""
    accent1: str = ""
    accent2: str = ""
    accent3: str = ""
    accent4: str = ""
    accent5: str = ""
    accent6: str = ""
    hyperlink: str = "#0563C1"
    followed_hyperlink: str = "#954F72"

    def to_dict(self) -> dict:
        return {
            k: v for k, v in self.__dict__.items()
        }

    @property
    def primary(self) -> str:
        return self.accent1 or self.dark1 or "#333333"


@dataclass
class FontScheme:
    """字体方案（major=标题/minor=正文 × latin/eastAsian/cs）"""
    major_latin: str = "Arial"
    major_east_asian: str = "微软雅黑"
    major_complex_script: str = ""
    minor_latin: str = "Arial"
    minor_east_asian: str = "微软雅黑"
    minor_complex_script: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @property
    def title_font(self) -> str:
        return self.major_east_asian or self.major_latin

    @property
    def body_font(self) -> str:
        return self.minor_east_asian or self.minor_latin


@dataclass
class EffectScheme:
    """效果方案（填充/线条/阴影/发光/反射等默认值）"""
    fill_style: str = ""       # solid / grad / none
    line_style: str = ""       # solid / none
    effect_type: str = ""      # outerShdw / reflection / glow / none
    shadow_blur_rad: str = ""  # 阴影模糊半径
    shadow_dist: str = ""      # 阴影距离
    shadow_dir: str = ""       # 阴影方向角度
    shadow_color: str = ""     # 阴影颜色

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class TextStyle:
    """完整文本样式"""
    font_name: str = ""
    font_size_pt: float = 0.0
    font_color: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    align: str = ""            # left / center / right / justify
    valign: str = ""           # top / middle / bottom / baseline
    line_spacing: float = 0.0   # 行距（倍数或pt）
    space_before_pt: float = 0.0   # 段前间距
    space_after_pt: float = 0.0    # 段后间距
    indent_level: int = 0      # 缩进层级
    margin_left: float = 0.0   # 左缩进(emu)
    bullet_type: str = ""      # bullet / number / none

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if v not in ("", 0, 0.0, False, None):
                d[k] = v
        return d

    @property
    def is_empty(self) -> bool:
        return (
            not self.font_name and self.font_size_pt == 0
            and not self.font_color and not self.bold
            and not self.italic and not self.underline
        )


@dataclass
class PlaceholderStyle:
    """占位符完整样式（含位置+文本格式）"""
    idx: int = 0
    ph_type: str = ""          # title / body / ctrTitle / subTitle / dt / sldNum / obj / pic / chart / tbl
    name: str = ""
    x_emu: int = 0
    y_emu: int = 0
    w_emu: int = 0
    h_emu: int = 0
    text_style: TextStyle = field(default_factory=TextStyle)

    @property
    def x_inch(self) -> float:
        return round(self.x_emu / 914400, 3)

    @property
    def y_inch(self) -> float:
        return round(self.y_emu / 914400, 3)

    @property
    def w_inch(self) -> float:
        return round(self.w_emu / 914400, 3)

    @property
    def h_inch(self) -> float:
        return round(self.h_emu / 914400, 3)

    def to_dict(self) -> dict:
        base = {
            'idx': self.idx,
            'ph_type': self.ph_type,
            'name': self.name,
            'position': {'x': self.x_inch, 'y': self.y_inch,
                         'w': self.w_inch, 'h': self.h_inch},
            'text_style': self.text_style.to_dict(),
        }
        if not self.text_style.is_empty:
            base['has_text_style'] = True
        return base


@dataclass
class GradientStop:
    """渐变色标"""
    position_pct: float = 0.0
    color: str = ""

    def to_dict(self) -> dict:
        return {'pos': self.position_pct, 'color': self.color}


@dataclass
class BackgroundStyle:
    """背景样式"""
    bg_type: str = "none"           # none / solid / gradient / image / pattern
    color: str = ""
    gradient_type: str = ""         # linear / radial / rect / path
    gradient_angle: int = 0         # 渐变角度
    gradient_stops: List[GradientStop] = field(default_factory=list)
    image_rel_id: str = ""

    def to_dict(self) -> dict:
        d = {'bg_type': self.bg_type}
        if self.color:
            d['color'] = self.color
        if self.bg_type == 'gradient':
            d['gradient'] = {
                'type': self.gradient_type,
                'angle': self.gradient_angle,
                'stops': [s.to_dict() for s in self.gradient_stops],
            }
        if self.bg_type == 'image' and self.image_rel_id:
            d['image_rId'] = self.image_rel_id
        return d


@dataclass
class ShapeDefaultStyle:
    """形状默认样式"""
    fill_type: str = ""             # solid / none / grad / blip
    fill_color: str = ""
    line_type: str = ""             # solid / none
    line_width_pt: float = 0.0
    line_color: str = ""
    dash_type: str = ""             # solid / dash / dashDot / dot ...
    shadow_enabled: bool = False
    shadow_color: str = ""
    shadow_dist_pt: float = 0.0
    shadow_angle: int = 0
    effect_3d: bool = False

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if v not in ("", 0, 0.0, False, None):
                d[k] = v
        return d


@dataclass
class ChartColorRule:
    """图表配色规则"""
    series_colors: List[str] = field(default_factory=list)
    background_color: str = ""
    plot_area_fill: str = ""
    gridline_color: str = ""
    axis_font_size: float = 8.0
    axis_line_color: str = ""

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if v not in ("", 0, 0.0, [], None):
                d[k] = v
        return d


@dataclass
class TitleLevelStyle:
    """标题层级样式 (H1 / H2 / H3)"""
    level: str = ""               # h1 / h2 / h3
    text_style: TextStyle = field(default_factory=TextStyle)
    used_for: str = ""            # cover_title / content_title / subtitle etc.

    def to_dict(self) -> dict:
        d = {'level': self.level, 'style': self.text_style.to_dict()}
        if self.used_for:
            d['used_for'] = self.used_for
        return d


@dataclass
class LayoutProfile:
    """单个版式完整画像"""
    index: int = 0
    name: str = ""
    layout_type: str = ""         # cover / toc / content / summary / ending / blank
    has_title_ph: bool = False
    has_body_ph: bool = False
    placeholders: List[PlaceholderStyle] = field(default_factory=list)
    background: BackgroundStyle = field(default_factory=BackgroundStyle)

    def to_dict(self) -> dict:
        return {
            'index': self.index,
            'name': self.name,
            'layout_type': self.layout_type,
            'has_title': self.has_title_ph,
            'has_body': self.has_body_ph,
            'placeholders': [p.to_dict() for p in self.placeholders],
            'background': self.background.to_dict(),
        }


@dataclass
class SlideMasterProfile:
    """母版画像"""
    width_emu: int = 9144000
    height_emu: int = 6858000
    background: BackgroundStyle = field(default_factory=BackgroundStyle)
    theme_name: str = ""

    @property
    def width_inches(self) -> float:
        return round(self.width_emu / 914400, 2)

    @property
    def height_inches(self) -> float:
        return round(self.height_emu / 914400, 2)

    @property
    def aspect_ratio(self) -> str:
        r = self.width_emu / self.height_emu if self.height_emu > 0 else 1
        return "16:9" if r > 1.5 else "4:3"

    def to_dict(self) -> dict:
        return {
            'width_inches': self.width_inches,
            'height_inches': self.height_inches,
            'aspect_ratio': self.aspect_ratio,
            'theme_name': self.theme_name,
            'background': self.background.to_dict(),
        }


@dataclass
class TemplateFullStyleProfile:
    """
    模板全量样式画像 (v3.0)
    
    包含重建模板视觉效果所需的全部6维数据。
    """
    template_id: str = ""
    template_name: str = ""

    colors: ColorScheme = field(default_factory=ColorScheme)
    fonts: FontScheme = field(default_factory=FontScheme)
    effects: EffectScheme = field(default_factory=EffectScheme)
    master: SlideMasterProfile = field(default_factory=SlideMasterProfile)
    layouts: List[LayoutProfile] = field(default_factory=list)
    shape_defaults: ShapeDefaultStyle = field(default_factory=ShapeDefaultStyle)
    chart_rules: ChartColorRule = field(default_factory=ChartColorRule)
    title_levels: List[TitleLevelStyle] = field(default_factory=list)

    extracted_at: str = ""
    extract_version: str = "3.0"

    @property
    def primary_color(self) -> str:
        return self.colors.primary

    @property
    def title_font(self) -> str:
        return self.fonts.title_font

    @property
    def body_font(self) -> str:
        return self.fonts.body_font

    @property
    def layout_count(self) -> int:
        return len(self.layouts)

    def get_layout_by_type(self, t: str) -> Optional[LayoutProfile]:
        for l in self.layouts:
            if l.layout_type == t:
                return l
        return None

    def to_dict(self) -> dict:
        return {
            'template_id': self.template_id,
            'template_name': self.template_name,
            'version': self.extract_version,
            'extracted_at': self.extracted_at,

            'colors': self.colors.to_dict(),
            'fonts': self.fonts.to_dict(),
            'effects': self.effects.to_dict(),

            'master': self.master.to_dict(),

            'layouts': [l.to_dict() for l in self.layouts],

            'shape_defaults': self.shape_defaults.to_dict(),
            'chart_rules': self.chart_rules.to_dict(),

            'title_levels': [t.to_dict() for t in self.title_levels],

            '_summary': {
                'primary_color': self.primary_color,
                'title_font': self.title_font,
                'body_font': self.body_font,
                'layout_count': self.layout_count,
                'aspect_ratio': self.master.aspect_ratio,
                'placeholder_total': sum(len(l.placeholders) for l in self.layouts),
                'bg_type': self.master.background.bg_type,
            }
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ============================================================
# 提取器核心
# ============================================================

class SmartStyleExtractor:
    """
    全量样式提取器 v3.0
    
    直接解析 PPTX 内部 XML，提取全部6维样式。
    
    用法：
        extractor = SmartStyleExtractor()
        profile = extractor.extract('/path/to/template.pptx')
        print(profile.primary_color)
        print(profile.title_levels[0].text_style.font_size_pt)
    """

    def __init__(self):
        self._zip: Optional[zipfile.ZipFile] = None
        self.profile: TemplateFullStyleProfile = TemplateFullStyleProfile()

    def extract(
        self,
        file_path: str,
        template_id: str = "",
        template_name: str = "",
    ) -> TemplateFullStyleProfile:
        from datetime import datetime

        logger.info(f"[StyleExtractor-v3] 开始全量提取: {file_path}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"模板文件不存在: {file_path}")

        try:
            self.profile = TemplateFullStyleProfile(
                template_id=template_id,
                template_name=template_name or os.path.basename(file_path),
                extracted_at=datetime.now().isoformat(),
            )

            with zipfile.ZipFile(file_path, 'r') as self._zip:
                self._step1_extract_theme()
                self._step2_extract_master()
                self._step3_extract_layouts()
                self._step4_extract_shape_defaults()
                self._step5_extract_chart_rules()
                self._step6_extract_title_levels()

            n_ph = sum(len(l.placeholders) for l in self.profile.layouts)
            logger.info(f"[StyleExtractor-v3] 提取完成:")
            logger.info(f"  主色调={self.profile.primary_color}  "
                       f"标题字体={self.profile.title_font}  "
                       f"正文字体={self.profile.body_font}")
            logger.info(f"  版式数={len(self.profile.layouts)}  "
                       f"总占位符={n_ph}  "
                       f"比例={self.profile.master.aspect_ratio}  "
                       f"背景={self.profile.master.background.bg_type}")
            logger.info(f"  标题层级={len(self.profile.title_levels)}级  "
                       f"形状填充={self.profile.shape_defaults.fill_type}")

            return self.profile

        except Exception as e:
            logger.error(f"[StyleExtractor-v3] 提取失败: {e}", exc_info=True)
            raise ValueError(f"样式提取失败: {str(e)}")
        finally:
            self._zip = None

    # ----------------------------------------------------------
    # 内部工具方法
    # ----------------------------------------------------------

    def _read_xml(self, path: str) -> Optional[ET.Element]:
        if not self._zip or path not in self._zip.namelist():
            return None
        try:
            with self._zip.open(path) as f:
                return ET.fromstring(f.read())
        except Exception as e:
            logger.debug(f"[XML读取失败] {path}: {e}")
            return None

    def _find(self, parent: ET.Element, tag: str, ns: str = 'a') -> Optional[ET.Element]:
        return parent.find(_ns(tag, ns))

    def _findall(self, parent: ET.Element, tag: str, ns: str = 'a') -> list:
        return parent.findall(_ns(tag, ns))

    def _attr(self, elem: Optional[ET.Element], attr: str, default: str = "") -> str:
        if elem is None:
            return default
        return elem.get(attr, default)

    def _attr_int(self, elem: Optional[ET.Element], attr: str, default: int = 0) -> int:
        v = self._attr(elem, attr, str(default))
        try:
            return int(v)
        except (ValueError, TypeError):
            return default

    def _parse_color(self, elem: ET.Element) -> str:
        """解析 <a:srgbClr> / <a:schemeClr> / <a:sysClr> → '#RRGGBB' 或 'scheme:xxx'"""
        for ch in elem:
            tn = _local(ch.tag)
            if tn == 'srgbClr':
                v = ch.get('val', '')
                return f'#{v}' if v else ''
            elif tn == 'schemeClr':
                v = ch.get('val', '')
                return f'scheme:{v}' if v else ''
            elif tn == 'sysClr':
                lc = ch.get('lastClr', '')
                return f'#{lc}' if lc else ''
            elif tn == 'prstClr':
                return ch.get('val', '')
        return ''

    def _resolve_scheme_color(self, raw: str) -> str:
        """将 scheme:accent1 等引用解析为实际 hex 值"""
        if not raw.startswith('scheme:'):
            return raw
        key = raw.replace('scheme:', '')
        mapping = {
            'dk1': 'dark1', 'lt1': 'light1',
            'dk2': 'dark2', 'lt2': 'light2',
            'accent1': 'accent1', 'accent2': 'accent2',
            'accent3': 'accent3', 'accent4': 'accent4',
            'accent5': 'accent5', 'accent6': 'accent6',
            'hlink': 'hyperlink', 'folHlink': 'followed_hyperlink',
        }
        attr = mapping.get(key, '')
        if attr:
            val = getattr(self.profile.colors, attr, "")
            if val.startswith('#'):
                return val
        return raw

    # ----------------------------------------------------------
    # Step 1: 主题提取（颜色/字体/效果/textStyles）
    # ----------------------------------------------------------

    def _step1_extract_theme(self):
        root = self._read_xml('ppt/theme/theme1.xml')
        if root is None:
            logger.warning("[Step1] 无法读取 theme1.xml")
            return

        self._extract_clrScheme(root)
        self._extract_fontScheme(root)
        self._extract_fmtScheme(root)
        self._extract_textStyles(root)
        self._extract_theme_name(root)

    def _extract_clrScheme(self, theme_root: ET.Element):
        cs = self._find(theme_root, 'clrScheme')
        if cs is None:
            return
        map_ = {
            'dk1': 'dark1', 'lt1': 'light1',
            'dk2': 'dark2', 'lt2': 'light2',
            'accent1': 'accent1', 'accent2': 'accent2',
            'accent3': 'accent3', 'accent4': 'accent4',
            'accent5': 'accent5', 'accent6': 'accent6',
            'hlink': 'hyperlink', 'folHlink': 'followed_hyperlink',
        }
        for child in cs:
            tn = _local(child.tag)
            if tn in map_:
                setattr(self.profile.colors, map_[tn], self._parse_color(child))

    def _extract_fontScheme(self, theme_root: ET.Element):
        fs = self._find(theme_root, 'fontScheme')
        if fs is None:
            return
        for role, attr_major, attr_minor in [
            ('majorFont', 'major_latin', 'major_east_asian'),
            ('minorFont', 'minor_latin', 'minor_east_asian'),
        ]:
            fe = self._find(fs, role)
            if fe is None:
                continue
            lat = self._find(fe, 'latin')
            ea = self._find(fe, 'ea')
            cs = self._find(fe, 'cs')
            if lat is not None:
                setattr(self.profile.fonts, attr_major if 'major' in attr_major else attr_minor,
                        self._attr(lat, 'typeface'))
            if ea is not None:
                setattr(self.profile.fonts, attr_major.replace('latin', 'east_asian').replace('minor_', 'minor_')
                        if 'east_asian' in attr_major else attr_minor.replace('latin', 'east_asian'),
                        self._attr(ea, 'typeface'))

    def _extract_fmtScheme(self, theme_root: ET.Element):
        fmt = self._find(theme_root, 'fmtScheme')
        if fmt is None:
            return
        fillStyleLst = self._find(fmt, 'fillStyleLst')
        if fillStyleLst is not None:
            first = list(fillStyleLst)
            if first:
                tn = _local(first[0].tag)
                self.profile.effects.fill_style = tn
                if tn == 'solidFill':
                    self.profile.effects.fill_style = 'solid'
                    sf = self._find(first[0], 'srgbClr')
                    if sf is not None:
                        c = sf.get('val', '')
                        self.profile.effects.fill_style = f'solid#{c}'
                elif tn == 'gradFill':
                    self.profile.effects.fill_style = 'grad'
                elif tn == 'noFill':
                    self.profile.effects.fill_style = 'none'

        lnStyleLst = self._find(fmt, 'lnStyleLst')
        if lnStyleLst is not None:
            first_ln = list(lnStyleLst)
            if first_ln:
                tn = _local(first_ln[0].tag)
                if tn == 'ln':
                    w = first_ln[0].get('w', '')
                    try:
                        self.profile.effects.line_width_pt = int(w) / 12700
                    except Exception:
                        pass
                    self.profile.effects.line_style = 'solid'
                elif tn == 'noFill':
                    self.profile.effects.line_style = 'none'

        effectStyleLst = self._find(fmt, 'effectStyleLst')
        if effectStyleLst is not None:
            effects = list(effectStyleLst)
            for eff in effects[:1]:
                eff_lst = self._find(eff, 'effectLst')
                if eff_lst is not None:
                    for sub in eff_lst:
                        stn = _local(sub.tag)
                        if stn == 'outerShdw':
                            self.profile.effects.effect_type = 'outerShdw'
                            self.profile.effects.shadow_dist = sub.get('dist', '')
                            self.profile.effects.shadow_dir = sub.get('dir', '')
                            blurRad = self._find(sub, 'blurRad')
                            if blurRad is not None:
                                self.profile.effects.shadow_blur_rad = blurRad.get('val', '')
                            srgbClr = self._find(sub, 'srgbClr')
                            if srgbClr is not None:
                                self.profile.effects.shadow_color = f'#{srgbClr.get("val", "")}'
                            break

    def _extract_textStyles(self, theme_root: ET.Element):
        """从 <a:textStyles> 提取 H1/H2/H3 等标题层级样式"""
        ts_elem = self._find(theme_root, 'textStyles')
        if ts_elem is None:
            return

        level_map = {
            'title': ('h1', 'cover_title'),
            'body': ('h2', 'body_title'),
            'other': ('h3', 'subtitle'),
        }

        for style_tag, (level, usage) in level_map.items():
            st = self._find(ts_elem, style_tag)
            if st is None:
                continue
            pPr = self._find(st, 'pPr')
            rPr_default = self._find(st, 'defRPr')

            ts = TextStyle()

            if pPr is not None:
                algn = self._attr(pPr, 'algn', '')
                amap = {'l': 'left', 'r': 'right', 'ctr': 'center', 'just': 'justify'}
                ts.align = amap.get(algn, '')

                spc_bef = self._find(pPr, 'spcBef')
                if spc_bef is not None:
                    spc_pts = self._find(spc_bef, 'pts')
                    if spc_pts is not None:
                        try:
                            ts.space_before_pt = int(spc_pts.get('val', '0')) / 100
                        except Exception:
                            pass
                    else:
                        spc_pct = self._find(spc_bef, 'spcPct')
                        if spc_pct is not None:
                            try:
                                ts.space_before_pt = int(spc_pct.get('val', '0')) / 1000
                            except Exception:
                                pass

                spc_aft = self._find(pPr, 'spcAft')
                if spc_aft is not None:
                    spc_pts = self._find(spc_aft, 'pts')
                    if spc_pts is not None:
                        try:
                            ts.space_after_pt = int(spc_pts.get('val', '0')) / 100
                        except Exception:
                            pass

                lnSpc = self._find(pPr, 'lnSpc')
                if lnSpc is not None:
                    pts = self._find(lnSpc, 'pts')
                    if pts is not None:
                        try:
                            ts.line_spacing = int(pts.get('val', '0')) / 100
                        except Exception:
                            pass

            if rPr_default is not None:
                ts.bold = self._attr(rPr_default, 'b', '').lower() in ('1', 'true')
                ts.italic = self._attr(rPr_default, 'i', '').lower() in ('1', 'true')
                sz = self._attr(rPr_default, 'sz', '')
                if sz:
                    try:
                        ts.font_size_pt = int(sz) / 100
                    except ValueError:
                        pass

                u_attr = self._attr(rPr_default, 'u', '')
                if u_attr and u_attr != 'none':
                    ts.underline = True

                strike = self._attr(rPr_default, 'strike', '')
                if strike and strike.lower() in ('1', 'true', 'sngStrike'):
                    ts.strike = True

                latin = self._find(rPr_default, 'latin')
                if latin is not None:
                    ts.font_name = self._attr(latin, 'typeface', '')

                solidFill = self._find(rPr_default, 'solidFill')
                if solidFill is not None:
                    ts.font_color = self._resolve_scheme_color(self._parse_color(solidFill))

            if not ts.is_empty:
                self.profile.title_levels.append(TitleLevelStyle(level=level, text_style=ts, used_for=usage))

    def _extract_theme_name(self, theme_root: ET.Element):
        extra = self._find(theme_root, 'extraTheme')
        if extra is not None:
            nm = self._attr(extra, 'name', '')
            if nm:
                self.profile.master.theme_name = nm

    # ----------------------------------------------------------
    # Step 2: 母版提取（尺寸+背景）
    # ----------------------------------------------------------

    def _step2_extract_master(self):
        master = self._read_xml('ppt/slideMasters/slideMaster1.xml')
        if master is None:
            logger.warning("[Step2] 无法读取 slideMaster1.xml")
            return

        sldSz = self._find(master, 'sldSz', 'p')
        if sldSz is not None:
            self.profile.master.width_emu = self._attr_int(sldSz, 'cx', 9144000)
            self.profile.master.height_emu = self._attr_int(sldSz, 'cy', 6858000)

        bg = self._find(master, 'bg', 'p')
        if bg is not None:
            self.profile.master.background = self._parse_bg_full(bg)

    # ----------------------------------------------------------
    # Step 3: 版式提取（所有版式+占位符位置+文本样式+背景）
    # ----------------------------------------------------------

    def _step3_extract_layouts(self):
        if not self._zip:
            return
        layout_files = sorted(
            [f for f in self._zip.namelist()
             if f.startswith('ppt/slideLayouts/') and f.endswith('.xml')],
            key=lambda x: int(''.join(filter(str.isdigit, x)) or '0')
        )

        for idx, lf in enumerate(layout_files):
            try:
                lr = self._read_xml(lf)
                if lr is None:
                    continue
                lp = self._build_layout_profile(lr, idx)
                self.profile.layouts.append(lp)
            except Exception as e:
                logger.warning(f"[Step3] 版式解析异常 {lf}: {e}")

    def _build_layout_profile(self, layout_root: ET.Element, idx: int) -> LayoutProfile:
        cSld = self._find(layout_root, 'cSld', 'p')
        nm_el = self._find(cSld, 'name', 'p') if cSld is not None else None
        name = self._attr(nm_el, 'val', f'Layout_{idx + 1}')

        lp = LayoutProfile(index=idx, name=name)

        if cSld is not None:
            spTree = self._find(cSld, 'spTree', 'p')
            if spTree is not None:
                self._extract_all_placeholders(spTree, lp)

            bg_el = self._find(cSld, 'bg', 'p')
            if bg_el is not None:
                lp.background = self._parse_bg_full(bg_el)

        lp.layout_type = self._infer_type(lp)
        return lp

    def _extract_all_placeholders(self, spTree: ET.Element, lp: LayoutProfile):
        shapes = self._findall(spTree, 'sp', 'p')
        for sh in shapes:
            nvSpPr = self._find(sh, 'nvSpPr', 'p')
            nvPr = self._find(nvSpPr, 'nvPr', 'p') if nvSpPr is not None else None
            if nvPr is None:
                continue

            ph = self._find(nvPr, 'ph', 'p')
            if ph is None:
                continue

            ph_idx = self._attr_int(ph, 'idx', 0)
            ph_type = self._attr(ph, 'type', 'body').lower()
            ph_name = self._attr(nvPr, 'name', f'PH_{ph_idx}')

            ps = PlaceholderStyle(idx=ph_idx, ph_type=ph_type, name=ph_name)

            spPr = self._find(sh, 'spPr', 'p')
            if spPr is not None:
                xfrm = self._find(spPr, 'xfrm', 'a')
                if xfrm is not None:
                    off = self._find(xfrm, 'off', 'a')
                    ext = self._find(xfrm, 'ext', 'a')
                    if off is not None:
                        ps.x_emu = self._attr_int(off, 'x', 0)
                        ps.y_emu = self._attr_int(off, 'y', 0)
                    if ext is not None:
                        ps.w_emu = self._attr_int(ext, 'cx', 0)
                        ps.h_emu = self._attr_int(ext, 'cy', 0)

            txBody = self._find(sh, 'txBody', 'a')
            if txBody is not None:
                ps.text_style = self._extract_txBody_style(txBody)

            lp.placeholders.append(ps)

            if ph_type in ('title', 'ctrTitle'):
                lp.has_title_ph = True
            if ph_type in ('body', 'obj', 'dt'):
                lp.has_body_ph = True

    def _extract_txBody_style(self, txBody: ET.Element) -> TextStyle:
        ts = TextStyle()

        paras = self._findall(txBody, 'p', 'a')
        if not paras:
            return ts

        p = paras[0]
        pPr = self._find(p, 'pPr', 'a')
        if pPr is not None:
            algn = self._attr(pPr, 'algn', '')
            amap = {'l': 'left', 'r': 'right', 'ctr': 'center', 'just': 'justify'}
            ts.align = amap.get(algn, '')

            buChar = self._find(pPr, 'buChar', 'a')
            if buChar is not None and self._attr(buChar, 'char', ''):
                ts.bullet_type = 'bullet'

            buAutoNum = self._find(pPr, 'buAutoNum', 'a')
            if buAutoNum is not None:
                ts.bullet_type = 'number'

            lvl = self._attr(pPr, 'lvl', '0')
            try:
                ts.indent_level = int(lvl)
            except ValueError:
                pass

            marL = self._attr(pPr, 'marL', '')
            if marL:
                try:
                    ts.margin_left = int(marL)
                except ValueError:
                    pass

            spcBef = self._find(pPr, 'spcBef', 'a')
            if spcBef is not None:
                pts = self._find(spcBef, 'pts', 'a')
                if pts is not None:
                    try:
                        ts.space_before_pt = int(pts.get('val', '0')) / 100
                    except Exception:
                        pass

            spcAft = self._find(pPr, 'spcAft', 'a')
            if spcAft is not None:
                pts = self._find(spcAft, 'pts', 'a')
                if pts is not None:
                    try:
                        ts.space_after_pt = int(pts.get('val', '0')) / 100
                    except Exception:
                        pass

            lnSpc = self._find(pPr, 'lnSpc', 'a')
            if lnSpc is not None:
                pts = self._find(lnSpc, 'pts', 'a')
                if pts is not None:
                    try:
                        ts.line_spacing = int(pts.get('val', '0')) / 100
                    except Exception:
                        pass

        runs = self._findall(p, 'r', 'a')
        if not runs:
            def_rpr = self._find(pPr, 'defRPr', 'a') if pPr is not None else None
            if def_rpr is not None:
                runs = [def_rpr]

        for r in runs:
            rPr = self._find(r, 'rPr', 'a')
            if rPr is None:
                continue

            if not ts.font_name:
                latin = self._find(rPr, 'latin', 'a')
                if latin is not None:
                    ts.font_name = self._attr(latin, 'typeface', '')

            if ts.font_size_pt == 0:
                sz = self._attr(rPr, 'sz', '')
                if sz:
                    try:
                        ts.font_size_pt = int(sz) / 100
                    except ValueError:
                        pass

            if not ts.font_color:
                sf = self._find(rPr, 'solidFill', 'a')
                if sf is not None:
                    ts.font_color = self._resolve_scheme_color(self._parse_color(sf))

            b = self._attr(rPr, 'b', '')
            if b.lower() in ('1', 'true'):
                ts.bold = True

            i = self._attr(rPr, 'i', '')
            if i.lower() in ('1', 'true'):
                ts.italic = True

            u = self._attr(rPr, 'u', '')
            if u and u != 'none':
                ts.underline = True

            strike = self._attr(rPr, 'strike', '')
            if strike.lower() in ('1', 'true', 'sngStrike', 'dblStrike'):
                ts.strike = True

        return ts

    def _parse_bg_full(self, bg_elem: ET.Element) -> BackgroundStyle:
        bs = BackgroundStyle()
        for ch in bg_elem:
            tn = _local(ch.tag)
            if tn == 'solidFill':
                bs.bg_type = 'solid'
                bs.color = self._resolve_scheme_color(self._parse_color(ch))
            elif tn == 'gradFill':
                bs.bg_type = 'gradient'
                lin = self._find(ch, 'lin', 'a')
                if lin is not None:
                    bs.gradient_angle = self._attr_int(lin, 'ang', 0) // 60000
                    sd = self._attr(lin, 'scaled', '')
                    if sd:
                        bs.gradient_type = 'rect' if sd.lower() == '1' else 'linear'
                gs_list = self._findall(ch, 'gs', 'a')
                for gs in gs_list:
                    pos_str = gs.get('pos', '0')
                    try:
                        pos_f = float(pos_str) * 100
                    except (ValueError, TypeError):
                        pos_f = 0.0
                    clr = self._resolve_scheme_color(self._parse_color(gs))
                    bs.gradient_stops.append(GradientStop(position_pct=pos_f, color=clr))
            elif tn == 'blipFill':
                bs.bg_type = 'image'
                blip = self._find(ch, 'blip', 'a')
                if blip is not None:
                    bs.image_rel_id = self._attr(blip, 'embed', '') or self._attr(blip, 'link', '')
            elif tn == 'pattFill':
                bs.bg_type = 'pattern'
                bs.color = self._attr(ch, 'prst', '')
            elif tn == 'noFill':
                bs.bg_type = 'none'
        return bs

    def _infer_type(self, lp: LayoutProfile) -> str:
        nl = lp.name.lower()
        if any(k in nl for k in ['blank', '空白']):
            return 'blank'
        if any(k in nl for k in ['title only', '标题页', '封面', 'cover']):
            return 'cover'
        if any(k in nl for k in ['toc', '目录', 'agenda', 'section header']):
            return 'toc'
        if any(k in nl for k in ['summary', '总结', 'conclusion', 'ending']):
            return 'ending'

        if lp.has_title_ph and not lp.has_body_ph:
            return 'cover'
        if lp.has_title_ph and lp.has_body_ph:
            return 'content'
        if not lp.has_title_ph and lp.has_body_ph:
            return 'content'
        return 'blank'

    # ----------------------------------------------------------
    # Step 4: 形状默认样式（从 theme/fmtScheme + slideMaster）
    # ----------------------------------------------------------

    def _step4_extract_shape_defaults(self):
        theme_root = self._read_xml('ppt/theme/theme1.xml')
        if theme_root is None:
            return
        fmt = self._find(theme_root, 'fmtScheme')
        if fmt is None:
            return

        fill_lst = self._find(fmt, 'fillStyleLst')
        if fill_lst is not None:
            items = list(fill_lst)
            if items:
                first = items[0]
                tn = _local(first.tag)
                if tn == 'solidFill':
                    sd = self.shape_defaults
                    sd.fill_type = 'solid'
                    sd.fill_color = self._resolve_scheme_color(self._parse_color(first))
                elif tn == 'gradFill':
                    self.shape_defaults.fill_type = 'grad'
                elif tn == 'noFill':
                    self.shape_defaults.fill_type = 'none'

        ln_lst = self._find(fmt, 'lnStyleLst')
        if ln_lst is not None:
            items = list(ln_lst)
            if items:
                first = items[0]
                tn = _local(first.tag)
                sd = self.shape_defaults
                if tn == 'ln':
                    sd.line_type = 'solid'
                    w = first.get('w', '')
                    try:
                        sd.line_width_pt = int(w) / 12700
                    except Exception:
                        pass
                    cap = self._find(first, 'cap', 'a')
                    if cap is not None:
                        sd.dash_type = self._attr(cap, 'prst', 'solid')
                    prstDash = self._find(first, 'prstDash', 'a')
                    if prstDash is not None:
                        sd.dash_type = self._attr(prstDash, 'val', 'solid')
                    solidFill = self._find(first, 'solidFill', 'a')
                    if solidFill is not None:
                        sd.line_color = self._resolve_scheme_color(self._parse_color(solidFill))
                elif tn == 'ln' and self._find(first, 'noFill', 'a'):
                    sd.line_type = 'none'

        eff_lst = self._find(fmt, 'effectStyleLst')
        if eff_lst is not None:
            for eff in list(eff_lst)[:1]:
                el = self._find(eff, 'effectLst')
                if el is not None:
                    for sub in el:
                        stn = _local(sub.tag)
                        if stn == 'outerShdw':
                            sd = self.shape_defaults
                            sd.shadow_enabled = True
                            sd.shadow_dist = sub.get('dist', '')
                            sd.shadow_dir = sub.get('dir', '')
                            try:
                                sd.shadow_dist_pt = int(sd.shadow_dist) / 12700
                            except Exception:
                                pass
                            try:
                                sd.shadow_angle = int(sd.shadow_dir) // 60000
                            except Exception:
                                pass
                            sc = self._find(sub, 'srgbClr', 'a')
                            if sc is not None:
                                sd.shadow_color = f'#{sc.get("val", "")}'
                            break

        master = self._read_xml('ppt/slideMasters/slideMaster1.xml')
        if master is not None:
            sp_tree = self._find(master, 'spTree', 'p')
            if sp_tree is not None:
                nvSpPr = self._find(sp_tree, 'nvGrpSpPr', 'p')
                if nvSpPr is not None:
                    grpSpPr = self._find(nvSpPr, 'grpSpPr', 'p')
                    if grpSpPr is not None:
                        self._extract_shape_spPr(grpSpPr, self.shape_defaults)

    def _extract_shape_spPr(self, spPr: ET.Element, target: ShapeDefaultStyle):
        solidFill = self._find(spPr, 'solidFill', 'a')
        if solidFill is not None and not target.fill_color:
            target.fill_color = self._resolve_scheme_color(self._parse_color(solidFill))
            target.fill_type = 'solid'

        ln = self._find(spPr, 'ln', 'a')
        if ln is not None:
            if not target.line_color:
                sf = self._find(ln, 'solidFill', 'a')
                if sf is not None:
                    target.line_color = self._resolve_scheme_color(self._parse_color(sf))
            if target.line_width_pt == 0:
                w = ln.get('w', '')
                try:
                    target.line_width_pt = int(w) / 12700
                except Exception:
                    pass

    # ----------------------------------------------------------
    # Step 5: 图表配色规则
    # ----------------------------------------------------------

    def _step5_extract_chart_rules(self):
        cr = self.profile.chart_rules

        theme_root = self._read_xml('ppt/theme/theme1.xml')
        if theme_root is None:
            return
        cs = self._find(theme_root, 'clrScheme')
        if cs is None:
            return

        accent_colors = []
        for tag in ['accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']:
            for ch in cs:
                if _local(ch.tag) == tag:
                    c = self._resolve_scheme_color(self._parse_color(ch))
                    if c.startswith('#'):
                        accent_colors.append(c)
                    break

        cr.series_colors = accent_colors
        cr.background_color = self.profile.colors.light1
        cr.plot_area_fill = self.profile.colors.light1
        cr.gridline_color = self.profile.colors.dark2 or self.profile.colors.dark1

        for ly in self.profile.layouts:
            for ph in ly.placeholders:
                if ph.ph_type in ('chart', 'tbl'):
                    if ph.text_style.font_size_pt > 0:
                        cr.axis_font_size = ph.text_style.font_size_pt
                    break

    # ----------------------------------------------------------
    # Step 6: 标题层级样式（已在 Step1 中通过 textStyles 提取）
    # ----------------------------------------------------------

    def _step6_extract_title_levels(self):
        if not self.profile.title_levels:
            fallback_h1 = TextStyle(font_size_pt=44.0, bold=True, align='center',
                                    font_name=self.profile.title_font)
            fallback_h2 = TextStyle(font_size_pt=28.0, bold=True, align='left',
                                    font_name=self.profile.title_font)
            fallback_h3 = TextStyle(font_size_pt=20.0, bold=False, align='left',
                                    font_name=self.profile.body_font)
            self.profile.title_levels = [
                TitleLevelStyle(level='h1', text_style=fallback_h1, used_for='cover_title'),
                TitleLevelStyle(level='h2', text_style=fallback_h2, used_for='content_title'),
                TitleLevelStyle(level='h3', text_style=fallback_h3, used_for='subtitle'),
            ]


# ============================================================
# 便捷入口函数
# ============================================================

def smart_extract_style(
    file_path: str,
    template_id: str = "",
    template_name: str = "",
) -> Dict[str, Any]:
    """提取模板全量样式并返回字典"""
    extractor = SmartStyleExtractor()
    profile = extractor.extract(file_path, template_id, template_name)
    return profile.to_dict()


if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("用法: python smart_style_extractor.py <pptx文件路径>")
        sys.exit(1)

    fp = sys.argv[1]
    try:
        result = smart_extract_style(fp)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
