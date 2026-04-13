"""
PPT生成API - 基于模板生成样式完全一致的PPT
"""

import os
import logging
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.config import settings
from repository.supabase_client import get_supabase_client
from utils.ppt_generator import PPTGenerator, generate_ppt_from_template, get_template_local_path
from service.storage_service import upload_template_file, get_file_signed_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ppt", tags=["ppt_generate"])


class SlideContent(BaseModel):
    """幻灯片内容模型"""
    type: str = Field(default="content", description="幻灯片类型: cover/content/summary/ending")
    title: str = Field(default="", description="标题")
    subtitle: str = Field(default="", description="副标题")
    content: str = Field(default="", description="正文内容")
    bullets: List[str] = Field(default=[], description="要点列表")


class PPTGenerateRequest(BaseModel):
    """PPT生成请求模型"""
    template_id: str = Field(..., description="模板ID")
    title: str = Field(default="未命名演示文稿", description="PPT标题")
    slides: List[SlideContent] = Field(..., description="幻灯片内容列表")


class PPTGenerateResponse(BaseModel):
    """PPT生成响应模型"""
    success: bool
    message: str
    file_path: Optional[str] = None
    download_url: Optional[str] = None
    file_size: Optional[int] = None
    slide_count: Optional[int] = None


def get_template_info(template_id: str) -> Optional[Dict[str, Any]]:
    """获取模板信息"""
    try:
        supabase = get_supabase_client()
        response = supabase.table('user_templates').select('*').eq('id', template_id).execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"获取模板信息失败: {e}")
        return None


def download_template_if_needed(template_id: str, template_info: Dict) -> Optional[str]:
    """如果本地没有模板文件，从Storage下载"""
    local_path = get_template_local_path(template_id)
    
    if os.path.exists(local_path):
        logger.info(f"[PPT Generate] 本地模板已存在: {local_path}")
        return local_path
    
    try:
        from api.ppt_templates import download_template_from_storage
        downloaded_path = download_template_from_storage(template_id, template_info)
        if downloaded_path and os.path.exists(downloaded_path):
            logger.info(f"[PPT Generate] 模板下载成功: {downloaded_path}")
            return downloaded_path
    except Exception as e:
        logger.error(f"[PPT Generate] 下载模板失败: {e}")
    
    return None


@router.post("/generate", response_model=PPTGenerateResponse)
async def generate_ppt(
    request: PPTGenerateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    基于模板生成PPT
    
    流程：
    1. 验证模板存在且有权限访问
    2. 获取模板文件（本地或从Storage下载）
    3. 使用模板生成新PPT（保留母版和样式）
    4. 上传生成的PPT到Storage
    5. 返回下载链接
    
    Args:
        request: 生成请求
            - template_id: 模板ID
            - title: PPT标题
            - slides: 幻灯片内容列表
            
    Returns:
        生成结果，包含下载链接
    """
    try:
        logger.info(f"[PPT Generate] 用户 {user_id} 请求生成PPT，模板: {request.template_id}")
        
        template_info = get_template_info(request.template_id)
        if not template_info:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template_info.get('visibility') == 'private' and template_info.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="没有权限使用此模板")
        
        template_path = download_template_if_needed(request.template_id, template_info)
        if not template_path:
            raise HTTPException(status_code=404, detail="模板文件不可用，请重新上传模板")
        
        logger.info(f"[PPT Generate] 使用模板: {template_path}")
        
        slides_data = [slide.dict() for slide in request.slides]
        logger.info(f"[PPT Generate] 准备生成 {len(slides_data)} 页幻灯片")
        
        generator = PPTGenerator(template_path)
        ppt_bytes = generator.generate(slides_data)
        
        logger.info(f"[PPT Generate] PPT生成成功，大小: {len(ppt_bytes)} 字节")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{request.title}_{timestamp}.pptx"
        
        upload_result = upload_template_file(
            user_id=user_id,
            file_name=file_name,
            file_data=ppt_bytes
        )
        
        download_url = None
        file_path = None
        
        if upload_result:
            file_path = upload_result['path']
            bucket = upload_result['bucket']
            
            try:
                supabase = get_supabase_client()
                download_url = supabase.storage.from_(bucket).create_signed_url(
                    file_path,
                    expires_in=3600
                )
                logger.info(f"[PPT Generate] 生成下载链接成功")
            except Exception as url_err:
                logger.warning(f"[PPT Generate] 生成下载链接失败: {url_err}")
                download_url = f"/api/ppt-templates/{request.template_id}/download"
        
        local_output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'generated'
        )
        os.makedirs(local_output_dir, exist_ok=True)
        local_output_path = os.path.join(local_output_dir, f"{user_id}_{timestamp}.pptx")
        
        with open(local_output_path, 'wb') as f:
            f.write(ppt_bytes)
        logger.info(f"[PPT Generate] PPT已保存到本地: {local_output_path}")
        
        logger.info(f"[PPT Generate] PPT生成完成: {file_name}")
        
        return PPTGenerateResponse(
            success=True,
            message="PPT生成成功",
            file_path=file_path,
            download_url=download_url,
            file_size=len(ppt_bytes),
            slide_count=len(slides_data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PPT Generate] 生成PPT失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"生成PPT失败: {str(e)}"
        )


@router.post("/preview")
async def preview_ppt_structure(
    request: PPTGenerateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    预览PPT结构（不生成文件，仅返回结构信息）
    
    用于前端预览生成效果
    """
    try:
        template_info = get_template_info(request.template_id)
        if not template_info:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template_info.get('visibility') == 'private' and template_info.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="没有权限使用此模板")
        
        template_path = download_template_if_needed(request.template_id, template_info)
        if not template_path:
            raise HTTPException(status_code=404, detail="模板文件不可用")
        
        generator = PPTGenerator(template_path)
        
        layout_info = []
        for name, info in generator.slide_layouts.items():
            if isinstance(info, dict) and 'index' in info:
                layout_info.append({
                    'index': info['index'],
                    'name': info['name'],
                    'has_title': info.get('has_title', False),
                    'has_body': info.get('has_body', False),
                    'placeholder_count': len(info.get('placeholders', []))
                })
        
        slides_preview = []
        for slide in request.slides:
            layout_idx = generator.find_best_layout(slide.type)
            slides_preview.append({
                'type': slide.type,
                'title': slide.title,
                'layout_index': layout_idx,
                'layout_name': generator.slide_layouts.get(str(layout_idx), {}).get('name', 'Unknown')
            })
        
        return JSONResponse({
            "success": True,
            "template_id": request.template_id,
            "template_name": template_info.get('title', ''),
            "layouts": layout_info[:10],
            "slides_preview": slides_preview,
            "master_count": len(generator.master_styles)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PPT Preview] 预览失败: {e}")
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


@router.get("/templates/{template_id}/layouts")
async def get_template_layouts(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板的所有版式信息
    
    用于前端选择合适的版式
    """
    try:
        template_info = get_template_info(template_id)
        if not template_info:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        if template_info.get('visibility') == 'private' and template_info.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="没有权限使用此模板")
        
        template_path = download_template_if_needed(template_id, template_info)
        if not template_path:
            raise HTTPException(status_code=404, detail="模板文件不可用")
        
        generator = PPTGenerator(template_path)
        
        layouts = []
        for name, info in generator.slide_layouts.items():
            if isinstance(info, dict) and 'index' in info:
                layouts.append({
                    'index': info['index'],
                    'name': info['name'],
                    'has_title': info.get('has_title', False),
                    'has_body': info.get('has_body', False),
                    'placeholders': info.get('placeholders', [])
                })
        
        layouts = sorted([l for l in layouts if l['index'] >= 0], key=lambda x: x['index'])
        
        return JSONResponse({
            "success": True,
            "template_id": template_id,
            "template_name": template_info.get('title', ''),
            "layouts": layouts,
            "master_styles": generator.master_styles
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PPT Layouts] 获取版式失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取版式失败: {str(e)}")


@router.post("/render-enhanced", response_model=PPTGenerateResponse)
async def render_enhanced_ppt(
    request: "EnhancedPPTRenderRequest",
    user_id: str = Depends(get_current_user)
):
    """
    增强版PPT渲染接口
    
    支持：
    1. 图片占位符 - 通过 images 字段传入
    2. 表格填充 - 通过 tables 字段传入
    3. 图表生成 - 通过 charts 字段传入
    4. 模板变量替换 - 通过 variables 字段传入 {{变量名}}
    
    请求示例：
    {
        "title": "数据分析报告",
        "template_id": "xxx",
        "slides": [
            {
                "title": "销售数据概览",
                "content": ["本季度销售数据如下"],
                "page_type": "content",
                "variables": {"quarter": "Q1", "year": "2024"},
                "images": [
                    {"name": "chart_image", "source": "https://...", "source_type": "url"}
                ],
                "tables": [
                    {
                        "name": "sales_table",
                        "headers": ["产品", "销量", "金额"],
                        "rows": [["产品A", 100, 10000], ["产品B", 200, 20000]]
                    }
                ],
                "charts": [
                    {
                        "name": "sales_chart",
                        "chart_type": "column_clustered",
                        "categories": ["Q1", "Q2", "Q3", "Q4"],
                        "series": [{"name": "销售额", "values": [100, 150, 200, 180]}]
                    }
                ]
            }
        ]
    }
    """
    try:
        logger.info(f"[Enhanced Render] 用户 {user_id} 请求增强版渲染，模板: {request.template_id}")
        
        template_path = None
        
        if request.template_path and os.path.exists(request.template_path):
            template_path = request.template_path
        elif request.template_id:
            template_info = get_template_info(request.template_id)
            if not template_info:
                raise HTTPException(status_code=404, detail="模板不存在")
            
            if template_info.get('visibility') == 'private' and template_info.get('user_id') != user_id:
                raise HTTPException(status_code=403, detail="没有权限使用此模板")
            
            template_path = download_template_if_needed(request.template_id, template_info)
        
        if not template_path:
            raise HTTPException(status_code=404, detail="模板不可用")
        
        from utils.ppt_enhanced_renderer import render_enhanced_ppt as do_render
        
        slides_data = [slide.model_dump() for slide in request.slides]
        logger.info(f"[Enhanced Render] 准备渲染 {len(slides_data)} 页幻灯片")
        
        ppt_bytes = do_render(
            slides=slides_data,
            template_id=request.template_id,
            template_path=template_path
        )
        
        ppt_bytes = ppt_bytes.getvalue()
        logger.info(f"[Enhanced Render] PPT渲染成功，大小: {len(ppt_bytes)} 字节")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{request.title}_{timestamp}.pptx"
        
        upload_result = upload_template_file(
            user_id=user_id,
            file_name=file_name,
            file_data=ppt_bytes
        )
        
        download_url = None
        file_path = None
        
        if upload_result:
            file_path = upload_result['path']
            bucket = upload_result['bucket']
            
            try:
                supabase = get_supabase_client()
                download_url = supabase.storage.from_(bucket).create_signed_url(
                    file_path,
                    expires_in=3600
                )
            except Exception as url_err:
                logger.warning(f"[Enhanced Render] 生成下载链接失败: {url_err}")
        
        local_output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'generated'
        )
        os.makedirs(local_output_dir, exist_ok=True)
        local_output_path = os.path.join(local_output_dir, f"{user_id}_{timestamp}.pptx")
        
        with open(local_output_path, 'wb') as f:
            f.write(ppt_bytes)
        
        return PPTGenerateResponse(
            success=True,
            message="PPT渲染成功",
            file_path=file_path,
            download_url=download_url,
            file_size=len(ppt_bytes),
            slide_count=len(slides_data)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Enhanced Render] 渲染PPT失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"渲染PPT失败: {str(e)}"
        )


from schema.chat_schema import EnhancedPPTRenderRequest
