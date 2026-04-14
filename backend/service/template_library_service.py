"""
模板库智能管理服务 (Template Library Service)
===============================================

核心功能：
1. 上传模板时自动提取完整样式基因（颜色/字体/版式/布局）
2. 样式特征结构化存储到 Supabase 数据库
3. 提供模板列表查询、样式调用接口
4. 支持模板的 CRUD 操作和样式预览

架构设计：
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  SmartStyle      │────▶│  TemplateLibrarySvc  │────▶│  Supabase DB │
│  Extractor       │     │  (业务逻辑层)         │     │              │
└─────────────────┘     └──────────────────────┘     └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   Storage    │
                        │  (文件存储)   │
                        └──────────────┘

使用方法：
    from service.template_library_service import TemplateLibraryService
    
    svc = TemplateLibraryService()
    
    # 上传并提取样式
    result = svc.upload_and_extract(file_bytes, user_id, title)
    
    # 获取模板列表（含样式摘要）
    templates = svc.get_template_list(user_id, page=1)
    
    # 获取完整样式（供 PPT 生成模块使用）
    style = svc.get_template_style(template_id)
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """上传结果"""
    success: bool
    template_id: str
    title: str
    message: str
    style_extracted: bool = False
    style_summary: Optional[Dict[str, Any]] = None


@dataclass 
class TemplateListItem:
    """模板列表项"""
    id: str
    title: str
    created_at: str
    usage_count: int
    file_size: int
    
    # 样式摘要（轻量级，用于列表展示）
    primary_color: str = ""
    title_font: str = ""
    body_font: str = ""
    layout_count: int = 0
    aspect_ratio: str = "16:9"
    has_style: bool = False


@dataclass
class TemplateStyleDetail:
    """完整样式详情（供 PPT 生成使用）— v3.0 全量"""
    template_id: str
    colors: Dict[str, str]
    fonts: Dict[str, str]
    effects: Dict[str, Any]
    layouts: List[Dict[str, Any]]
    master: Dict[str, Any]
    shape_defaults: Dict[str, Any]
    chart_rules: Dict[str, Any]
    title_levels: List[Dict[str, Any]]
    raw_json: Optional[Dict[str, Any]] = None
    
    @property
    def primary_color(self) -> str:
        return self.colors.get('accent1') or self.colors.get('dark1') or '#333333'
    
    @property
    def title_font(self) -> str:
        return self.fonts.get('major_east_asian') or self.fonts.get('major_latin') or '微软雅黑'
    
    @property
    def body_font(self) -> str:
        return self.fonts.get('minor_east_asian') or self.fonts.get('minor_latin') or '微软雅黑'
    
    @property
    def has_full_style(self) -> str:
        return bool(self.effects or self.shape_defaults or self.chart_rules)
    
    def to_dict(self) -> Dict[str, Any]:
        d = {
            'template_id': self.template_id,
            'colors': self.colors,
            'fonts': self.fonts,
            'effects': self.effects,
            'master': self.master,
            'layouts': self.layouts,
            'shape_defaults': self.shape_defaults,
            'chart_rules': self.chart_rules,
            'title_levels': self.title_levels,
        }
        if self.raw_json:
            d['raw'] = self.raw_json
        return d
    
    def get_layout_by_type(self, layout_type: str) -> Optional[Dict[str, Any]]:
        for l in self.layouts:
            if l.get('layout_type') == layout_type:
                return l
        return None
    
    def get_title_level(self, level: str = 'h1') -> Optional[Dict[str, Any]]:
        for t in self.title_levels:
            if t.get('level') == level:
                return t
        return None


class TemplateLibraryService:
    """
    模板库智能管理服务
    
    整合样式提取、存储、查询的统一入口。
    """
    
    def __init__(self):
        self._style_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl: int = 3600  # 缓存1小时
        self._cache_timestamps: Dict[str, float] = {}
    
    def upload_and_extract(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        title: str = "",
        visibility: str = "private"
    ) -> UploadResult:
        """
        上传模板并自动提取样式
        
        完整流程：
        1. 保存原始文件到临时位置
        2. 使用 SmartStyleExtractor 提取样式基因
        3. 上传文件到 Storage
        4. 存储元数据和样式到数据库
        5. 清理临时文件
        
        Args:
            file_content: 文件字节内容
            filename: 原始文件名
            user_id: 用户ID
            title: 模板标题
            visibility: 可见性 private/public
            
        Returns:
            UploadResult 上传结果
        """
        from repository.supabase_client import get_supabase_client
        from utils.smart_style_extractor import SmartStyleExtractor
        from service.storage_service import upload_template_file
        
        template_id = str(uuid.uuid4())
        
        temp_path = self._save_temp_file(file_content, template_id, filename)
        
        try:
            logger.info(f"[TemplateLib] 开始提取样式: {filename}")
            
            extractor = SmartStyleExtractor()
            style_profile = extractor.extract(
                file_path=temp_path,
                template_id=template_id,
                template_name=title or filename
            )
            
            style_dict = style_profile.to_dict()
            
            style_summary = {
                'primary_color': style_profile.primary_color,
                'title_font': style_profile.title_font,
                'body_font': style_profile.body_font,
                'layout_count': style_profile.layout_count,
                'aspect_ratio': style_profile.master.aspect_ratio,
                'has_style': bool(style_profile.colors.get('accent1')),
            }
            
            logger.info(f"[TemplateLib] 样式提取成功: {json.dumps(style_summary, ensure_ascii=False)}")
            
            storage_info = self._upload_to_storage(
                file_content=file_content,
                filename=filename,
                user_id=user_id,
                template_id=template_id
            )
            
            db_record = self._build_db_record(
                template_id=template_id,
                user_id=user_id,
                title=title or filename.replace('.pptx', ''),
                filename=filename,
                visibility=visibility,
                style_data=style_dict,
                storage_info=storage_info,
                file_size=len(file_content)
            )
            
            supabase = get_supabase_client()
            
            result = supabase.table('user_templates').insert(db_record).execute()
            
            if not result.data:
                raise Exception("数据库写入失败")
            
            self._style_cache[template_id] = style_dict
            
            return UploadResult(
                success=True,
                template_id=template_id,
                title=db_record['title'],
                message=f"模板上传成功，已提取 {style_summary['layout_count']} 个版式",
                style_extracted=True,
                style_summary=style_summary,
            )
            
        except Exception as e:
            logger.error(f"[TemplateLib] 处理失败: {e}", exc_info=True)
            
            try:
                supabase = get_supabase_client()
                
                fallback_record = {
                    'id': template_id,
                    'user_id': user_id,
                    'title': title or filename.replace('.pptx', ''),
                    'filename': filename,
                    'visibility': visibility,
                    'file_bucket': 'local',
                    'file_path': f'templates/{template_id}.pptx',
                    'file_size': len(file_content),
                    'style_gene': {},
                    'style_extracted': False,
                    'usage_count': 0,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                }
                
                supabase.table('user_templates').insert(fallback_record).execute()
                
                return UploadResult(
                    success=True,
                    template_id=template_id,
                    title=title or filename,
                    message="模板已保存（样式提取跳过）",
                    style_extracted=False,
                )
                
            except Exception as db_err:
                logger.error(f"[TemplateLib] 降级存储也失败: {db_err}")
                return UploadResult(
                    success=False,
                    template_id="",
                    title=title or filename,
                    message=f"上传失败: {str(e)}"
                )
                
        finally:
            self._cleanup_temp_file(temp_path)
    
    def get_template_list(
        self,
        user_id: str,
        template_type: str = "personal",
        page: int = 1,
        page_size: int = 20,
        search_query: str = ""
    ) -> Tuple[List[TemplateListItem], int]:
        """
        获取模板列表（含样式摘要）
        
        Args:
            user_id: 用户ID
            template_type: personal 或 public
            page: 页码
            page_size: 每页数量
            search_query: 搜索关键词
            
        Returns:
            (模板列表, 总数)
        """
        from repository.supabase_client import get_supabase_client, execute_with_retry
        
        supabase = get_supabase_client()
        
        def query_fn(supabase):
            base = supabase.table("user_templates").select("*", count="exact")
            
            if template_type == "personal":
                base = base.eq("user_id", user_id).eq("visibility", "private")
            else:
                base = base.eq("visibility", "public")
            
            if search_query:
                base = base.or_(f"title.ilike.%{search_query}%,filename.ilike.%{search_query}%")
            
            return (
                base
                .order("created_at", desc=True)
                .range((page - 1) * page_size, page * page_size - 1)
                .execute()
            )
        
        response = execute_with_retry(query_fn, max_retries=3)
        
        if not response or not response.data:
            return [], 0
        
        items = []
        for t in response.data:
            style_gene = t.get('style_gene') or {}
            summary = style_gene.get('_summary', {})
            
            item = TemplateListItem(
                id=t.get('id', ''),
                title=t.get('title', ''),
                created_at=t.get('created_at', ''),
                usage_count=t.get('usage_count', 0),
                file_size=t.get('file_size', 0),
                primary_color=summary.get('primary_color', style_gene.get('colors', {}).get('accent1', '')),
                title_font=summary.get('title_font', style_gene.get('fonts', {}).get('major_east_asian', '')),
                body_font=summary.get('body_font', style_gene.get('fonts', {}).get('minor_east_asian', '')),
                layout_count=summary.get('layout_count', len(style_gene.get('layouts', []))),
                aspect_ratio=summary.get('aspect_ratio', '16:9'),
                has_style=bool(summary.get('primary_color')),
            )
            items.append(item)
        
        total = getattr(response, 'count', len(response.data))
        
        return items, total
    
    def get_template_style(self, template_id: str) -> Optional[TemplateStyleDetail]:
        """
        获取模板完整样式（供 PPT 生成模块使用）
        
        优先从缓存读取，缓存未命中则查数据库。
        
        Args:
            template_id: 模板ID
            
        Returns:
            完整样式详情，如果不存在则返回 None
        """
        cached = self._get_from_cache(template_id)
        if cached:
            return TemplateStyleDetail(
                template_id=cached.get('template_id', template_id),
                colors=cached.get('colors', {}),
                fonts=cached.get('fonts', {}),
                effects=cached.get('effects', {}),
                layouts=cached.get('layouts', []),
                master=cached.get('master', {}),
                shape_defaults=cached.get('shape_defaults', {}),
                chart_rules=cached.get('chart_rules', {}),
                title_levels=cached.get('title_levels', []),
                raw_json=cached,
            )
        
        from repository.supabase_client import get_supabase_client
        
        try:
            supabase = get_supabase_client()
            response = (
                supabase
                .table("user_templates")
                .select("id, style_gene, style_extracted")
                .eq("id", template_id)
                .execute()
            )
            
            if not response or not response.data:
                return None
            
            record = response.data[0]
            style_data = record.get('style_gene')
            
            if not style_data or not isinstance(style_data, dict):
                return None
            
            detail = TemplateStyleDetail(
                template_id=template_id,
                colors=style_data.get('colors', {}),
                fonts=style_data.get('fonts', {}),
                effects=style_data.get('effects', {}),
                layouts=style_data.get('layouts', []),
                master=style_data.get('master', {}),
                shape_defaults=style_data.get('shape_defaults', {}),
                chart_rules=style_data.get('chart_rules', {}),
                title_levels=style_data.get('title_levels', []),
                raw_json=style_data,
            )
            
            self._set_cache(template_id, style_data)
            
            return detail
            
        except Exception as e:
            logger.error(f"[TemplateLib] 获取样式失败: {e}")
            return None
    
    def get_template_style_json(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        获取模板样式的 JSON 格式（直接用于渲染引擎）
        
        Args:
            template_id: 模板ID
            
        Returns:
            样式字典或 None
        """
        detail = self.get_template_style(template_id)
        return detail.to_dict() if detail else None
    
    def delete_template(self, template_id: str, user_id: str) -> Tuple[bool, str]:
        """
        删除模板（同时清理 Storage 和数据库）
        
        Args:
            template_id: 模板ID
            user_id: 用户ID（用于权限验证）
            
        Returns:
            (是否成功, 消息)
        """
        from repository.supabase_client import get_supabase_client
        
        try:
            supabase = get_supabase_client()
            
            record_response = (
                supabase
                .table("user_templates")
                .select("*")
                .eq("id", template_id)
                .execute()
            )
            
            if not record_response or not record_response.data:
                return False, "模板不存在"
            
            record = record_response.data[0]
            
            if record.get('user_id') != user_id:
                return False, "无权删除此模板"
            
            bucket = record.get('file_bucket')
            path = record.get('file_path')
            
            if bucket and path and bucket != 'local':
                try:
                    supabase.storage.from_(bucket).remove([path])
                    logger.info(f"[TemplateLib] 已删除Storage文件: {bucket}/{path}")
                except Exception as e:
                    logger.warning(f"[TemplateLib] 删除Storage文件失败: {e}")
            
            delete_response = (
                supabase
                .table("user_templates")
                .delete()
                .eq("id", template_id)
                .execute()
            )
            
            if template_id in self._style_cache:
                del self._style_cache[template_id]
            if template_id in self._cache_timestamps:
                del self._cache_timestamps[template_id]
            
            return True, "删除成功"
            
        except Exception as e:
            logger.error(f"[TemplateLib] 删除失败: {e}")
            return False, f"删除失败: {str(e)}"
    
    def copy_template_to_user(
        self,
        template_id: str,
        target_user_id: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        复制公共模板到个人库
        
        Args:
            template_id: 原模板ID
            target_user_id: 目标用户ID
            
        Returns:
            (是否成功, 消息, 新模板ID)
        """
        from repository.supabase_client import get_supabase_client
        from service.storage_service import download_template_file
        
        try:
            supabase = get_supabase_client()
            
            source = (
                supabase
                .table("user_templates")
                .select("*")
                .eq("id", template_id)
                .execute()
            )
            
            if not source or not source.data:
                return False, "源模板不存在", None
            
            original = source.data[0]
            
            new_id = str(uuid.uuid4())
            
            new_record = {
                'id': new_id,
                'user_id': target_user_id,
                'title': f"{original.get('title', '')} (副本)",
                'filename': original.get('filename', ''),
                'visibility': 'private',
                'file_bucket': original.get('file_bucket'),
                'file_path': original.get('file_path'),
                'file_size': original.get('file_size', 0),
                'style_gene': original.get('style_gene', {}),
                'style_extracted': original.get('style_extracted', False),
                'usage_count': 0,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
            }
            
            result = supabase.table('user_templates').insert(new_record).execute()
            
            if result.data:
                return True, "复制成功", new_id
            else:
                return False, "复制失败", None
                
        except Exception as e:
            logger.error(f"[TemplateLib] 复制失败: {e}")
            return False, f"复制失败: {str(e)}", None
    
    def reextract_style(self, template_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        重新提取模板样式（用于修复之前失败的提取）
        
        Args:
            template_id: 模板ID
            
        Returns:
            (是否成功, 消息, 新样式数据)
        """
        from repository.supabase_client import get_supabase_client
        
        try:
            supabase = get_supabase_client()
            
            record_resp = (
                supabase
                .table("user_templates")
                .select("*")
                .eq("id", template_id)
                .execute()
            )
            
            if not record_resp or not record_resp.data:
                return False, "模板不存在", None
            
            record = record_resp.data[0]
            
            local_path = self._download_template_local(record)
            
            if not local_path:
                return False, "无法获取模板文件", None
            
            from utils.smart_style_extractor import SmartStyleExtractor
            
            extractor = SmartStyleExtractor()
            profile = extractor.extract(local_path, template_id, record.get('title', ''))
            style_dict = profile.to_dict()
            
            update_resp = (
                supabase
                .table("user_templates")
                .update({
                    'style_gene': style_dict,
                    'style_extracted': True,
                    'style_extracted_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat(),
                })
                .eq("id", template_id)
                .execute()
            )
            
            if template_id in self._style_cache:
                del self._style_cache[template_id]
            
            self._style_cache[template_id] = style_dict
            
            return True, "重新提取成功", style_dict
            
        except Exception as e:
            logger.error(f"[TemplateLib] 重新提取失败: {e}")
            return False, f"重新提取失败: {str(e)}", None
    
    def _save_temp_file(
        self,
        content: bytes,
        template_id: str,
        filename: str
    ) -> str:
        """保存临时文件"""
        temp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'temp'
        )
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_path = os.path.join(temp_dir, f"{template_id}.pptx")
        
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        return temp_path
    
    def _cleanup_temp_file(self, path: str):
        """清理临时文件"""
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    
    def _upload_to_storage(
        self,
        file_content: bytes,
        filename: str,
        user_id: str,
        template_id: str
    ) -> Dict[str, str]:
        """上传文件到 Storage"""
        from service.storage_service import upload_template_file
        
        try:
            info = upload_template_file(
                user_id=user_id,
                file_name=filename,
                file_data=file_content,
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            
            if info:
                return {
                    'bucket': info.get('bucket', 'coursewares'),
                    'path': info.get('path', f"templates/{user_id}/{template_id}.pptx"),
                }
        except Exception as e:
            logger.warning(f"[TemplateLib] Storage上传失败: {e}")
        
        local_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'templates'
        )
        os.makedirs(local_dir, exist_ok=True)
        
        local_path = os.path.join(local_dir, f"{template_id}.pptx")
        with open(local_path, 'wb') as f:
            f.write(file_content)
        
        return {'bucket': 'local', 'path': local_path}
    
    def _build_db_record(
        self,
        template_id: str,
        user_id: str,
        title: str,
        filename: str,
        visibility: str,
        style_data: Dict[str, Any],
        storage_info: Dict[str, str],
        file_size: int
    ) -> Dict[str, Any]:
        """构建数据库记录"""
        return {
            'id': template_id,
            'user_id': user_id,
            'title': title,
            'filename': filename,
            'source_type': 'upload',
            'template_data': {},
            'visibility': visibility,
            'file_bucket': storage_info.get('bucket', 'local'),
            'file_path': storage_info.get('path', ''),
            'file_size': file_size,
            'style_gene': style_data,
            'style_extracted': True,
            'style_extracted_at': datetime.now().isoformat(),
            'usage_count': 0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
    
    def _download_template_local(self, record: Dict[str, Any]) -> Optional[str]:
        """下载模板到本地"""
        cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'templates'
        )
        os.makedirs(cache_dir, exist_ok=True)
        
        template_id = record.get('id', '')
        local_path = os.path.join(cache_dir, f"{template_id}.pptx")
        
        if os.path.exists(local_path):
            return local_path
        
        bucket = record.get('file_bucket')
        path = record.get('file_path')
        
        if not bucket or not path or bucket == 'local':
            return local_path if os.path.exists(local_path) else None
        
        try:
            from repository.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            file_data = supabase.storage.from_(bucket).download(path)
            
            with open(local_path, 'wb') as f:
                f.write(file_data)
            
            return local_path
            
        except Exception as e:
            logger.error(f"[TemplateLib] 下载模板失败: {e}")
            return None
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """从缓存获取"""
        if key not in self._style_cache:
            return None
        
        ts = self._cache_timestamps.get(key, 0)
        import time
        if time.time() - ts > self._cache_ttl:
            del self._style_cache[key]
            if key in self._cache_timestamps:
                del self._cache_timestamps[key]
            return None
        
        return self._style_cache.get(key)
    
    def _set_cache(self, key: str, value: Dict[str, Any]):
        """设置缓存"""
        import time
        self._style_cache[key] = value
        self._cache_timestamps[key] = time.time()


# 全局单例
_service_instance: Optional[TemplateLibraryService] = None

def get_template_library_service() -> TemplateLibraryService:
    """获取服务实例（单例模式）"""
    global _service_instance
    if _service_instance is None:
        _service_instance = TemplateLibraryService()
    return _service_instance


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("模板库智能管理服务 - 测试程序")
    print("=" * 60)
    
    svc = TemplateLibraryService()
    
    if len(sys.argv) < 2:
        print("\n用法:")
        print("  python template_library_service.py <pptx文件路径> [用户ID]")
        sys.exit(1)
    
    file_path = sys.argv[1]
    test_user_id = sys.argv[2] if len(sys.argv) > 2 else "test-user-001"
    
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 - {file_path}")
        sys.exit(1)
    
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    print(f"\n正在处理: {os.path.basename(file_path)} ({len(file_content)/1024:.1f}KB)")
    
    result = svc.upload_and_extract(
        file_content=file_content,
        filename=os.path.basename(file_path),
        user_id=test_user_id,
        title=os.path.basename(file_path).replace('.pptx', '')
    )
    
    print(f"\n{'='*40}")
    print(f"结果: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"模板ID: {result.template_id}")
    print(f"标题: {result.title}")
    print(f"消息: {result.message}")
    print(f"样式提取: {'✅' if result.style_extracted else '⏭️ 跳过'}")
    
    if result.style_summary:
        print(f"\n--- 样式摘要 ---")
        print(json.dumps(result.style_summary, ensure_ascii=False, indent=2))
