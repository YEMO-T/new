"""
智能模板库管理 API (v3.0)
==========================

完整功能：
1. ✅ 上传模板 + 自动提取完整样式基因
2. ✅ 模板列表（含样式摘要：颜色/字体/版式数）
3. ✅ 获取模板完整样式（供PPT生成模块调用）
4. ✅ 删除/复制/重新提取样式
5. ✅ 使用模板生成最终渲染好的 PPT

架构特点：
- 样式与内容分离存储
- 智能缓存机制
- 完整的降级保障
- 端到端可追溯

API 端点：
POST   /api/template-library/upload           - 上传并提取样式
GET    /api/template-library/list             - 获取列表（含样式摘要）
GET    /api/template-library/{id}/style       - 获取完整样式
GET    /api/template-library/{id}/detail      - 获取模板详情
POST   /api/template-library/{id}/generate    - 生成最终PPT
DELETE /api/template-library/{id}             - 删除模板
POST   /api/template-library/{id}/copy        - 复制到个人库
POST   /api/template-library/{id}/reextract  - 重新提取样式
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from io import BytesIO

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    UploadFile,
    File,
    Request,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from core.auth import get_current_user
from service.template_library_service import (
    TemplateLibraryService,
    get_template_library_service,
)
from utils.intelligent_ppt_builder import IntelligentPPTBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/template-library", tags=["template_library"])


# ============================================================
# Pydantic Models (请求/响应模型)
# ============================================================

class SlideDataInput(BaseModel):
    """单页幻灯片输入"""
    title: str = Field(..., description="页面标题")
    subtitle: str = Field("", description="副标题")
    content: List[str] = Field(default_factory=list, description="内容列表")
    page_type: str = Field("content", description="页面类型: cover/content/toc/summary/ending")


class GeneratePPTRequest(BaseModel):
    """生成PPT请求"""
    title: str = Field(..., description="演示文稿标题")
    slides: List[SlideDataInput] = Field(..., description="幻灯片数据")
    auto_export: bool = Field(True, description="是否保存导出记录")


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool = True
    template_id: str = ""
    title: str = ""
    message: str = ""
    style_extracted: bool = False
    style_summary: Optional[Dict[str, Any]] = None


class TemplateListResponse(BaseModel):
    """列表响应"""
    success: bool = True
    templates: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class StyleResponse(BaseModel):
    """样式响应"""
    success: bool = True
    template_id: str = ""
    style_data: Dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    """生成响应"""
    success: bool = True
    export_id: str = ""
    download_url: str = ""
    file_name: str = ""
    slide_count: int = 0
    engine_used: str = ""


# ============================================================
# API 端点实现
# ============================================================

@router.post("/upload", response_model=UploadResponse)
async def upload_template_with_style(
    request: Request,
    file: UploadFile = File(..., description="PPTX 模板文件"),
    title: str = Query("", description="模板标题"),
    visibility: str = Query("private", description="可见性: private/public"),
    user_id: str = Depends(get_current_user)
):
    """
    上传模板并自动提取完整样式基因
    
    提取的样式信息包括：
    - 颜色方案（主色调、强调色、文字色等）
    - 字体方案（标题字体、正文字体）
    - 版式结构（封面、内页、结尾等布局）
    - 占位符格式（字体大小、颜色、对齐方式）
    
    所有样式信息会结构化存储到数据库，
    供后续 PPT 生成模块直接调用。
    """
    logger.info(f"[TemplateLib-API] 上传请求: user={user_id}, file={file.filename}")
    
    if not file.filename or not file.filename.lower().endswith('.pptx'):
        raise HTTPException(status_code=400, detail="只支持 .pptx 格式")
    
    content = await file.read()
    
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 50MB")
    
    svc = get_template_library_service()
    
    result = svc.upload_and_extract(
        file_content=content,
        filename=file.filename or "template.pptx",
        user_id=user_id,
        title=title,
        visibility=visibility,
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)
    
    return UploadResponse(
        success=result.success,
        template_id=result.template_id,
        title=result.title,
        message=result.message,
        style_extracted=result.style_extracted,
        style_summary=result.style_summary,
    )


@router.get("/list", response_model=TemplateListResponse)
async def get_template_list(
    template_type: str = Query("personal", description="personal 或 public"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="搜索关键词"),
    user_id: str = Depends(get_current_user)
):
    """
    获取模板列表（含样式摘要）
    
    返回每个模板的轻量级样式信息：
    - primary_color: 主色调
    - title_font: 标题字体
    - body_font: 正文字体
    - layout_count: 版式数量
    - aspect_ratio: 比例 (16:9 或 4:3)
    """
    logger.info(f"[TemplateLib-API] 列表请求: type={template_type}, page={page}, search={search}")
    
    svc = get_template_library_service()
    
    items, total = svc.get_template_list(
        user_id=user_id,
        template_type=template_type,
        page=page,
        page_size=page_size,
        search_query=search,
    )
    
    formatted = []
    for item in items:
        formatted.append({
            'id': item.id,
            'title': item.title,
            'created_at': item.created_at,
            'usage_count': item.usage_count,
            'file_size': item.file_size,
            'style_preview': {
                'primary_color': item.primary_color,
                'title_font': item.title_font,
                'body_font': item.body_font,
                'layout_count': item.layout_count,
                'aspect_ratio': item.aspect_ratio,
                'has_style': item.has_style,
            },
        })
    
    return TemplateListResponse(
        templates=formatted,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{template_id}/style", response_model=StyleResponse)
async def get_template_style(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板完整样式数据
    
    这是供 PPT 生成模块调用的核心接口。
    返回完整的样式基因，包括：
    - colors: 完整的颜色方案
    - fonts: 字体配置
    - layouts: 所有版式及其占位符格式
    - master: 母版设置（背景、尺寸等）
    """
    logger.info(f"[TemplateLib-API] 样式请求: template={template_id}")
    
    svc = get_template_library_service()
    
    style_data = svc.get_template_style_json(template_id)
    
    if not style_data:
        raise HTTPException(status_code=404, detail="模板不存在或未提取样式")
    
    return StyleResponse(
        template_id=template_id,
        style_data=style_data,
    )


@router.get("/{template_id}/detail")
async def get_template_detail(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板详情（含完整样式和元数据）
    
    用于前端展示模板详情页。
    """
    logger.info(f"[TemplateLib-API] 详情请求: template={template_id}")
    
    from repository.supabase_client import get_supabase_client
    
    supabase = get_supabase_client()
    
    response = (
        supabase
        .table("user_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    
    if not response or not response.data:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    template = response.data[0]
    
    if template.get('visibility') == 'private' and template.get('user_id') != user_id:
        raise HTTPException(status_code=403, detail="无权访问此模板")
    
    style_gene = template.get('style_gene') or {}
    summary = style_gene.get('_summary', {})
    
    return {
        "success": True,
        "template": {
            'id': template.get('id'),
            'title': template.get('title'),
            'filename': template.get('filename'),
            'created_at': template.get('created_at'),
            'updated_at': template.get('updated_at'),
            'usage_count': template.get('usage_count', 0),
            'file_size': template.get('file_size', 0),
            'visibility': template.get('visibility', 'private'),
            'style_extracted': template.get('style_extracted', False),
            
            # 完整样式
            'colors': style_gene.get('colors', {}),
            'fonts': style_gene.get('fonts', {}),
            'layouts': style_gene.get('layouts', []),
            'master': style_gene.get('master', {}),
            
            # 样式摘要
            'style_preview': {
                'primary_color': summary.get('primary_color', ''),
                'title_font': summary.get('title_font', ''),
                'body_font': summary.get('body_font', ''),
                'layout_count': summary.get('layout_count', 0),
                'aspect_ratio': summary.get('aspect_ratio', ''),
                'has_style': bool(summary.get('primary_color')),
            },
        },
    }


@router.post("/{template_id}/generate", response_model=GenerateResponse)
async def generate_ppt_with_template(
    template_id: str,
    request: GeneratePPTRequest,
    user_id: str = Depends(get_current_user)
):
    """
    使用模板生成最终渲染好的 PPT
    
    完整流程：
    1. 加载模板样式基因
    2. 使用 IntelligentPPTBuilder 创建新PPT
    3. 应用完整样式（字体/颜色/版式）
    4. 上传到 Storage 并返回下载链接
    
    支持自动降级：如果新引擎失败，回退到 clean_renderer
    """
    from repository.supabase_client import get_supabase_client
    
    logger.info(f"[TemplateLib-API] 生成PPT: template={template_id}, slides={len(request.slides)}")
    
    supabase = get_supabase_client()
    
    template_resp = (
        supabase
        .table("user_templates")
        .select("*")
        .eq("id", template_id)
        .execute()
    )
    
    if not template_resp or not template_resp.data:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    template = template_resp.data[0]
    
    slides_data = [slide.dict() for slide in request.slides]
    
    builder = IntelligentPPTBuilder()
    
    try:
        result_bytes, engine_used = builder.build_with_fallback(
            slides_data=slides_data,
            template_id=template_id,
            title=request.title,
        )
    except Exception as e:
        logger.error(f"[TemplateLib-API] 生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"PPT生成失败: {str(e)}")
    
    export_id = f"exp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id[:8]}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{request.title}_{timestamp}.pptx"
    
    storage_path = f"exports/{user_id}/{export_id}_{file_name}"
    download_url = None
    
    try:
        supabase.storage.from_('coursewares').upload(
            storage_path,
            result_bytes,
            {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
        )
        
        download_url = supabase.storage.from_('coursewares').get_public_url(storage_path)
        
        logger.info(f"[TemplateLib-API] 已上传: {storage_path}")
        
    except Exception as e:
        logger.warning(f"[TemplateLib-API] Storage上传失败: {e}")
        download_url = f"/api/template-library/{export_id}/download"
    
    if request.auto_export:
        try:
            export_record = {
                'id': export_id,
                'user_id': user_id,
                'template_id': template_id,
                'template_name': template.get('title', ''),
                'title': request.title,
                'file_name': file_name,
                'file_size': len(result_bytes),
                'format': 'pptx',
                'storage_bucket': 'coursewares',
                'storage_path': storage_path,
                'download_url': download_url,
                'slide_count': len(slides_data),
                'engine_used': engine_used,
                'status': 'completed',
                'created_at': datetime.now().isoformat(),
            }
            
            supabase.table('ppt_exports').insert(export_record).execute()
            
        except Exception as e:
            logger.debug(f"[TemplateLib-API] 导出记录创建失败: {e}")
    
    try:
        supabase.table('user_templates').update({
            'usage_count': (template.get('usage_count', 0) or 0) + 1,
            'updated_at': datetime.now().isoformat(),
        }).eq('id', template_id).execute()
    except Exception:
        pass
    
    return GenerateResponse(
        success=True,
        export_id=export_id,
        download_url=download_url or "",
        file_name=file_name,
        slide_count=len(slides_data),
        engine_used=engine_used,
    )


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """删除模板（同时清理 Storage 和数据库）"""
    logger.info(f"[TemplateLib-API] 删除请求: template={template_id}, user={user_id}")
    
    svc = get_template_library_service()
    
    success, message = svc.delete_template(template_id, user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.post("/{template_id}/copy")
async def copy_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """复制公共模板到个人库"""
    logger.info(f"[TemplateLib-API] 复制请求: template={template_id}, to={user_id}")
    
    svc = get_template_library_service()
    
    success, message, new_id = svc.copy_template_to_user(template_id, user_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "new_template_id": new_id,
    }


@router.post("/{template_id}/reextract")
async def reextract_template_style(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    重新提取模板样式
    
    用于修复之前失败的样式提取，或更新样式数据。
    """
    logger.info(f"[TemplateLib-API] 重新提取: template={template_id}")
    
    svc = get_template_library_service()
    
    success, message, style_data = svc.reextract_style(template_id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    summary = style_data.get('_summary', {}) if style_data else {}
    
    return {
        "success": True,
        "message": message,
        "style_summary": summary,
    }


@router.get("/categories")
async def get_categories(user_id: str = Depends(get_current_user)):
    """获取模板分类列表"""
    return {
        "success": True,
        "categories": [
            {"id": "education", "name": "教育培训", "icon": "📚"},
            {"id": "business", "name": "商业汇报", "icon": "💼"},
            {"id": "creative", "name": "创意设计", "icon": "🎨"},
            {"id": "technology", "name": "科技互联网", "icon": "💻"},
            {"id": "simple", "name": "简约清新", "icon": "✨"},
            {"id": "festival", "name": "节日庆典", "icon": "🎉"},
        ],
    }
