from pydantic import BaseModel
from typing import List, Optional

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
    """单页 PPT 结构化数据"""
    title: str
    content: List[str]
    page_type: str  # cover, toc, content, ending
    layout_suggestion: Optional[str] = "bullet_points"

class PPTGenerateRequest(BaseModel):
    """PPT 生成请求参数"""
    theme: str
    audience: Optional[str] = "学生"
    page_count: Optional[int] = 10
    style: Optional[str] = "简约、专业、教学风格"
    grade: Optional[str] = "通用"
    subject: Optional[str] = "通用"

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
    template_id: str
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
