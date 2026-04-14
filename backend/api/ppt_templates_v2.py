"""
智能模板库管理系统 API (v2.0)
=============================

核心功能：
1. ✅ 上传模板时自动提取样式（纯视觉信息，不含原始内容）
2. ✅ 模板浏览展示样式画像（颜色/字体/版式）
3. ✅ 生成PPT时直接渲染最终版本（使用 UltimateRenderer）
4. ✅ 完整的导出记录管理（Storage存储 + 数据库记录 + 本地下载）

架构特点：
- 样式与内容分离：数据库只存样式基因
- 直接生成：无预览步骤，一步到位
- 完整追踪：每次导出都有详细记录

API 端点：
POST   /api/ppt-templates/v2/upload          - 上传并提取样式
GET    /api/ppt-templates/v2                  - 获取模板列表（含样式摘要）
GET    /api/ppt-templates/v2/{id}/style       - 获取模板完整样式
GET    /api/ppt-templates/v2/{id}/preview     - 获取样式预览图
POST   /api/ppt-templates/v2/{id}/generate    - 生成最终PPT
GET    /api/ppt-templates/v2/exports           - 获取导出记录列表
GET    /api/ppt-templates/v2/exports/{id}     - 获取导出详情
GET    /api/ppt-templates/v2/exports/{id}/download - 下载导出的PPT
DELETE /api/ppt-templates/v2/exports/{id}     - 删除导出记录
DELETE /api/ppt-templates/v2/{id}             - 删除模板（级联清理）
"""

import os
import json
import uuid
import logging
import tempfile
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

from repository.supabase_client import get_supabase_client, execute_with_retry
from service.storage_service import (
    upload_template_file,
    delete_file as storage_delete_file,
    get_file_signed_url,
    get_file_public_url,
    TEMPLATE_BUCKET,
)
from utils.style_extractor import PPTStyleExtractor, extract_style_from_pptx
from utils.ultimate_renderer import UltimateRenderer, render_ultimate_ppt
from core.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ppt-templates/v2", tags=["ppt_templates_v2"])


# ============================================================
# Pydantic Models (请求/响应模型)
# ============================================================

class SlideData(BaseModel):
    """单页幻灯片数据"""
    title: str = Field(..., description="页面标题")
    subtitle: str = Field("", description="副标题")
    content: List[str] = Field(default_factory=list, description="内容列表")
    page_type: str = Field("content", description="页面类型: cover/content/toc/ending")


class GenerateRequest(BaseModel):
    """PPT生成请求"""
    title: str = Field(..., description="演示文稿标题")
    slides: List[SlideData] = Field(..., description="幻灯片数据列表")
    auto_export: bool = Field(True, description="是否自动保存到导出记录")


class TemplateListResponse(BaseModel):
    """模板列表响应"""
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
    generated_at: str = ""


class ExportRecordResponse(BaseModel):
    """导出记录响应"""
    success: bool = True
    exports: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ============================================================
# 核心功能实现
# ============================================================

@router.post("/upload", response_model=Dict[str, Any])
async def upload_template_with_style_extraction(
    request: Request,
    file: UploadFile = File(..., description="PPTX 模板文件"),
    title: str = Query("", description="模板标题"),
    visibility: str = Query("private", description="可见性: private/public"),
    user_id: str = Depends(get_current_user)
):
    """
    上传模板并自动提取样式

    流程：
    1. 接收上传的 PPTX 文件
    2. 保存到本地临时位置
    3. 使用 StyleExtractor 提取纯样式信息
    4. 上传原始文件到 Storage
    5. 将样式数据存入数据库（不包含原始内容！）
    6. 返回成功信息和样式摘要

    特点：
    - 数据库只存储样式基因（颜色、字体、版式结构）
    - 不存储任何示例文字或装饰元素
    - 用户浏览时看到的是"风格画像"而非原始内容
    """
    logger.info(f"[v2/Upload] 开始上传: user={user_id}, file={file.filename}")

    try:
        # 1. 验证文件类型
        if not file.filename or not file.filename.lower().endswith('.pptx'):
            raise HTTPException(status_code=400, detail="只支持 .pptx 格式")

        # 2. 读取文件内容
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:  # 50MB 限制
            raise HTTPException(status_code=400, detail="文件大小不能超过 50MB")

        # 3. 保存到临时文件用于样式提取
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        template_id = str(uuid.uuid4())
        temp_path = os.path.join(temp_dir, f"{template_id}.pptx")

        with open(temp_path, 'wb') as f:
            f.write(content)

        logger.info(f"[v2/Upload] 文件已保存: {temp_path}, 大小: {len(content)} 字节")

        # 4. 提取样式（核心步骤！使用智能提取器）
        try:
            logger.info(f"[v2/Upload] 开始智能提取样式...")
            from utils.smart_style_extractor import SmartStyleExtractor
            
            smart_extractor = SmartStyleExtractor()
            style_profile = smart_extractor.extract(
                file_path=temp_path,
                template_id=template_id,
                template_name=title or file.filename
            )
            style_data = style_profile.to_dict()

            logger.info(f"[v2/Upload] 智能样式提取成功:")
            logger.info(f"  - 主色调: {style_profile.primary_color}")
            logger.info(f"  - 标题字体: {style_profile.title_font}")
            logger.info(f"  - 正文字体: {style_profile.body_font}")
            logger.info(f"  - 版式数: {style_profile.layout_count}")

        except Exception as e:
            logger.error(f"[v2/Upload] 智能样式提取失败: {e}, 尝试旧版提取器...")
            
            try:
                style_extractor = PPTStyleExtractor()
                style_profile = style_extractor.extract(
                    file_path=temp_path,
                    template_id=template_id,
                    template_name=title or file.filename
                )
                style_data = style_profile.to_dict()
                
                logger.info(f"[v2/Upload] 旧版样式提取成功（降级模式）")
            except Exception as e2:
                logger.error(f"[v2/Upload] 旧版样式提取也失败: {e2}")
                style_data = {
                    'template_id': template_id,
                    'template_name': title or file.filename,
                    'extracted_at': datetime.now().isoformat(),
                    'error': f"样式提取失败: {str(e)}",
                    'color_scheme': {},
                'font_scheme': {},
                'layouts': [],
                'total_layouts': 0,
                'summary': {}
            }

        # 5. 上传到 Storage（使用正确的参数签名）
        try:
            storage_info = upload_template_file(
                user_id=user_id,
                file_name=file.filename or f"{template_id}.pptx",
                file_data=content,
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

            if storage_info:
                file_bucket = storage_info.get('bucket', TEMPLATE_BUCKET)
                file_path = storage_info.get('path', f"templates/{user_id}/{template_id}.pptx")
            else:
                raise Exception("Storage返回空结果")

            logger.info(f"[v2/Upload] 已上传到 Storage: bucket={file_bucket}, path={file_path}")

        except Exception as e:
            logger.warning(f"[v2/Upload] Storage 上传失败: {e}, 使用本地存储")

            import shutil

            local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
            os.makedirs(local_dir, exist_ok=True)

            file_bucket = "local"
            file_path = os.path.join(local_dir, f"{template_id}.pptx")
            shutil.copy2(temp_path, file_path)
            logger.info(f"[v2/Upload] 已保存到本地: {file_path}")

        # 6. 保存到数据库（只存样式，不存原始内容！）
        supabase = get_supabase_client()

        db_record = {
            'id': template_id,
            'user_id': user_id,
            'title': title or file.filename,
            'filename': file.filename,
            'source_type': 'upload',
            'template_data': style_data or {},
            'visibility': visibility,
            'file_bucket': file_bucket,
            'file_path': file_path,
            'file_size': len(content),

            # === 核心改进：存储样式基因 ===
            'style_gene': style_data,
            'style_extracted': True,
            'style_extracted_at': datetime.now().isoformat(),

            # 统计信息
            'usage_count': 0,

            # 时间戳
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }

        result = supabase.table('user_templates').insert(db_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="数据库写入失败")

        # 7. 清理临时文件
        try:
            if os.path.exists(temp_path) and file_bucket != "local":
                os.remove(temp_path)
        except Exception:
            pass

        logger.info(f"[v2/Upload] 上传完成: id={template_id}")

        return {
            "success": True,
            "message": "模板上传成功，样式已自动提取",
            "template_id": template_id,
            "style_summary": {
                "total_layouts": style_data.get('total_layouts', 0),
                "main_font": style_data.get('font_scheme', {}).get('major_latin', ''),
                "primary_color": style_data.get('color_scheme', {}).get('accent1', ''),
                "aspect_ratio": style_data.get('summary', {}).get('aspect_ratio', ''),
            },
            "title": title or file.filename,
            "created_at": db_record['created_at'],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Upload] 上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("", response_model=TemplateListResponse)
async def get_template_list_with_styles(
    template_type: str = Query("personal", description="personal 或 public"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user)
):
    """
    获取模板列表（含样式摘要）

    返回的每个模板都包含：
    - 基础信息（ID、标题、时间等）
    - **样式画像摘要**（主字体、主色调、版式数量等）

    注意：不返回原始PPT内容，只返回风格特征！
    """
    logger.info(f"[v2/List] 获取列表: type={template_type}, page={page}")

    try:
        def query(supabase):
            base = supabase.table("user_templates").select("*", count="exact")

            if template_type == "personal":
                query = base.eq("user_id", user_id).eq("visibility", "private")
            else:
                query = base.eq("visibility", "public")

            return (
                query
                .order("created_at", desc=True)
                .range((page - 1) * page_size, page * page_size - 1)
                .execute()
            )

        response = execute_with_retry(query, max_retries=3)

        if not response or not response.data:
            return TemplateListResponse(templates=[], total=0)

        # 格式化输出（只返回样式摘要，不返回完整样式数据）
        formatted = []
        for t in response.data:
            style_gene = t.get('style_gene') or {}

            item = {
                'id': t.get('id'),
                'title': t.get('title'),
                'created_at': t.get('created_at'),
                'usage_count': t.get('usage_count', 0),

                # === 样式画像（轻量级） ===
                'style_preview': {
                    'total_layouts': style_gene.get('total_layouts', 0),
                    'main_font': style_gene.get('font_scheme', {}).get('major_latin', ''),
                    'primary_color': style_gene.get('color_scheme', {}).get('accent1', ''),
                    'aspect_ratio': style_gene.get('summary', {}).get('aspect_ratio', ''),
                    'has_style': bool(style_gene.get('color_scheme')),
                },

                # 缩略图（如果有）
                'thumbnail_url': t.get('thumbnail_url'),
            }

            formatted.append(item)

        total = getattr(response, 'count', len(response.data))

        return TemplateListResponse(
            templates=formatted,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"[v2/List] 列表获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{template_id}/style", response_model=StyleResponse)
async def get_template_complete_style(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板完整样式数据

    用于：
    - 在编辑器中显示完整的样式配置
    - 生成PPT时加载样式规则
    - 高级用户查看详细信息

    返回完整的样式基因数据（JSON格式）
    """
    logger.info(f"[v2/Style] 获取样式: template_id={template_id}")

    try:
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

        # 权限检查
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="无权访问此模板")

        style_data = template.get('style_gene') or {}

        if not style_data:
            raise HTTPException(status_code=404, detail="该模板尚未提取样式")

        return StyleResponse(
            template_id=template_id,
            style_data=style_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Style] 获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/generate", response_model=GenerateResponse)
async def generate_final_ppt(
    template_id: str,
    request: GenerateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    生成最终渲染好的 PPT（直接版本，无预览）

    使用 UltimateRenderer 直接生成最终可用的 PPTX 文件：
    - ✅ 继承模板的完整视觉风格（字体/颜色/版式）
    - ✅ 只包含用户提供的内容（无模板残留）
    - ✅ 一步到位，无需后续处理
    - ✅ 自动保存到导出记录

    流程：
    1. 加载模板样式（从数据库或文件）
    2. 使用 UltimateRenderer 创建全新演示文稿
    3. 填充用户内容（保持样式一致）
    4. 保存到 Storage 和本地
    5. 创建导出记录
    6. 返回下载链接
    """
    from datetime import datetime

    logger.info(f"[v2/Generate] 开始生成: template={template_id}, slides={len(request.slides)}")

    try:
        # 1. 获取模板信息
        supabase = get_supabase_client()
        response = (
            supabase.table("user_templates")
            .select("*")
            .eq("id", template_id)
            .execute()
        )

        if not response or not response.data:
            raise HTTPException(status_code=404, detail="模板不存在")

        template = response.data[0]

        # 权限检查
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="无权使用此模板")

        # 2. 获取模板文件路径
        local_path = _get_local_template_path(template_id, template)

        if not local_path:
            raise HTTPException(status_code=404, detail="模板文件不存在")

        # 3. 准备幻灯片数据
        slides_data = [slide.dict() for slide in request.slides]

        if not slides_data:
            raise HTTPException(status_code=400, detail="请提供幻灯片内容")

        logger.info(f"[v2/Generate] 使用 UltimateRenderer 生成...")

        # 4. 使用终极渲染器生成（核心步骤！）
        output_stream = BytesIO()

        try:
            renderer = UltimateRenderer(local_path)
            ppt_stream = renderer.render(slides_data)
            output_stream.write(ppt_stream.getvalue())
        except Exception as render_err:
            logger.warning(f"[v2/Generate] UltimateRenderer 失败: {render_err}")
            # 降级到标准渲染器
            from utils.ppt_enhanced_renderer import render_enhanced_ppt
            ppt_io = render_enhanced_ppt(slides_data, template_id)
            if ppt_io:
                output_stream = ppt_io
            else:
                raise HTTPException(status_code=500, detail="所有渲染器均失败")

        ppt_content = output_stream.getvalue()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{request.title}_{timestamp}.pptx"
        export_id = str(uuid.uuid4())

        # 5. 保存到 Storage
        storage_path = f"exports/{user_id}/{export_id}_{file_name}"
        download_url = None

        try:
            supabase.storage.from_('coursewares').upload(
                storage_path,
                ppt_content,
                {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            )
            download_url = supabase.storage.from_('coursewares').get_public_url(storage_path)
            logger.info(f"[v2/Generate] 已上传到 Storage: {storage_path}")
        except Exception as storage_err:
            logger.warning(f"[v2/Generate] Storage 上传失败: {storage_err}, 使用本地存储")

            # 保存到本地
            local_export_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'exports'
            )
            os.makedirs(local_export_dir, exist_ok=True)

            local_file_path = os.path.join(local_export_dir, f"{export_id}_{file_name}")
            with open(local_file_path, 'wb') as f:
                f.write(ppt_content)

            download_url = f"/api/ppt-templates/v2/exports/{export_id}/download"

        # 6. 创建导出记录（如果启用）
        if request.auto_export:
            try:
                export_record = {
                    'id': export_id,
                    'user_id': user_id,
                    'template_id': template_id,
                    'template_name': template.get('title', ''),
                    'title': request.title,
                    'file_name': file_name,
                    'file_size': len(ppt_content),
                    'format': 'pptx',
                    'storage_bucket': 'coursewares',
                    'storage_path': storage_path if download_url and 'http' in download_url else None,
                    'local_path': local_file_path if 'http' not in (download_url or '') else None,
                    'download_url': download_url,
                    'slide_count': len(slides_data),
                    'status': 'completed',
                    'created_at': datetime.now().isoformat(),
                }

                supabase.table('ppt_exports').insert(export_record).execute()
                logger.info(f"[v2/Generate] 导出记录已创建: {export_id}")
            except Exception as export_err:
                logger.warning(f"[v2/Generate] 导出记录创建失败: {export_err}")

        # 7. 更新模板使用次数
        try:
            supabase.table('user_templates').update({
                'usage_count': (template.get('usage_count', 0) + 1),
                'updated_at': datetime.now().isoformat(),
            }).eq('id', template_id).execute()
        except Exception:
            pass

        logger.info(f"[v2/Generate] 生成完成: id={export_id}, size={len(ppt_content)} bytes")

        return GenerateResponse(
            export_id=export_id,
            download_url=download_url or "",
            file_name=file_name,
            slide_count=len(slides_data),
            generated_at=datetime.now().isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Generate] 生成失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/exports", response_model=ExportRecordResponse)
async def list_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user)
):
    """
    获取导出记录列表

    返回当前用户的所有导出记录，包括：
    - 文件名、大小、格式
    - 使用的模板信息
    - 生成时间
    - 下载链接
    """
    logger.info(f"[v2/Exports] 获取列表: user={user_id}, page={page}")

    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table("ppt_exports")
            .select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range((page - 1) * page_size, page * page_size - 1)
            .execute()
        )

        if not response or not response.data:
            return ExportRecordResponse(exports=[], total=0)

        total = getattr(response, 'count', len(response.data))

        return ExportRecordResponse(
            exports=response.data,
            total=total,
        )

    except Exception as e:
        logger.error(f"[v2/Exports] 列表获取失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports/{export_id}")
async def get_export_detail(
    export_id: str,
    user_id: str = Depends(get_current_user)
):
    """获取单个导出记录详情"""
    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table("ppt_exports")
            .select("*")
            .eq("id", export_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response or not response.data:
            raise HTTPException(status_code=404, detail="导出记录不存在")

        return {"success": True, "data": response.data[0]}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Export Detail] 获取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    下载导出的 PPT 文件

    支持：
    - 从 Storage 下载（如果有 URL）
    - 从本地文件系统下载
    - 307 重定向到公开链接
    """
    logger.info(f"[v2/Download] 下载: export_id={export_id}")

    try:
        supabase = get_supabase_client()

        response = (
            supabase
            .table("ppt_exports")
            .select("*")
            .eq("id", export_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response or not response.data:
            raise HTTPException(status_code=404, detail="导出记录不存在")

        export_record = response.data[0]
        file_name = export_record.get('file_name', 'presentation.pptx')

        # 方案1: 如果有公开URL，重定向
        public_url = export_record.get('download_url')
        if public_url and public_url.startswith('http'):
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=public_url)

        # 方案2: 从本地路径下载
        local_path = export_record.get('local_path')
        if local_path and os.path.exists(local_path):
            return FileResponse(
                local_path,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=file_name,
            )

        # 方案3: 从 Storage 下载
        storage_path = export_record.get('storage_path')
        bucket = export_record.get('storage_bucket', 'coursewares')

        if storage_path:
            try:
                signed_url = get_file_signed_url(storage_path, expires_in=3600, bucket=bucket)
                if signed_url:
                    from fastapi.responses import RedirectResponse
                    return RedirectResponse(url=signed_url)
            except Exception as e:
                logger.warning(f"[v2/Download] 签名URL生成失败: {e}")

        raise HTTPException(status_code=404, detail="文件不可用")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Download] 下载失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/exports/{export_id}")
async def delete_export_record(
    export_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除导出记录（同时清理文件）

    操作：
    1. 删除本地文件（如果存在）
    2. 删除 Storage 文件（如果存在）
    3. 删除数据库记录
    """
    logger.info(f"[v2/Delete Export] 删除: export_id={export_id}")

    try:
        supabase = get_supabase_client()

        # 获取记录
        response = (
            supabase
            .table("ppt_exports")
            .select("*")
            .eq("id", export_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not response or not response.data:
            raise HTTPException(status_code=404, detail="记录不存在")

        record = response.data[0]

        # 删除本地文件
        local_path = record.get('local_path')
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.info(f"[v2/Delete Export] 本地文件已删除: {local_path}")
            except Exception as e:
                logger.warning(f"[v2/Delete Export] 本地文件删除失败: {e}")

        # 删除 Storage 文件
        storage_path = record.get('storage_path')
        bucket = record.get('storage_bucket')
        if storage_path and bucket:
            try:
                storage_delete_file(storage_path, bucket)
                logger.info(f"[v2/Delete Export] Storage文件已删除: {storage_path}")
            except Exception as e:
                logger.warning(f"[v2/Delete Export] Storage删除失败: {e}")

        # 删除数据库记录
        supabase.table('ppt_exports').delete().eq('id', export_id).execute()

        logger.info(f"[v2/Delete Export] 记录已删除: {export_id}")

        return {"success": True, "message": "导出记录已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Delete Export] 删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{template_id}")
async def delete_template_cascade(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除模板（级联清理）

    执行以下操作：
    1. 删除本地模板文件
    2. 删除 Storage 中的模板文件
    3. 清理相关的导出记录和文件
    4. 删除数据库中的模板记录（包括样式数据）
    """
    logger.info(f"[v2/Delete Template] 删除: template_id={template_id}")

    try:
        supabase = get_supabase_client()

        # 获取模板信息
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

        # 权限检查
        is_owner = template.get('user_id') == user_id
        # 可以添加管理员检查...

        if not is_owner:
            raise HTTPException(status_code=403, detail="无权删除此模板")

        operations = []

        # 1. 删除本地文件
        local_path = _get_local_template_path(template_id, template)
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                operations.append("本地文件: ✓")
            except Exception as e:
                operations.append(f"本地文件: ⊘ ({e})")
        else:
            operations.append("本地文件: ⊘ (不存在)")

        # 2. 删除 Storage 文件
        file_path = template.get('file_path')
        file_bucket = template.get('file_bucket')
        if file_path and file_bucket and file_bucket != "local":
            try:
                storage_delete_file(file_path, file_bucket)
                operations.append("Storage文件: ✓")
            except Exception as e:
                operations.append(f"Storage文件: ⊘ ({e})")
        else:
            operations.append("Storage文件: ⊘ (无)")

        # 3. 清理关联的导出记录
        try:
            exports_response = (
                supabase
                .table("ppt_exports")
                .select("id")
                .eq("template_id", template_id)
                .eq("user_id", user_id)
                .execute()
            )

            if exports_response and exports_response.data:
                cleaned = 0
                for exp in exports_response.data[:10]:  # 限制数量
                    try:
                        # 递归调用删除逻辑（简化版）
                        exp_local = exp.get('local_path')
                        if exp_local and os.path.exists(exp_local):
                            os.remove(exp_local)

                        exp_storage = exp.get('storage_path')
                        exp_bucket = exp.get('storage_bucket')
                        if exp_storage and exp_bucket:
                            storage_delete_file(exp_storage, exp_bucket)

                        cleaned += 1
                    except Exception:
                        continue

                # 批量删除记录
                supabase.table('ppt_exports').delete().eq(
                    'template_id', template_id
                ).eq('user_id', user_id).execute()

                operations.append(f"导出记录: ✓ ({cleaned}个)")
            else:
                operations.append("导出记录: ⊘ (无)")
        except Exception as e:
            operations.append(f"导出记录: ⊘ ({e})")

        # 4. 删除主记录（包括样式数据）
        supabase.table('user_templates').delete().eq('id', template_id).execute()
        operations.append("数据库记录: ✓ (含样式)")

        logger.info(f"[v2/Delete Template] 删除完成: {template_id}")
        logger.info(f"[v2/Delete Template] 操作: {' | '.join(operations)}")

        return {
            "success": True,
            "message": f"模板已完全删除（{sum(1 for o in operations if '✓' in o)}/{len(operations)} 项）",
            "operations": operations,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[v2/Delete Template] 删除失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 辅助函数
# ============================================================

def _get_local_template_path(template_id: str, template_info: dict = None) -> Optional[str]:
    """
    获取模板文件的本地路径（多级查找策略）

    查找顺序：
    1. 标准本地路径 data/templates/{id}.pptx
    2. 数据库记录中的 file_path 字段
    3. 从 Storage 下载到本地缓存
    4. 临时文件路径 data/temp/{id}.pptx（兼容旧逻辑）
    """
    backend_dir = os.path.dirname(os.path.dirname(__file__))

    # 方法1: 标准路径
    standard_path = os.path.join(backend_dir, 'data', 'templates', f"{template_id}.pptx")
    if os.path.exists(standard_path):
        logger.debug(f"[Path] 找到标准路径: {standard_path}")
        return standard_path

    # 方法2: 从数据库记录中获取
    if template_info:
        file_path = template_info.get('file_path')
        if file_path and os.path.exists(file_path):
            logger.debug(f"[Path] 找到DB路径: {file_path}")
            return file_path

        # 方法3: 尝试从Storage下载（如果记录中有storage信息）
        storage_path = template_info.get('file_path')
        bucket = template_info.get('file_bucket')

        if storage_path and bucket and bucket != "local":
            downloaded = _download_template_from_storage(template_id, template_info)
            if downloaded:
                return downloaded

    # 方法4: 临时文件路径（最后手段）
    temp_path = os.path.join(backend_dir, 'data', 'temp', f"{template_id}.pptx")
    if os.path.exists(temp_path):
        logger.debug(f"[Path] 找到临时路径: {temp_path}")
        return temp_path

    logger.warning(f"[Path] 未找到模板文件: template_id={template_id}")
    return None


def _download_template_from_storage(template_id: str, template_info: dict) -> Optional[str]:
    """
    从 Storage 下载模板文件到本地缓存

    Returns:
        本地文件路径 或 None
    """
    try:
        supabase = get_supabase_client()

        storage_path = template_info.get('file_path')
        bucket = template_info.get('file_bucket') or TEMPLATE_BUCKET

        if not storage_path or not bucket:
            return None

        # 下载文件
        response = supabase.storage.from_(bucket).download(storage_path)

        if not response:
            return None

        # 保存到本地缓存
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
        os.makedirs(cache_dir, exist_ok=True)

        local_path = os.path.join(cache_dir, f"{template_id}.pptx")
        with open(local_path, 'wb') as f:
            f.write(response)

        logger.info(f"[Download] 已从 Storage 下载模板: {template_id} -> {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"[Download] 从 Storage 下载失败: {e}")
        return None


# ============================================================
# 注册路由（在 main.py 中导入）
# ============================================================

def register_routes(app):
    """注册所有路由到 FastAPI 应用"""
    app.include_router(router)
    logger.info("[v2/Router] 智能模板库路由已注册")
