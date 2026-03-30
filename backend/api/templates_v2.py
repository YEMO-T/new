"""
PPT模板API路由 - v2版本，支持用户模板上传和管理
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse

from core.auth import get_current_user
from service.template_service import TemplateService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["templates_v2"])


@router.post("/templates/upload")
async def upload_template(
    user_id: str = Depends(get_current_user),
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(""),
    visibility: str = Form("private")
):
    """
    上传PPT文件作为模板
    
    Parameters:
    - file: PPT文件（.pptx格式）
    - title: 模板标题
    - description: 模板描述
    - category: 分类（学术、趣味互动、简约白板、科学探究、艺术创作）
    - visibility: 可见范围（private=个人, public=公共）
    """
    try:
        if visibility not in ['private', 'public']:
            raise ValueError("visibility 必须是 'private' 或 'public'")
        
        template = await TemplateService.upload_template(
            user_id=user_id,
            file=file,
            title=title,
            description=description,
            category=category,
            visibility=visibility
        )
        
        return {
            "success": True,
            "message": "模板上传成功",
            "template": template
        }
        
    except ValueError as e:
        logger.warning(f"上传验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"上传模板异常: {e}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/templates/save-courseware")
async def save_courseware_as_template(
    user_id: str = Depends(get_current_user),
    courseware_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(""),
    visibility: str = Form("private")
):
    """
    将已生成的课件保存为模板
    
    Parameters:
    - courseware_id: 课件ID
    - title: 模板标题
    - description: 模板描述
    - category: 分类
    - visibility: 可见范围
    """
    try:
        if visibility not in ['private', 'public']:
            raise ValueError("visibility 必须是 'private' 或 'public'")
        
        template = await TemplateService.save_courseware_as_template(
            user_id=user_id,
            courseware_id=courseware_id,
            title=title,
            description=description,
            category=category,
            visibility=visibility
        )
        
        return {
            "success": True,
            "message": "课件已保存为模板",
            "template": template
        }
        
    except ValueError as e:
        logger.warning(f"保存验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"保存模板异常: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/templates/my-templates")
async def get_my_templates(
    user_id: str = Depends(get_current_user),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    获取当前用户的个人模板列表
    
    Parameters:
    - category: 可选的分类过滤
    - skip: 分页偏移
    - limit: 分页限制（最多100）
    """
    try:
        templates = await TemplateService.get_user_templates(
            user_id=user_id,
            category=category,
            skip=skip,
            limit=limit
        )
        
        return {
            "success": True,
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"获取个人模板异常: {e}")
        raise HTTPException(status_code=500, detail="获取模板列表失败")


@router.get("/templates/public")
async def get_public_templates(
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    获取公共模板列表
    
    Parameters:
    - category: 可选的分类过滤
    - skip: 分页偏移
    - limit: 分页限制
    """
    try:
        templates = await TemplateService.get_public_templates(
            category=category,
            skip=skip,
            limit=limit
        )
        
        return {
            "success": True,
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"获取公共模板异常: {e}")
        raise HTTPException(status_code=500, detail="获取模板列表失败")


@router.get("/templates/categories")
async def get_template_categories():
    """
    获取模板分类列表
    """
    categories = [
        {"id": "academic", "name": "学术", "description": "学术类课件模板"},
        {"id": "interactive", "name": "趣味互动", "description": "互动游戏类模板"},
        {"id": "minimalist", "name": "简约白板", "description": "极简主义风格模板"},
        {"id": "science", "name": "科学探究", "description": "科学实验类模板"},
        {"id": "art", "name": "艺术创作", "description": "艺术美学类模板"},
    ]
    
    return {
        "success": True,
        "categories": categories,
        "count": len(categories)
    }

@router.get("/templates/{template_id}")
async def get_template_detail(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    获取模板详情
    
    Parameters:
    - template_id: 模板ID
    """
    try:
        template = await TemplateService.get_template_by_id(template_id)
        
        if not template:
            raise HTTPException(status_code=404, detail="模板不存在")
        
        # 权限检查：只有所有者和公共模板可以查看
        if template['visibility'] != 'public' and template['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="没有权限访问此模板")
        
        return {
            "success": True,
            "template": template
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模板详情异常: {e}")
        raise HTTPException(status_code=500, detail="获取模板失败")


@router.post("/templates/{template_id}/copy")
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
        new_template = await TemplateService.copy_template(
            source_template_id=template_id,
            user_id=user_id
        )
        
        return {
            "success": True,
            "message": "模板复制成功",
            "template": new_template
        }
        
    except ValueError as e:
        logger.warning(f"复制验证失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"复制模板异常: {e}")
        raise HTTPException(status_code=500, detail="复制失败")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    删除个人模板
    
    Parameters:
    - template_id: 模板ID
    """
    try:
        success = await TemplateService.delete_template(user_id, template_id)
        
        if success:
            return {
                "success": True,
                "message": "模板已删除"
            }
        else:
            raise HTTPException(status_code=500, detail="删除失败")
            
    except ValueError as e:
        logger.warning(f"删除验证失败: {e}")
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"删除模板异常: {e}")
        raise HTTPException(status_code=500, detail="删除失败")


@router.post("/templates/{template_id}/favorite")
async def add_favorite(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    添加模板到收藏
    
    Parameters:
    - template_id: 模板ID
    """
    try:
        success = await TemplateService.add_favorite(user_id, template_id)
        
        if success:
            return {
                "success": True,
                "message": "已添加到收藏"
            }
        else:
            raise HTTPException(status_code=500, detail="添加收藏失败")
            
    except Exception as e:
        logger.error(f"添加收藏异常: {e}")
        raise HTTPException(status_code=500, detail="添加收藏失败")


@router.delete("/templates/{template_id}/favorite")
async def remove_favorite(
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    从收藏移除模板
    
    Parameters:
    - template_id: 模板ID
    """
    try:
        success = await TemplateService.remove_favorite(user_id, template_id)
        
        if success:
            return {
                "success": True,
                "message": "已从收藏移除"
            }
        else:
            raise HTTPException(status_code=500, detail="移除收藏失败")
            
    except Exception as e:
        logger.error(f"移除收藏异常: {e}")
        raise HTTPException(status_code=500, detail="移除收藏失败")


@router.get("/templates/favorites/list")
async def get_favorites(
    user_id: str = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """
    获取用户的收藏模板列表
    
    Parameters:
    - skip: 分页偏移
    - limit: 分页限制
    """
    try:
        all_favorites = await TemplateService.get_favorites(user_id)
        
        # 手动分页
        favorites = all_favorites[skip:skip + limit]
        
        return {
            "success": True,
            "templates": favorites,
            "count": len(favorites),
            "total": len(all_favorites)
        }
        
    except Exception as e:
        logger.error(f"获取收藏列表异常: {e}")
        raise HTTPException(status_code=500, detail="获取收藏列表失败")



