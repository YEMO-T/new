"""
PPT模板管理 API 接口
====================
功能：
1. 获取模板列表（支持 personal/public 筛选）
2. 预览 PPT 文件（返回文件流）
3. 下载 PPT 文件
4. 删除模板（同时删除 Storage 文件和数据库记录）

权限控制：
- 个人模板：仅本人可查看、删除
- 公共模板：所有人可查看，仅上传者/管理员可删除
"""

import os
import logging
import time
from typing import Optional, List
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
import jwt

from core.auth import get_current_user
from core.config import settings
from repository.supabase_client import get_supabase_client, execute_with_retry
from utils.slide_renderer import SlideRenderer
from service.storage_service import get_file_signed_url, get_file_public_url, TEMPLATE_BUCKET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ppt-templates", tags=["ppt_templates"])

JWT_ALGORITHM = "HS256"


def get_user_from_token_or_header(token: Optional[str] = None, user_id: str = Depends(get_current_user)) -> str:
    """
    从 URL 参数 token 或 Authorization header 获取用户ID
    优先使用 header 中的认证，如果失败则尝试 URL 参数
    """
    if user_id:
        return user_id
    
    if token:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            uid = payload.get("sub")
            if uid:
                return uid
        except Exception as e:
            logger.error(f"Token 验证失败: {e}")
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="缺少认证头"
    )


# ============================================================
# 响应模型
# ============================================================

class TemplateListResponse(BaseModel):
    """模板列表响应"""
    success: bool
    templates: List[dict]
    total: int
    page: int
    page_size: int


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool
    message: str


# ============================================================
# 辅助函数
# ============================================================

def check_user_role(user_id: str) -> dict:
    """
    检查用户角色
    返回: {"is_admin": bool, "role": str}
    """
    try:
        supabase = get_supabase_client()
        response = supabase.table('users').select('role').eq('id', user_id).execute()
        
        if response.data:
            role = response.data[0].get('role', 'teacher')
            return {
                "is_admin": role == 'admin',
                "role": role
            }
    except Exception as e:
        logger.error(f"检查用户角色失败: {e}")
    
    return {"is_admin": False, "role": "teacher"}


def get_template_by_id(template_id: str, table_name: str = 'user_templates') -> Optional[dict]:
    """根据ID获取模板"""
    try:
        def query_template(supabase):
            return supabase.table(table_name).select('*').eq('id', template_id).execute()
        
        response = execute_with_retry(query_template, operation_name=f"get_template_{template_id}")
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"获取模板失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"数据库连接失败，请稍后重试: {str(e)}"
        )


def get_local_template_path(template_id: str) -> Optional[str]:
    """获取本地模板文件路径"""
    local_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'templates', f"{template_id}.pptx"
    )
    if os.path.exists(local_path):
        return local_path
    return None


def download_template_from_storage(template_id: str, template_info: dict) -> Optional[str]:
    """从 Supabase Storage 下载模板文件到本地"""
    max_retries = 3
    retry_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            supabase = get_supabase_client()
            
            storage_path = template_info.get('file_path') or template_info.get('storage_path')
            if not storage_path:
                logger.warning(f"模板 {template_id} 没有文件路径")
                return None
            
            bucket_name = template_info.get('file_bucket') or 'ppt-templates'
            
            logger.info(f"[Storage] 尝试下载: bucket={bucket_name}, path={storage_path}, attempt={attempt + 1}/{max_retries}")
            
            response = None
            try:
                response = supabase.storage.from_(bucket_name).download(storage_path)
                logger.info(f"[Storage] 从 {bucket_name} 下载成功")
            except Exception as e:
                error_str = str(e)
                is_connection_error = any(err in error_str for err in [
                    '10054', '10060', '10061', '10064',
                    'ConnectionReset', 'ConnectionRefused', 
                    'Timeout', 'timed out',
                    '远程主机强迫关闭', '远程主机',
                    'SSL', 'TLS', 'handshake',
                    'EOF', 'Broken pipe'
                ])
                
                if is_connection_error and attempt < max_retries - 1:
                    logger.warning(f"[Storage] 连接错误，准备重试: {e}")
                    from repository.supabase_client import _reset_supabase_client
                    _reset_supabase_client()
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                
                logger.warning(f"[Storage] 从 {bucket_name} 下载失败: {e}")
                
                from service.storage_service import get_available_buckets
                available_buckets = get_available_buckets()
                logger.info(f"[Storage] 可用的 Buckets: {available_buckets}")
                
                downloaded = False
                for alt_bucket in available_buckets:
                    if alt_bucket == bucket_name:
                        continue
                    try:
                        response = supabase.storage.from_(alt_bucket).download(storage_path)
                        bucket_name = alt_bucket
                        logger.info(f"[Storage] 从 {alt_bucket} 下载成功")
                        downloaded = True
                        break
                    except Exception as alt_e:
                        logger.debug(f"[Storage] 从 {alt_bucket} 下载失败: {alt_e}")
                        continue
                
                if not downloaded:
                    if attempt < max_retries - 1:
                        logger.warning(f"[Storage] 所有 bucket 下载失败，准备重试")
                        from repository.supabase_client import _reset_supabase_client
                        _reset_supabase_client()
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    logger.error(f"[Storage] 无法从任何 bucket 下载文件")
                    return None
            
            if response is None:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return None
            
            local_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'templates'
            )
            os.makedirs(local_dir, exist_ok=True)
            
            local_path = os.path.join(local_dir, f"{template_id}.pptx")
            
            with open(local_path, 'wb') as f:
                f.write(response)
            
            logger.info(f"[OK] 模板文件已下载到本地: {local_path}")
            return local_path
            
        except Exception as e:
            error_str = str(e)
            is_connection_error = any(err in error_str for err in [
                '10054', '10060', '10061', '10064',
                'ConnectionReset', 'ConnectionRefused', 
                'Timeout', 'timed out',
                '远程主机强迫关闭', '远程主机',
                'SSL', 'TLS', 'handshake',
                'EOF', 'Broken pipe'
            ])
            
            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"[Storage] 连接错误，准备重试 ({attempt + 1}/{max_retries}): {e}")
                from repository.supabase_client import _reset_supabase_client
                _reset_supabase_client()
                time.sleep(retry_delay * (attempt + 1))
                continue
            
            logger.error(f"下载模板文件失败: {e}")
            return None
    
    return None


def delete_local_file(template_id: str) -> bool:
    """删除本地模板文件"""
    try:
        local_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'templates', f"{template_id}.pptx"
        )
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info(f"[OK] 已删除本地文件: {local_path}")
            return True
        return False
    except Exception as e:
        logger.warning(f"删除本地文件失败: {e}")
        return False


# ============================================================
# API 接口
# ============================================================

@router.get("", response_model=TemplateListResponse)
async def get_template_list(
    template_type: str = Query("personal", description="模板类型: personal 或 public"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    user_id: str = Depends(get_current_user)
):
    """
    获取模板列表

    Parameters:
    - template_type: 模板类型筛选
        - personal: 个人模板（仅本人可见）
        - public: 公共模板（所有人可见）
    - page: 页码
    - page_size: 每页数量
    """
    logger.info("[API] get_template_list 开始 | type=%s page=%d page_size=%d user=%s", template_type, page, page_size, user_id)

    if not user_id or not user_id.strip():
        logger.error("[API] user_id 为空")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户未登录或认证无效")

    template_type = template_type.strip().lower()
    if template_type not in ("personal", "public"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="template_type 必须是 'personal' 或 'public'")

    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    try:
        def query_templates(supabase):
            if template_type == "personal":
                return (
                    supabase.table("user_templates")
                    .select("*", count="exact")
                    .eq("user_id", user_id)
                    .eq("visibility", "private")
                    .order("created_at", desc=True)
                    .range((page - 1) * page_size, page * page_size - 1)
                    .execute()
                )
            return (
                supabase.table("user_templates")
                .select("*", count="exact")
                .eq("visibility", "public")
                .order("created_at", desc=True)
                .range((page - 1) * page_size, page * page_size - 1)
                .execute()
            )

        response = execute_with_retry(
            query_templates,
            max_retries=3,
            base_delay=1.5,
            operation_name=f"get_template_list_{template_type}",
        )

        if response is None or not hasattr(response, "data") or response.data is None:
            logger.warning("[API] 查询结果为空，返回空列表")
            return TemplateListResponse(success=True, templates=[], total=0, page=page, page_size=page_size)

        raw_items = response.data or []
        total = getattr(response, "count", None) if isinstance(getattr(response, "count", None), int) else len(raw_items)

        formatted_templates = []
        for idx, t in enumerate(raw_items):
            try:
                thumbnail_url = t.get("thumbnail_url")
                thumbnail_path = t.get("thumbnail_path")

                if thumbnail_path and not thumbnail_url:
                    try:
                        thumbnail_url = get_file_signed_url(thumbnail_path, expires_in=3600, bucket=TEMPLATE_BUCKET)
                    except Exception as thumb_err:
                        logger.debug("[API] 缩略图URL生成失败 (id=%s): %s", t.get("id"), thumb_err)
                        thumbnail_url = None
                elif thumbnail_url and thumbnail_path:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(thumbnail_url)
                        if not parsed.query or "token=" not in thumbnail_url:
                            thumbnail_url = get_file_signed_url(thumbnail_path, expires_in=3600, bucket=TEMPLATE_BUCKET)
                    except Exception as parse_err:
                        logger.debug("[API] 解析缩略图URL失败: %s", parse_err)

                formatted_templates.append({
                    "id": t.get("id") or "",
                    "user_id": t.get("user_id") or "",
                    "title": t.get("title") or "",
                    "description": t.get("description") or "",
                    "category": t.get("category") or "",
                    "visibility": t.get("visibility") or "private",
                    "source_type": t.get("source_type") or "upload",
                    "thumbnail_url": thumbnail_url,
                    "thumbnail_path": thumbnail_path,
                    "original_file_name": t.get("original_file_name") or "",
                    "original_file_size": t.get("original_file_size") or 0,
                    "usage_count": t.get("usage_count") or 0,
                    "created_at": t.get("created_at") or "",
                    "updated_at": t.get("updated_at") or "",
                    "template_data": t.get("template_data"),
                    "slides_structure": t.get("slides_structure"),
                    "theme_colors": t.get("theme_colors"),
                    "fonts": t.get("fonts"),
                    "placeholders": t.get("placeholders"),
                    "has_original_file": t.get("has_original_file") or False,
                    "file_path": t.get("file_path"),
                    "file_bucket": t.get("file_bucket"),
                })
            except Exception as fmt_err:
                logger.error("[API] 格式化模板 %d 失败: %s", idx, fmt_err)

        logger.info("[OK] 获取模板列表成功 | type=%s user=%s count=%d total=%d", template_type, user_id, len(formatted_templates), total)

        return TemplateListResponse(
            success=True,
            templates=formatted_templates,
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        conn_keywords = ("10054", "10060", "10061", "connectionreset", "connecterror", "timeout", "远程主机强迫关闭")
        is_conn = any(kw in error_str for kw in conn_keywords)

        if is_conn:
            logger.error("[ERROR] 模板列表连接异常: %s", e, exc_info=True)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库连接暂时不可用，请稍后重试")

        logger.error("[ERROR] 获取模板列表失败: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"服务内部错误，请稍后重试")


@router.get("/{template_id}")
async def get_template_info(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板详情
    
    Parameters:
    - template_id: 模板ID
    
    权限：
    - 个人模板：仅本人可查看
    - 公共模板：所有人可查看
    """
    try:
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限查看此模板"
            )
        
        logger.info(f"[OK] 获取模板详情: {template_id}")
        
        return {
            "success": True,
            "template": {
                'id': template.get('id'),
                'user_id': template.get('user_id'),
                'title': template.get('title', ''),
                'description': template.get('description', ''),
                'category': template.get('category', ''),
                'visibility': template.get('visibility', 'private'),
                'source_type': template.get('source_type', 'upload'),
                'thumbnail_url': template.get('thumbnail_url'),
                'original_file_name': template.get('original_file_name'),
                'original_file_size': template.get('original_file_size'),
                'usage_count': template.get('usage_count', 0),
                'created_at': template.get('created_at'),
                'updated_at': template.get('updated_at'),
                'template_data': template.get('template_data'),
                'theme_colors': template.get('theme_colors'),
                'fonts': template.get('fonts'),
                'slides_structure': template.get('slides_structure'),
                'placeholders': template.get('placeholders'),
                'has_original_file': template.get('has_original_file', False),
                'file_path': template.get('file_path'),
                'file_bucket': template.get('file_bucket'),
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取模板详情失败: {str(e)}"
        )


@router.get("/{template_id}/thumbnail-url")
async def get_template_thumbnail_url(
    template_id: str,
    expires_in: int = Query(3600, ge=60, le=86400, description="URL有效期(秒)"),
    user_id: str = Depends(get_current_user)
):
    """
    获取模板缩略图的签名URL
    
    用于解决私有桶图片访问 400 错误问题
    
    Parameters:
    - template_id: 模板ID
    - expires_in: URL有效期，默认1小时
    
    Returns:
    - signed_url: 签名URL（带token）
    """
    try:
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限访问此模板"
            )
        
        thumbnail_path = template.get('thumbnail_path')
        if not thumbnail_path:
            return {
                "success": False,
                "signed_url": None,
                "message": "模板没有缩略图"
            }
        
        signed_url = get_file_signed_url(thumbnail_path, expires_in=expires_in, bucket=TEMPLATE_BUCKET)
        
        if not signed_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="生成签名URL失败"
            )
        
        return {
            "success": True,
            "signed_url": signed_url,
            "expires_in": expires_in
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缩略图URL失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取缩略图URL失败: {str(e)}"
        )


@router.get("/{template_id}/preview")
async def preview_template(
    request: Request,
    template_id: str,
    token: Optional[str] = Query(None, description="认证Token（可选，用于直接访问）")
):
    """
    预览 PPT 模板 - 返回 HTML 预览页面
    
    Parameters:
    - template_id: 模板ID
    - token: 认证Token（URL参数方式，用于直接打开链接）
    
    返回:
    - HTML 预览页面
    
    权限：
    - 个人模板：仅本人可预览
    - 公共模板：所有人可预览
    """
    try:
        uid = None
        
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                header_token = auth_header.split(' ')[1]
                payload = jwt.decode(header_token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
            except:
                pass
        
        if not uid and token:
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
            except Exception as e:
                logger.error(f"Token 验证失败: {e}")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少认证头"
            )
        
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        if template.get('visibility') == 'private' and template.get('user_id') != uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限预览此模板"
            )
        
        local_path = get_local_template_path(template_id)
        
        if not local_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板文件不存在，请重新上传"
            )
        
        file_name = template.get('original_file_name') or f"{template.get('title', 'template')}.pptx"
        title = template.get('title', 'PPT模板预览')
        
        base_url = str(request.base_url).rstrip('/')
        download_url = f"{base_url}/api/ppt-templates/{template_id}/download?token={token}"
        
        html_content = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - PPT预览</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            color: white;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .header p {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .preview-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
            text-align: center;
        }}
        .file-icon {{
            font-size: 80px;
            margin-bottom: 20px;
        }}
        .file-name {{
            font-size: 20px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 10px;
            word-break: break-all;
        }}
        .file-info {{
            color: #7f8c8d;
            font-size: 14px;
            margin-bottom: 30px;
        }}
        .btn-group {{
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .btn {{
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }}
        .btn-secondary {{
            background: #f5f7fa;
            color: #667eea;
            border: 2px solid #667eea;
        }}
        .btn-secondary:hover {{
            background: #667eea;
            color: white;
        }}
        .tips {{
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: left;
        }}
        .tips h3 {{
            font-size: 14px;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .tips ul {{
            list-style: none;
            font-size: 13px;
            color: #7f8c8d;
        }}
        .tips li {{
            margin-bottom: 6px;
            padding-left: 20px;
            position: relative;
        }}
        .tips li::before {{
            content: "•";
            position: absolute;
            left: 0;
            color: #667eea;
        }}
        .loading {{
            display: none;
            text-align: center;
            padding: 20px;
        }}
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 PPT模板预览</h1>
        <p>豆沙包教师助手</p>
    </div>
    
    <div class="preview-container">
        <div class="file-icon">📊</div>
        <div class="file-name">{file_name}</div>
        <div class="file-info">
            文件大小: {template.get('original_file_size', '未知')} | 
            使用次数: {template.get('usage_count', 0)}
        </div>
        
        <div class="btn-group">
            <a href="{download_url}" class="btn btn-primary" download>
                ⬇️ 下载文件
            </a>
            <button class="btn btn-secondary" onclick="openWithOffice()">
                🖥️ 用Office打开
            </button>
        </div>
        
        <div class="tips">
            <h3>💡 预览提示</h3>
            <ul>
                <li>点击"下载文件"可将PPT保存到本地</li>
                <li>下载后使用 PowerPoint 或 WPS 打开查看</li>
                <li>支持 .pptx 格式的演示文稿</li>
            </ul>
        </div>
    </div>
    
    <script>
        function openWithOffice() {{
            // 尝试使用 ms-office 协议打开
            const fileUrl = window.location.href.replace('/preview', '/download');
            const officeUrl = 'ms-powerpoint:ofe|u|' + fileUrl;
            
            // 创建隐藏的 iframe 尝试打开
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = officeUrl;
            document.body.appendChild(iframe);
            
            // 3秒后移除 iframe
            setTimeout(() => {{
                document.body.removeChild(iframe);
            }}, 3000);
            
            alert('正在尝试用 Microsoft Office 打开...\\n如果未自动打开，请下载后手动打开。');
        }}
    </script>
</body>
</html>
'''
        
        logger.info(f"[OK] 预览模板页面: {template_id}")
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览模板失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"预览模板失败: {str(e)}"
        )


@router.get("/{template_id}/download")
async def download_template(
    request: Request,
    template_id: str,
    token: Optional[str] = Query(None, description="认证Token（可选，用于直接访问）")
):
    """
    下载 PPT 模板
    
    Parameters:
    - template_id: 模板ID
    - token: 认证Token（URL参数方式，用于直接打开链接）
    
    返回:
    - PPT 文件流（作为附件下载）
    
    权限：
    - 个人模板：仅本人可下载
    - 公共模板：所有人可下载
    """
    try:
        uid = None
        
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                header_token = auth_header.split(' ')[1]
                payload = jwt.decode(header_token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
                logger.info(f"[DOWNLOAD] 从 Header 获取用户: {uid}")
            except:
                pass
        
        if not uid and token:
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
                logger.info(f"[DOWNLOAD] 从 URL Token 获取用户: {uid}")
            except Exception as e:
                logger.error(f"Token 验证失败: {e}")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录"
            )
        
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        logger.info(f"[DOWNLOAD] 模板信息: id={template_id}, title={template.get('title')}, has_file={template.get('has_original_file')}, file_path={template.get('file_path')}, file_bucket={template.get('file_bucket')}")
        
        if template.get('visibility') == 'private' and template.get('user_id') != uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限下载此模板"
            )
        
        supabase = get_supabase_client()
        try:
            supabase.table('user_templates').update({
                'usage_count': (template.get('usage_count', 0) + 1)
            }).eq('id', template_id).execute()
        except:
            pass
        
        local_path = None
        try:
            local_path = get_local_template_path(template_id)
            logger.info(f"[DOWNLOAD] 本地文件路径: {local_path}")
            
            if not local_path:
                logger.info(f"[DOWNLOAD] 尝试从 Storage 下载文件...")
                local_path = download_template_from_storage(template_id, template)
                logger.info(f"[DOWNLOAD] Storage 下载结果: {local_path}")
        except Exception as e:
            logger.warning(f"[DOWNLOAD] 获取文件失败: {e}")
            local_path = None
        
        if local_path and os.path.exists(local_path):
            file_name = template.get('original_file_name') or f"{template.get('title', 'template')}.pptx"
            
            logger.info(f"[OK] 下载模板: {template_id}, 文件名: {file_name}")
            
            return FileResponse(
                path=local_path,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=file_name
            )
        
        logger.error(f"[DOWNLOAD] 文件不存在: template_id={template_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板文件不存在，请重新上传模板"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载模板失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载模板失败: {str(e)}"
        )


@router.delete("/{template_id}", response_model=DeleteResponse)
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除 PPT 模板
    
    Parameters:
    - template_id: 模板ID
    
    权限：
    - 个人模板：仅本人可删除
    - 公共模板：上传者或管理员可删除
    
    操作：
    1. 删除本地存储的文件
    2. 删除数据库记录
    """
    try:
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        user_role = check_user_role(user_id)
        is_owner = template.get('user_id') == user_id
        is_admin = user_role['is_admin']
        
        if not is_owner and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除此模板"
            )
        
        delete_local_file(template_id)
        
        supabase = get_supabase_client()
        supabase.table('user_templates').delete().eq('id', template_id).execute()
        
        logger.info(f"[OK] 模板删除成功: {template_id}, 删除者: {user_id}")
        
        return DeleteResponse(
            success=True,
            message="模板删除成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除模板失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模板失败: {str(e)}"
        )


@router.post("/{template_id}/copy")
async def copy_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    复制公共模板到个人库
    
    Parameters:
    - template_id: 源模板ID
    """
    try:
        supabase = get_supabase_client()
        
        source = get_template_by_id(template_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="源模板不存在"
            )
        
        if source.get('visibility') != 'public':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能复制公共模板"
            )
        
        copy_data = {
            'user_id': user_id,
            'title': f"{source.get('title', '')} (副本)",
            'description': source.get('description', ''),
            'category': source.get('category', ''),
            'source_type': source.get('source_type', 'upload'),
            'visibility': 'private',
            'template_data': source.get('template_data'),
            'theme_colors': source.get('theme_colors'),
            'fonts': source.get('fonts'),
            'placeholders': source.get('placeholders'),
            'original_file_name': source.get('original_file_name'),
            'usage_count': 0,
        }
        
        response = supabase.table('user_templates').insert(copy_data).execute()
        
        if response.data:
            template = response.data[0]
            
            local_path = get_local_template_path(template_id)
            if local_path:
                import shutil
                new_local_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    'data', 'templates', f"{template['id']}.pptx"
                )
                os.makedirs(os.path.dirname(new_local_path), exist_ok=True)
                shutil.copy2(local_path, new_local_path)
                logger.info(f"[OK] 复制模板文件: {template_id} -> {template['id']}")
            
            logger.info(f"[OK] 模板复制成功: {template_id} -> {template['id']}")
            
            return {
                "success": True,
                "message": "模板复制成功",
                "template": template
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="复制失败"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"复制模板失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"复制模板失败: {str(e)}"
        )


@router.get("/{template_id}/slides")
async def get_template_slides(
    request: Request,
    template_id: str,
    token: Optional[str] = Query(None, description="认证Token")
):
    """
    获取模板幻灯片图片列表（用于翻页预览）
    
    Parameters:
    - template_id: 模板ID
    - token: 认证Token
    
    返回:
    - 幻灯片图片列表（base64格式）
    """
    local_path = None
    try:
        uid = None
        
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            try:
                header_token = auth_header.split(' ')[1]
                payload = jwt.decode(header_token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
                logger.info(f"[AUTH] 从 Header 获取用户: {uid}")
            except Exception as e:
                logger.warning(f"Header Token 解析失败: {e}")
        
        if not uid and token:
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                uid = payload.get("sub")
                logger.info(f"[AUTH] 从 URL Token 获取用户: {uid}")
            except Exception as e:
                logger.error(f"Token 验证失败: {e}")
        
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录"
            )
        
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        logger.info(f"[TEMPLATE] 模板信息: id={template_id}, title={template.get('title')}, has_file={template.get('has_original_file')}, file_path={template.get('file_path')}, file_bucket={template.get('file_bucket')}")
        
        if template.get('visibility') == 'private' and template.get('user_id') != uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限查看此模板"
            )
        
        try:
            local_path = get_local_template_path(template_id)
            logger.info(f"[LOCAL] 本地文件路径: {local_path}")
            
            if not local_path:
                logger.info(f"[STORAGE] 尝试从 Storage 下载文件...")
                local_path = download_template_from_storage(template_id, template)
                logger.info(f"[STORAGE] 下载结果: {local_path}")
        except Exception as e:
            logger.warning(f"[STORAGE] 获取文件失败: {e}")
            local_path = None
        
        if local_path and os.path.exists(local_path):
            try:
                logger.info(f"[RENDER] 开始渲染幻灯片: {local_path}")
                slides = SlideRenderer.render_pptx_to_images(local_path)
                logger.info(f"[RENDER] 渲染完成: {len(slides)} 页")
                
                return JSONResponse({
                    "success": True,
                    "template_id": template_id,
                    "title": template.get('title', ''),
                    "total_slides": len(slides),
                    "slides": slides,
                    "preview_type": "rendered"
                })
            except Exception as render_err:
                logger.error(f"[RENDER] 渲染失败: {render_err}")
        
        logger.warning(f"[FALLBACK] 文件不存在或渲染失败，返回预览占位符")
        page_count = 1
        template_data = template.get('template_data', {})
        if template_data and isinstance(template_data, dict):
            page_count = template_data.get('page_count', 1) or 1
        
        slides = SlideRenderer._create_placeholder_slides(page_count)
        
        return JSONResponse({
            "success": True,
            "template_id": template_id,
            "title": template.get('title', ''),
            "total_slides": len(slides),
            "slides": slides,
            "preview_type": "placeholder",
            "message": "模板文件不可用，显示占位预览"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取幻灯片失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取幻灯片失败: {str(e)}"
        )


@router.post("/{template_id}/extract-style")
async def extract_template_style(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    提取模板样式元数据
    
    从指定的 PPT 模板中提取可复用的样式信息，用于后续生成同风格 PPT
    
    Returns:
        - title_font: 标题字体样式（字体名、大小、颜色、粗体、斜体）
        - body_font: 正文字体样式
        - theme_colors: 主题颜色（背景色、强调色）
        - slide_layouts: 幻灯片布局信息
        - background_styles: 背景样式
        - extracted_styles: 可直接用于生成 PPT 的样式配置
    """
    from utils.ppt_style_extractor import extract_ppt_style_metadata
    
    try:
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限查看此模板"
            )
        
        local_path = get_local_template_path(template_id)
        
        if not local_path:
            local_path = download_template_from_storage(template_id, template)
        
        if not local_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板文件不存在"
            )
        
        with open(local_path, 'rb') as f:
            ppt_bytes = f.read()
        
        style_metadata = extract_ppt_style_metadata(ppt_bytes)
        
        if style_metadata.get("success"):
            logger.info(f"[OK] 提取模板样式成功: {template_id}")
        else:
            logger.warning(f"提取模板样式部分失败: {style_metadata.get('error')}")
        
        return JSONResponse(style_metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取模板样式失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取模板样式失败: {str(e)}"
        )


@router.post("/extract-style-from-file")
async def extract_style_from_file(
    user_id: str = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """
    从上传的 PPT 文件中提取样式元数据
    
    无需保存模板，直接从上传的文件提取样式
    
    Returns:
        样式元数据 JSON
    """
    from utils.ppt_style_extractor import extract_ppt_style_metadata
    
    try:
        if not file.filename or not file.filename.lower().endswith(('.pptx', '.ppt')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请上传 .pptx 或 .ppt 格式的文件"
            )
        
        ppt_bytes = await file.read()
        
        style_metadata = extract_ppt_style_metadata(ppt_bytes)
        
        if style_metadata.get("success"):
            logger.info(f"[OK] 从文件提取样式成功: {file.filename}")
        else:
            logger.warning(f"提取样式部分失败: {style_metadata.get('error')}")
        
        return JSONResponse(style_metadata)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从文件提取样式失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取样式失败: {str(e)}"
        )


class SlideData(BaseModel):
    """单页幻灯片数据"""
    type: str = "content"
    title: str = ""
    content: List[str] = []
    subtitle: str = ""


class GeneratePPTRequest(BaseModel):
    """生成 PPT 请求"""
    slides: List[SlideData] = []
    title: str = "未命名演示文稿"


@router.post("/{template_id}/generate")
async def generate_ppt_from_template(
    template_id: str,
    request: GeneratePPTRequest,
    user_id: str = Depends(get_current_user)
):
    """
    根据模板样式生成新 PPT
    
    使用指定模板的字体、颜色、布局风格，生成内容全新的 PPT 文件。
    
    Args:
        template_id: 模板 ID
        request: 包含 slides 数组的请求数据
            - slides[].type: 页面类型 (cover/content/toc/ending)
            - slides[].title: 页面标题
            - slides[].content: 内容列表
            - slides[].subtitle: 副标题
            
    Returns:
        - download_url: 生成的 PPT 下载链接
        - file_name: 文件名
        - slide_count: 幻灯片数量
    """
    from utils.ppt_style_generator import generate_ppt_with_style
    from datetime import datetime
    
    try:
        template = get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板不存在"
            )
        
        if template.get('visibility') == 'private' and template.get('user_id') != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限使用此模板"
            )
        
        local_path = get_local_template_path(template_id)
        
        if not local_path:
            local_path = download_template_from_storage(template_id, template)
        
        if not local_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模板文件不存在"
            )
        
        with open(local_path, 'rb') as f:
            template_bytes = f.read()
        
        slides_data = [slide.dict() for slide in request.slides]
        
        if not slides_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供幻灯片内容"
            )
        
        ppt_stream = generate_ppt_with_style(template_bytes, slides_data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{request.title}_{timestamp}.pptx"
        
        supabase = get_supabase_client()
        
        storage_path = f"generated/{user_id}/{timestamp}_{file_name}"
        
        try:
            supabase.storage.from_('coursewares').upload(
                storage_path,
                ppt_stream.getvalue(),
                {"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
            )
            
            download_url = supabase.storage.from_('coursewares').get_public_url(storage_path)
            
            logger.info(f"[OK] PPT 已上传到 Storage: {storage_path}")
            
        except Exception as e:
            logger.warning(f"上传到 Storage 失败: {e}, 使用本地存储")
            
            local_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'generated'
            )
            os.makedirs(local_dir, exist_ok=True)
            
            local_file_path = os.path.join(local_dir, f"{timestamp}_{file_name}")
            
            with open(local_file_path, 'wb') as f:
                f.write(ppt_stream.getvalue())
            
            download_url = f"/api/ppt-templates/download/local/{timestamp}_{file_name}"
        
        return JSONResponse({
            "success": True,
            "download_url": download_url,
            "file_name": file_name,
            "slide_count": len(slides_data),
            "template_id": template_id,
            "template_name": template.get('title', ''),
            "generated_at": timestamp
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 PPT 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成 PPT 失败: {str(e)}"
        )


@router.get("/download/local/{file_name}")
async def download_local_file(
    file_name: str,
    user_id: str = Depends(get_current_user)
):
    """
    下载本地生成的 PPT 文件
    """
    local_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'generated', file_name
    )
    
    if not os.path.exists(local_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    return FileResponse(
        local_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=file_name
    )
