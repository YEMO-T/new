from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
from repository.supabase_client import get_exports, delete_export, get_supabase_client
from core.auth import get_current_user
import os
import tempfile
import requests
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/exports")
async def list_exports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user)
):
    """
    获取用户的导出记录列表（分页）
    """
    try:
        exports = get_exports(user_id)
        
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_exports = exports[start:end]
        
        return {
            "success": True,
            "data": {
                "records": paginated_exports,
                "total": len(exports),
                "page": page,
                "page_size": page_size,
                "total_pages": (len(exports) + page_size - 1) // page_size
            }
        }
    except Exception as e:
        logger.error(f"获取导出记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导出记录失败: {str(e)}")

@router.get("/exports/{export_id}")
async def get_export_detail(export_id: str, user_id: str = Depends(get_current_user)):
    """
    获取单条导出记录详情
    """
    try:
        exports = get_exports(user_id)
        export_record = next((exp for exp in exports if exp.get("id") == export_id), None)
        
        if not export_record:
            raise HTTPException(status_code=404, detail="导出记录不存在")
            
        return {
            "success": True,
            "data": export_record
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取导出详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导出详情失败: {str(e)}")

@router.get("/exports/{export_id}/download")
async def download_export_file(export_id: str, user_id: str = Depends(get_current_user)):
    """
    根据导出记录ID下载文件（支持云端URL和本地文件）
    """
    try:
        exports = get_exports(user_id)
        export_record = next((exp for exp in exports if exp.get("id") == export_id), None)
        
        if not export_record:
            raise HTTPException(status_code=404, detail="导出记录不存在")
            
        file_url = export_record.get("file_url")
        title = export_record.get("title", "未命名课件")
        fmt = export_record.get("format", "pptx").lower()
        
        if not file_url:
            raise HTTPException(status_code=400, detail="该导出记录没有关联的文件")
        
        import re
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:50]
        file_name = f"{safe_title}.{fmt}"
        
        if file_url.startswith('http://') or file_url.startswith('https://'):
            response = requests.get(file_url, stream=True, timeout=30)
            
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="无法从远程服务器获取文件")
                
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}")
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
            
            def cleanup_temp():
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            
            return FileResponse(
                temp_file.name,
                media_type=_get_media_type(fmt),
                filename=file_name,
                background=BackgroundTask(cleanup_temp)
            )
        else:
            local_path = _resolve_local_path(file_url)
            
            if not local_path or not os.path.exists(local_path):
                raise HTTPException(status_code=404, detail="本地文件不存在或已被删除")
                
            return FileResponse(
                local_path,
                media_type=_get_media_type(fmt),
                filename=file_name
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载导出文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

@router.delete("/exports/{export_id}")
async def remove_export(export_id: str, user_id: str = Depends(get_current_user)):
    """
    删除导出记录（仅删除数据库记录，不删除实际文件）
    """
    try:
        res = delete_export(export_id, user_id)
        if res is None:
            raise HTTPException(status_code=404, detail="记录不存在或无权删除")
        return {"status": "success", "message": "已删除导出记录"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除导出记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

@router.delete("/exports/batch")
async def batch_remove_exports(export_ids: list[str], user_id: str = Depends(get_current_user)):
    """
    批量删除导出记录
    """
    try:
        deleted_count = 0
        failed_ids = []
        
        for export_id in export_ids:
            res = delete_export(export_id, user_id)
            if res is not None:
                deleted_count += 1
            else:
                failed_ids.append(export_id)
                
        return {
            "status": "success",
            "message": f"成功删除{deleted_count}条记录",
            "deleted_count": deleted_count,
            "failed_ids": failed_ids
        }
    except Exception as e:
        logger.error(f"批量删除导出记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除失败: {str(e)}")

def _get_media_type(fmt: str) -> str:
    """根据文件格式返回MIME类型"""
    mime_types = {
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg'
    }
    return mime_types.get(fmt.lower(), 'application/octet-stream')

def _resolve_local_path(file_url: str) -> Optional[str]:
    """解析本地文件路径"""
    if file_url.startswith('/local/'):
        relative_path = file_url[7:]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, relative_path.lstrip('/'))
    
    if os.path.isabs(file_url) and os.path.exists(file_url):
        return file_url
    
    return None

@router.get("/local/{file_path:path}")
async def download_local_file(file_path: str, user_id: str = Depends(get_current_user)):
    """
    下载本地存储的PPT文件
    
    路径格式: /local/coursewares/{user_id}/{filename}
             /local/temp_exports/{filename}
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 安全检查：防止路径遍历攻击
        safe_path = file_path.replace('..', '').replace('//', '/')
        full_path = os.path.join(base_dir, 'data', safe_path)
        
        # 规范化路径，确保在允许的目录内
        full_path = os.path.normpath(full_path)
        allowed_base = os.path.normpath(os.path.join(base_dir, 'data'))
        
        if not full_path.startswith(allowed_base):
            raise HTTPException(status_code=403, detail="访问被拒绝：路径不在允许范围内")
        
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="文件不存在或已被删除")
            
        # 从文件名推断MIME类型
        _, ext = os.path.splitext(full_path)
        ext = ext.lower().lstrip('.')
        media_type = _get_media_type(ext) if ext else 'application/octet-stream'
        
        # 提取文件名
        filename = os.path.basename(full_path)
        
        logger.info(f"[LocalDownload] 用户 {user_id} 下载本地文件: {full_path}")
        
        return FileResponse(
            full_path,
            media_type=media_type,
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LocalDownload] 本地文件下载失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")