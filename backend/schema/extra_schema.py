from pydantic import BaseModel
from typing import List, Optional

class KnowledgeCreate(BaseModel):
    name: str
    type: str
    size: str
    tags: Optional[List[str]] = None
    content: Optional[str] = None

class KnowledgeUpdate(BaseModel):
    """
    用于知识库条目的编辑：允许用户修改名称、标签、内容（可选）
    """
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    content: Optional[str] = None
    type: Optional[str] = None
    size: Optional[str] = None

class ExportCreate(BaseModel):
    user_id: Optional[str] = None
    title: str
    format: str
    size: str
    file_url: Optional[str] = None

class TemplateResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    usage_count: int = 0
    image_url: Optional[str] = None

class PPTExportRequest(BaseModel):
    slides: List[dict]
    user_id: Optional[str] = None
    template_id: Optional[str] = None

class DocxExportRequest(BaseModel):
    lessonPlan: dict
    user_id: Optional[str] = None
