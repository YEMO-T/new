from pydantic import BaseModel, field_validator
from typing import List, Optional, Union, Dict, Any
from enum import Enum


class ChartTypeEnum(str, Enum):
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


class ImagePlaceholderModel(BaseModel):
    """图片占位符模型"""
    name: str
    source: str
    source_type: str = "url"
    width: Optional[float] = None
    height: Optional[float] = None
    fit: str = "contain"


class TableDataModel(BaseModel):
    """表格数据模型"""
    name: str
    headers: List[str]
    rows: List[List[Any]]
    style: Optional[str] = None


class ChartSeriesModel(BaseModel):
    """图表系列模型"""
    name: str
    values: List[Union[int, float]]


class ChartDataModel(BaseModel):
    """图表数据模型"""
    name: str
    chart_type: ChartTypeEnum = ChartTypeEnum.COLUMN_CLUSTERED
    categories: List[str]
    series: List[ChartSeriesModel]
    title: Optional[str] = None
    show_legend: bool = True
    legend_position: str = "bottom"


class EnhancedPPTSlide(BaseModel):
    """增强版幻灯片数据模型"""
    title: str = ""
    content: Union[str, List[str]] = ""
    page_type: Optional[str] = "content"
    type: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    images: Optional[List[ImagePlaceholderModel]] = None
    tables: Optional[List[TableDataModel]] = None
    charts: Optional[List[ChartDataModel]] = None
    
    @field_validator('page_type', mode='before')
    @classmethod
    def set_page_type(cls, v, info):
        if v:
            return v
        if info.data.get('type'):
            return info.data.get('type')
        return 'content'
    
    @field_validator('content', mode='before')
    @classmethod
    def normalize_content(cls, v):
        if isinstance(v, str):
            return [v] if v else []
        return v or []


class EnhancedPPTRenderRequest(BaseModel):
    """增强版PPT渲染请求"""
    slides: List[EnhancedPPTSlide]
    title: str
    template_id: Optional[str] = None
    template_path: Optional[str] = None


class FileInfo(BaseModel):
    name: str
    size: str
    status: Optional[str] = "completed"
    mimeType: Optional[str] = None
    data: Optional[str] = None

class MessageModel(BaseModel):
    id: str
    role: str
    content: str
    type: Optional[str] = "text"
    fileInfo: Optional[FileInfo] = None

class ChatRequest(BaseModel):
    prompt: str
    history: List[MessageModel] = []

# --- PPT 生成相关模型 ---

class PPTSlide(BaseModel):
    """单页 PPT 结构化数据 - 兼容前端格式，支持增强功能"""
    title: str
    content: Union[str, List[str]] = ""
    page_type: Optional[str] = None
    type: Optional[str] = None
    layout_suggestion: Optional[str] = "bullet_points"
    imagePrompt: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    images: Optional[List[ImagePlaceholderModel]] = None
    tables: Optional[List[TableDataModel]] = None
    charts: Optional[List[ChartDataModel]] = None
    
    @field_validator('page_type', mode='before')
    @classmethod
    def set_page_type(cls, v, info):
        if v:
            return v
        if info.data.get('type'):
            return info.data.get('type')
        return 'content'
    
    @field_validator('content', mode='before')
    @classmethod
    def normalize_content(cls, v):
        if isinstance(v, str):
            return [v] if v else []
        return v or []

class PPTGenerateRequest(BaseModel):
    """PPT 生成请求参数"""
    theme: str
    audience: Optional[str] = "学生"
    page_count: Optional[int] = 10
    style: Optional[str] = "简约、专业、教学风格"
    grade: Optional[str] = "通用"
    subject: Optional[str] = "通用"
    template_id: Optional[str] = None

class PPTGenerateResponse(BaseModel):
    """PPT 生成响应（结构化内容）"""
    slides: List[PPTSlide]
    title: str
    description: Optional[str] = None
    user_id: Optional[str] = "default_user"
    file_url: Optional[str] = None # 生成后的文件下载链接
    storage_path: Optional[str] = None # 在 Supabase 中的路径

class PPTRenderRequest(BaseModel):
    """全量模板渲染请求"""
    slides: List[PPTSlide]
    title: str
    template_id: Optional[str] = None
    lesson_plan: Optional[dict] = None
    interaction: Optional[dict] = None

class DecomposeRequest(BaseModel):
    prompt: str
    grade: Optional[str] = "通用"
    subject: Optional[str] = "通用"
    template_id: Optional[str] = None
    history: List[MessageModel] = []

class SlideTask(BaseModel):
    page: int
    topic: str
    layout_suggestion: Optional[str] = "content"
    description: Optional[str] = ""

class SlideGenerateRequest(BaseModel):
    task: SlideTask
    context: Optional[str] = ""  # 整个大纲的上下文
    user_id: str
    template_id: Optional[str] = None
    history: List[MessageModel] = []

class DocxRenderRequest(BaseModel):
    """教案 Docx 渲染请求"""
    title: str
    lesson_plan: dict
