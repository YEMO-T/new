"""
PPT模板管理服务 - 处理模板上传、保存、应用等业务逻辑
优化版本：使用 Supabase Storage 存储文件
集成PPT模板标准化功能
"""

import logging
import tempfile
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from fastapi import UploadFile

from repository.supabase_client import get_supabase_client
from service.ppt_parser import extract_template_from_pptx
from service.storage_service import (
    upload_template_file,
    upload_template_thumbnail,
    get_file_public_url,
    get_file_signed_url,
    delete_file,
    TEMPLATE_BUCKET
)
from utils.ppt_template_standardizer import make_qualified_ppt_template
from utils.slide_renderer import SlideRenderer

logger = logging.getLogger(__name__)


def get_supabase_with_retry(max_retries: int = 3, delay: float = 1.0):
    """带重试的 Supabase 客户端获取"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return get_supabase_client()
        except Exception as e:
            last_error = e
            logger.warning(f"Supabase 连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
    raise last_error


class TemplateService:
    """PPT模板管理服务"""
    
    @staticmethod
    async def upload_template(
        user_id: str,
        file: UploadFile,
        title: str,
        description: str,
        category: str,
        visibility: str = 'private',
        applicable_scenarios: str = None
    ) -> Dict[str, Any]:
        """
        上传PPT文件作为模板
        
        Args:
            user_id: 用户ID
            file: PPT文件
            title: 模板标题
            description: 模板描述
            category: 分类
            visibility: 可见性 (private/public)
            applicable_scenarios: 适用场景
        """
        temp_file_path = None
        try:
            if not file.filename.lower().endswith('.pptx'):
                raise ValueError("只支持 .pptx 格式的PPT文件")
            
            temp_file_path = tempfile.mktemp(suffix='.pptx')
            contents = await file.read()
            
            logger.info(f"[UPLOAD] 用户 {user_id} 上传PPT: {file.filename} ({len(contents)} 字节)")
            
            logger.info(f"[STANDARDIZE] 开始标准化PPT模板...")
            standardized_contents = make_qualified_ppt_template(contents)
            logger.info(f"[STANDARDIZE] 标准化完成，输出大小: {len(standardized_contents)} 字节")
            
            with open(temp_file_path, 'wb') as f:
                f.write(standardized_contents)
            
            file_size = os.path.getsize(temp_file_path)
            logger.info(f"[UPLOAD] 标准化后文件大小: {file_size} 字节")
            
            template_data = extract_template_from_pptx(temp_file_path)
            
            supabase = get_supabase_with_retry()
            
            slides_structure = template_data.get('slides_structure', [])
            
            simplified_template_data = {
                'page_count': template_data.get('page_count', 0),
                'slide_dimensions': template_data.get('slide_dimensions'),
                'theme_colors': template_data.get('theme_colors'),
                'fonts': template_data.get('fonts'),
            }
            
            insert_data = {
                'user_id': user_id,
                'title': title,
                'description': description,
                'category': category if category else '未分类',
                'source_type': 'upload',
                'visibility': visibility,
                'template_data': simplified_template_data,
                'slides_structure': slides_structure,
                'theme_colors': template_data.get('theme_colors'),
                'fonts': template_data.get('fonts'),
                'placeholders': template_data.get('placeholders'),
                'thumbnail_url': None,
                'original_file_name': file.filename,
                'original_file_size': f"{file_size / 1024:.2f} KB",
                'usage_count': 0,
                'applicable_scenarios': applicable_scenarios,
                'has_original_file': False,
            }
            
            response = supabase.table('user_templates').insert(insert_data).execute()
            
            if not response.data:
                raise Exception("插入数据库失败")
            
            template = response.data[0]
            template_id = template['id']
            
            local_template_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'templates'
            )
            os.makedirs(local_template_dir, exist_ok=True)
            local_template_path = os.path.join(local_template_dir, f"{template_id}.pptx")
            
            with open(local_template_path, 'wb') as f:
                f.write(standardized_contents)
            logger.info(f"[OK] 模板文件已保存到本地: {local_template_path}")
            
            try:
                logger.info(f"[THUMBNAIL] 生成预览缩略图...")
                preview_slides = SlideRenderer.render_pptx_to_images(local_template_path, max_slides=1)
                if preview_slides and len(preview_slides) > 0:
                    first_slide = preview_slides[0]
                    image_data_url = first_slide.get('image', '')
                    if image_data_url and image_data_url.startswith('data:image/png;base64,'):
                        import base64
                        thumbnail_bytes = base64.b64decode(image_data_url.replace('data:image/png;base64,', ''))
                        
                        thumbnail_result = upload_template_thumbnail(
                            user_id=user_id,
                            template_id=template_id,
                            thumbnail_data=thumbnail_bytes
                        )
                        
                        if thumbnail_result:
                            thumbnail_url = get_file_public_url(
                                thumbnail_result['path'],
                                bucket=TEMPLATE_BUCKET
                            )
                            if thumbnail_url:
                                supabase.table('user_templates').update({
                                    'thumbnail_url': thumbnail_url,
                                    'thumbnail_path': thumbnail_result['path']
                                }).eq('id', template_id).execute()
                                template['thumbnail_url'] = thumbnail_url
                                logger.info(f"[OK] 预览缩略图已上传: {thumbnail_url}")
            except Exception as thumb_err:
                logger.warning(f"[WARN] 生成预览缩略图失败: {thumb_err}")
            
            storage_result = upload_template_file(
                user_id=user_id,
                file_name=file.filename,
                file_data=standardized_contents
            )
            
            if storage_result:
                supabase.table('user_templates').update({
                    'file_path': storage_result['path'],
                    'file_bucket': storage_result['bucket'],
                    'file_size_bytes': storage_result['size'],
                    'has_original_file': True
                }).eq('id', template_id).execute()
                
                template['file_path'] = storage_result['path']
                template['file_bucket'] = storage_result['bucket']
                template['has_original_file'] = True
                
                logger.info(f"[OK] 模板文件已上传到 Storage: {storage_result['path']}")
            else:
                logger.warning(f"[WARN] 模板文件上传到 Storage 失败，仅保存到本地")
            
            # 自动提取样式基因并保存到数据库
            try:
                logger.info(f"[STYLE_EXTRACT] 开始自动提取模板样式...")
                from service.template_style_service import extract_and_save_template_style
                
                style_extracted = extract_and_save_template_style(
                    template_path=local_template_path,
                    template_id=template_id,
                    template_name=title
                )
                
                if style_extracted:
                    logger.info(f"[STYLE_EXTRACT] 样式提取并保存成功!")
                    template['style_extracted'] = True
                else:
                    logger.warning(f"[STYLE_EXTRACT] 样式保存失败（不影响上传）")
                    
            except Exception as style_err:
                logger.warning(f"[STYLE_EXTRACT] 样式提取失败（不影响上传）: {style_err}")

            logger.info(f"[OK] 模板上传成功: ID={template_id}, 标题={title}")
            return template
                
        except ValueError as e:
            logger.error(f"文件验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"上传模板失败: {type(e).__name__}: {e}")
            raise
        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
    
    @staticmethod
    async def save_courseware_as_template(
        user_id: str,
        courseware_id: str,
        title: str,
        description: str,
        category: str,
        visibility: str = 'private'
    ) -> Dict[str, Any]:
        """
        将生成的课件保存为模板（优化版）
        """
        try:
            supabase = get_supabase_with_retry()
            
            courseware_response = supabase.table('coursewares').select('*').eq('id', courseware_id).execute()
            
            if not courseware_response.data:
                raise ValueError(f"课件不存在: {courseware_id}")
            
            courseware = courseware_response.data[0]
            
            logger.info(f"用户 {user_id} 保存课件为模板: {courseware_id}")
            
            template_data = {
                'page_count': len(courseware.get('slides', [])),
                'lesson_plan': courseware.get('lesson_plan'),
                'interaction': courseware.get('interaction'),
            }
            
            insert_data = {
                'user_id': user_id,
                'title': title,
                'description': description,
                'category': category if category else '未分类',
                'source_type': 'saved_courseware',
                'visibility': visibility,
                'template_data': template_data,
                'slides_structure': None,
                'theme_colors': {
                    'primary': '#2F5233',
                    'secondary': '#FFFFFF',
                    'accent1': '#4CAF50',
                },
                'fonts': {
                    'default_font': 'SimHei',
                    'common_fonts': ['SimHei', 'Arial', 'Calibri'],
                    'font_sizes': [18, 24, 32, 44],
                },
                'placeholders': None,
                'original_file_name': f"{courseware.get('title', 'unnamed')}.pptx",
                'usage_count': 0,
            }
            
            response = supabase.table('user_templates').insert(insert_data).execute()
            
            if response.data:
                template = response.data[0]
                logger.info(f"[OK] 课件保存为模板成功: ID={template['id']}, 标题={title}")
                return template
            else:
                raise Exception("插入数据库失败")
            
        except Exception as e:
            logger.error(f"保存课件为模板失败: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    async def get_user_templates(
        user_id: str,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取用户的个人模板列表
        """
        try:
            supabase = get_supabase_with_retry()
            
            query = supabase.table('user_templates').select('id, title, description, category, visibility, original_file_name, original_file_size, usage_count, created_at, updated_at').eq('user_id', user_id).eq('visibility', 'private')
            
            if category:
                query = query.eq('category', category)
            
            query = query.order('created_at', desc=True).range(skip, skip + limit - 1)
            response = query.execute()
            
            logger.info(f"[OK] 获取用户模板: user_id={user_id}, 数量={len(response.data)}")
            return response.data or []
            
        except Exception as e:
            logger.error(f"获取用户模板失败: {type(e).__name__}: {e}")
            return []
    
    @staticmethod
    async def get_public_templates(
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取所有公共模板
        """
        try:
            supabase = get_supabase_with_retry()
            
            query = supabase.table('user_templates').select('id, title, description, category, visibility, original_file_name, original_file_size, usage_count, created_at, updated_at').eq('visibility', 'public')
            
            if category:
                query = query.eq('category', category)
            
            query = query.order('usage_count', desc=True).range(skip, skip + limit - 1)
            response = query.execute()
            
            logger.info(f"[OK] 获取公共模板: 数量={len(response.data)}")
            return response.data or []
            
        except Exception as e:
            logger.error(f"获取公共模板失败: {type(e).__name__}: {e}")
            return []
    
    @staticmethod
    async def get_template_by_id(template_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取模板详情
        """
        try:
            supabase = get_supabase_with_retry()
            
            response = supabase.table('user_templates').select('*').eq('id', template_id).execute()
            
            if response.data:
                logger.info(f"[OK] 获取模板详情: ID={template_id}")
                return response.data[0]
            else:
                logger.warning(f"模板不存在: ID={template_id}")
                return None
            
        except Exception as e:
            logger.error(f"获取模板详情失败: {type(e).__name__}: {e}")
            return None
    
    @staticmethod
    async def copy_template(
        source_template_id: str,
        user_id: str,
        new_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        复制公共模板到用户的个人库
        """
        try:
            supabase = get_supabase_with_retry()
            
            source = await TemplateService.get_template_by_id(source_template_id)
            if not source:
                raise ValueError(f"源模板不存在: {source_template_id}")
            
            copy_data = {
                'user_id': user_id,
                'title': new_title or f"{source['title']} (副本)",
                'description': source.get('description', ''),
                'category': source.get('category', ''),
                'source_type': source.get('source_type', 'upload'),
                'visibility': 'private',
                'template_data': source.get('template_data'),
                'slides_structure': None,
                'theme_colors': source.get('theme_colors'),
                'fonts': source.get('fonts'),
                'placeholders': source.get('placeholders'),
                'thumbnail_url': None,
                'original_file_name': source.get('original_file_name'),
                'usage_count': 0,
            }
            
            response = supabase.table('user_templates').insert(copy_data).execute()
            
            if response.data:
                template = response.data[0]
                logger.info(f"[OK] 模板复制成功: {source_template_id} -> {template['id']}")
                return template
            else:
                raise Exception("复制失败")
            
        except Exception as e:
            logger.error(f"复制模板失败: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    async def delete_template(user_id: str, template_id: str) -> bool:
        """
        删除模板（同时删除 Storage 中的文件）
        """
        try:
            supabase = get_supabase_with_retry()
            
            template = await TemplateService.get_template_by_id(template_id)
            if not template or template['user_id'] != user_id:
                raise ValueError("没有权限删除此模板")
            
            if template.get('file_path'):
                delete_file(template['file_path'], bucket=TEMPLATE_BUCKET)
                logger.info(f"[OK] 已删除 Storage 文件: {template['file_path']}")
            
            if template.get('thumbnail_path'):
                delete_file(template['thumbnail_path'], bucket=TEMPLATE_BUCKET)
                logger.info(f"[OK] 已删除预览图: {template['thumbnail_path']}")
            
            supabase.table('user_templates').delete().eq('id', template_id).execute()
            
            logger.info(f"[OK] 模板删除成功: ID={template_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除模板失败: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    async def get_template_download_url(
        template_id: str,
        user_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取模板文件的下载链接
        
        Args:
            template_id: 模板ID
            user_id: 用户ID（用于权限检查）
        
        Returns:
            {"download_url": "xxx", "file_name": "xxx"} 或 None
        """
        try:
            template = await TemplateService.get_template_by_id(template_id)
            if not template:
                return None
            
            if not template.get('has_original_file') or not template.get('file_path'):
                return None
            
            is_public = template.get('visibility') == 'public'
            is_owner = user_id and template.get('user_id') == user_id
            
            if not is_public and not is_owner:
                return None
            
            if is_public:
                download_url = get_file_public_url(template['file_path'], bucket=TEMPLATE_BUCKET)
            else:
                download_url = get_file_signed_url(template['file_path'], bucket=TEMPLATE_BUCKET)
            
            if not download_url:
                return None
            
            return {
                "download_url": download_url,
                "file_name": template.get('original_file_name'),
                "expires_in": 3600 if not is_public else None
            }
            
        except Exception as e:
            logger.error(f"获取模板下载链接失败: {type(e).__name__}: {e}")
            return None
    
    @staticmethod
    async def add_favorite(user_id: str, template_id: str) -> bool:
        """
        添加模板到收藏
        """
        try:
            supabase = get_supabase_with_retry()
            
            response = supabase.table('template_favorites').insert({
                'user_id': user_id,
                'template_id': template_id,
            }).execute()
            
            logger.info(f"[OK] 添加收藏: user_id={user_id}, template_id={template_id}")
            return True
            
        except Exception as e:
            logger.warning(f"添加收藏失败: {type(e).__name__}: {e}")
            return False
    
    @staticmethod
    async def remove_favorite(user_id: str, template_id: str) -> bool:
        """
        从收藏移除模板
        """
        try:
            supabase = get_supabase_with_retry()
            
            supabase.table('template_favorites').delete().eq('user_id', user_id).eq('template_id', template_id).execute()
            
            logger.info(f"[OK] 移除收藏: user_id={user_id}, template_id={template_id}")
            return True
            
        except Exception as e:
            logger.warning(f"移除收藏失败: {type(e).__name__}: {e}")
            return False
    
    @staticmethod
    async def get_favorites(user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的收藏模板
        """
        try:
            supabase = get_supabase_with_retry()
            
            favorites_response = supabase.table('template_favorites').select('template_id').eq('user_id', user_id).execute()
            
            if not favorites_response.data:
                return []
            
            template_ids = [fav['template_id'] for fav in favorites_response.data]
            
            templates_response = supabase.table('user_templates').select('id, title, description, category, visibility, original_file_name, usage_count, created_at').in_('id', template_ids).execute()
            
            logger.info(f"[OK] 获取收藏模板: user_id={user_id}, 数量={len(templates_response.data)}")
            return templates_response.data or []
            
        except Exception as e:
            logger.error(f"获取收藏模板失败: {type(e).__name__}: {e}")
            return []
    
    @staticmethod
    async def increment_usage_count(template_id: str) -> bool:
        """
        增加模板的使用次数
        """
        try:
            supabase = get_supabase_with_retry()
            
            response = supabase.table('user_templates').select('usage_count').eq('id', template_id).execute()
            
            if not response.data:
                return False
            
            current_count = response.data[0].get('usage_count', 0)
            
            supabase.table('user_templates').update({'usage_count': current_count + 1}).eq('id', template_id).execute()
            
            logger.debug(f"更新模板使用次数: {template_id} -> {current_count + 1}")
            return True
            
        except Exception as e:
            logger.warning(f"更新使用次数失败: {type(e).__name__}: {e}")
            return False
