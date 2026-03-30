"""
PPT模板管理服务 - 处理模板上传、保存、应用等业务逻辑
"""

import logging
import tempfile
import os
import shutil
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from fastapi import UploadFile

from repository.supabase_client import get_supabase_client
from service.ppt_parser import extract_template_from_pptx

logger = logging.getLogger(__name__)


class TemplateService:
    """PPT模板管理服务"""
    
    @staticmethod
    async def upload_template(
        user_id: str,
        file: UploadFile,
        title: str,
        description: str,
        category: str,
        visibility: str = 'private'
    ) -> Dict[str, Any]:
        """
        上传PPT文件作为模板
        """
        temp_file_path = None
        try:
            if not file.filename.lower().endswith('.pptx'):
                raise ValueError("只支持 .pptx 格式的PPT文件")
            
            temp_file_path = tempfile.mktemp(suffix='.pptx')
            contents = await file.read()
            
            with open(temp_file_path, 'wb') as f:
                f.write(contents)
            
            file_size = os.path.getsize(temp_file_path)
            
            logger.info(f"用户 {user_id} 上传PPT: {file.filename} ({file_size} 字节)")
            
            template_data = extract_template_from_pptx(temp_file_path)
            
            supabase = get_supabase_client()
            
            insert_data = {
                'user_id': user_id,
                'title': title,
                'description': description,
                'category': category if category else '未分类',
                'source_type': 'upload',
                'visibility': visibility,
                'template_data': template_data,
                'slides_structure': template_data.get('slides_structure'),
                'theme_colors': template_data.get('theme_colors'),
                'fonts': template_data.get('fonts'),
                'placeholders': template_data.get('placeholders'),
                'thumbnail_url': template_data.get('thumbnail'),
                'original_file_name': file.filename,
                'original_file_size': f"{file_size / 1024:.2f} KB",
                'usage_count': 0,
            }
            
            response = supabase.table('user_templates').insert(insert_data).execute()
            
            if response.data:
                template = response.data[0]
                template_id = template['id']
                
                try:
                    target_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'templates')
                    os.makedirs(target_dir, exist_ok=True)
                    target_path = os.path.join(target_dir, f"{template_id}.pptx")
                    shutil.copy2(temp_file_path, target_path)
                    logger.info(f"[OK] 模板已保存至本地: {target_path}")
                except Exception as e:
                    logger.error(f"保存模板到本地失败: {e}")

                logger.info(f"[OK] 模板上传成功: ID={template_id}, 标题={title}")
                return template
            else:
                raise Exception("插入数据库失败")
                
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
        将生成的课件保存为模板
        """
        try:
            supabase = get_supabase_client()
            
            courseware_response = supabase.table('coursewares').select('*').eq('id', courseware_id).execute()
            
            if not courseware_response.data:
                raise ValueError(f"课件不存在: {courseware_id}")
            
            courseware = courseware_response.data[0]
            
            logger.info(f"用户 {user_id} 保存课件为模板: {courseware_id}")
            
            template_data = {
                'slides_structure': courseware.get('slides', []),
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
                'placeholders': {
                    'title': True,
                    'content': True,
                    'subtitle': False,
                    'example_content': [],
                },
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
                'slides_structure': template_data.get('slides_structure'),
                'theme_colors': template_data.get('theme_colors'),
                'fonts': template_data.get('fonts'),
                'placeholders': template_data.get('placeholders'),
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
            supabase = get_supabase_client()
            
            query = supabase.table('user_templates').select('*').eq('user_id', user_id).eq('visibility', 'private')
            
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
            supabase = get_supabase_client()
            
            query = supabase.table('user_templates').select('*').eq('visibility', 'public')
            
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
            supabase = get_supabase_client()
            
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
            supabase = get_supabase_client()
            
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
                'slides_structure': source.get('slides_structure'),
                'theme_colors': source.get('theme_colors'),
                'fonts': source.get('fonts'),
                'placeholders': source.get('placeholders'),
                'thumbnail_url': source.get('thumbnail_url'),
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
        删除模板
        """
        try:
            supabase = get_supabase_client()
            
            template = await TemplateService.get_template_by_id(template_id)
            if not template or template['user_id'] != user_id:
                raise ValueError("没有权限删除此模板")
            
            supabase.table('user_templates').delete().eq('id', template_id).execute()
            
            logger.info(f"[OK] 模板删除成功: ID={template_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除模板失败: {type(e).__name__}: {e}")
            raise
    
    @staticmethod
    async def add_favorite(user_id: str, template_id: str) -> bool:
        """
        添加模板到收藏
        """
        try:
            supabase = get_supabase_client()
            
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
            supabase = get_supabase_client()
            
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
            supabase = get_supabase_client()
            
            favorites_response = supabase.table('template_favorites').select('*').eq('user_id', user_id).execute()
            
            if not favorites_response.data:
                return []
            
            template_ids = [fav['template_id'] for fav in favorites_response.data]
            
            templates_response = supabase.table('user_templates').select('*').in_('id', template_ids).execute()
            
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
            supabase = get_supabase_client()
            
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
