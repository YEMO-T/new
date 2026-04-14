from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from typing import Optional
from schema.chat_schema import DecomposeRequest, SlideGenerateRequest, PPTRenderRequest, DocxRenderRequest, EnhancedPPTRenderRequest
from service.llm_service import decompose_topic, generate_single_slide
from repository.supabase_client import insert_courseware, insert_export, upload_ppt_to_public_bucket
from core.auth import get_current_user
from service.template_service import TemplateService
from utils.ppt_template_renderer import render_ppt_with_template
from utils.ppt_enhanced_renderer import render_enhanced_ppt
from utils.slide_renderer import SlideRenderer
from service.export_service import generate_docx_stream
import logging
import asyncio
import concurrent.futures
from datetime import datetime
import tempfile
import os
import io
import json

logger = logging.getLogger(__name__)

router = APIRouter()

PPT_RENDER_TIMEOUT = 120

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

@router.post("/coursewares/decompose")
async def decompose_endpoint(request: DecomposeRequest, user_id: str = Depends(get_current_user)):
    """
    大纲拆解接口 - 优化后第一步
    """
    try:
        tasks = await decompose_topic(
            prompt=request.prompt,
            grade=request.grade,
            subject=request.subject,
            template_id=request.template_id
        )
        if not tasks:
            return {"tasks": [], "error": "LLM返回空结果，请重试或更换主题"}
        return {"tasks": tasks}
    except Exception as e:
        err_str = str(e)
        logger.error(f"拆解大纲失败: {e}")

        if "429" in err_str or "quota" in err_str.lower() or "exceeded" in err_str.lower():
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "tasks": [],
                    "error": "AI服务配额已用尽（Token额度超限），请联系管理员充值或稍后重试",
                    "error_code": "QUOTA_EXCEEDED"
                }
            )
        elif "Timeout" in err_str or "timeout" in err_str.lower():
            return {"tasks": [], "error": "AI服务响应超时，请稍后重试", "error_code": "TIMEOUT"}
        elif "Connection" in err_str or "connection" in err_str.lower():
            return {"tasks": [], "error": "AI服务连接失败，请检查网络", "error_code": "CONNECTION_ERROR"}

        return {"tasks": [], "error": f"拆解失败: {err_str[:100]}", "error_code": "UNKNOWN"}

@router.post("/coursewares/generate/slide")
async def generate_slide_endpoint(request: SlideGenerateRequest, user_id: str = Depends(get_current_user)):
    """
    单页生成接口 - 优化后第二步
    """
    try:
        slide_content = await generate_single_slide(
            task=request.task.dict(),
            context=request.context,
            user_id=user_id,
            template_id=request.template_id
        )
        return slide_content
    except Exception as e:
        logger.error(f"生成单页内容失败: {e}")
        return {"error": str(e)}

def _render_ppt_task(slides_data: list, template_id: str):
    """
    PPT渲染任务（在线程池中执行）
    
    使用智能渲染引擎：
    1. 提取模板的完整视觉基因（颜色/字体/版式）
    2. 创建新PPT并应用样式
    3. 输出具有完整样式的PPTX
    """
    try:
        logger.info(f"[PPT渲染] 开始渲染 | 页数: {len(slides_data)} | 模板ID: {template_id}")

        if not slides_data:
            raise ValueError("幻灯片数据为空")

        for idx, slide in enumerate(slides_data):
            logger.debug(f"[PPT渲染] 第{idx + 1}页: title={slide.get('title')}, type={slide.get('page_type')}")

        from utils.intelligent_ppt_builder import IntelligentPPTBuilder

        builder = IntelligentPPTBuilder()
        result_bytes, engine_used = builder.build_with_fallback(
            slides_data=slides_data,
            template_id=template_id
        )

        logger.info(f"[PPT渲染] 渲染成功 | 引擎: {engine_used} | 文件大小: {len(result_bytes)} 字节")
        return result_bytes

    except Exception as e:
        logger.error(f"[PPT渲染] 渲染任务失败: {e}", exc_info=True)
        raise


def _render_with_ultimate_engine(slides_data: list, template_id: str) -> io.BytesIO:
    """
    使用终极渲染器渲染 PPT（推荐）
    
    核心优势：
    1. 通过 TemplateStyleCloner 深度克隆模板风格
    2. 创建全新演示文稿，100% 清除原始内容
    3. 完整继承母版、版式、颜色主题、字体方案
    4. 智能选择版式并填充内容（保持样式）
    
    与旧版 smart_layout_engine 的区别：
    - 旧版：Presentation(template_path) + add_slide() → 原始内容残留
    - 本版：StyleCloner.clone_style_to_new_presentation() → 干净的新演示文稿
    """
    from utils.ultimate_renderer import UltimateRenderer, render_ultimate_ppt
    
    # 解析模板路径
    template_path = None
    if template_id:
        template_path = _resolve_template_path_for_ultimate(template_id)
    
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_id}")
    
    # 转换数据格式
    converted_slides = []
    for slide_dict in slides_data:
        content = slide_dict.get('content', [])
        if isinstance(content, str):
            content = [content] if content.strip() else []
        elif not isinstance(content, list):
            content = []
        
        converted_slide = {
            'title': slide_dict.get('title', ''),
            'subtitle': slide_dict.get('subtitle', ''),
            'content': content,
            'page_type': slide_dict.get('page_type', 
                                     slide_dict.get('type', 'content'))
        }
        converted_slides.append(converted_slide)
    
    # 调用终极渲染器
    result_stream = render_ultimate_ppt(
        template_path=template_path,
        slides_data=converted_slides
    )
    
    # 确保返回 bytes 类型（而不是 BytesIO）
    if hasattr(result_stream, 'getvalue'):
        return result_stream.getvalue()
    return result_stream


def _resolve_template_path_for_ultimate(template_id: str) -> Optional[str]:
    """为终极渲染器解析模板路径（支持本地文件 + Supabase 云端下载）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_path = os.path.join(base_dir, 'data', 'templates', f"{template_id}.pptx")

    if os.path.exists(local_path):
        logger.info(f"[UltimateRender] 使用本地缓存: {local_path}")
        return local_path

    logger.info(f"[UltimateRender] 本地未找到，尝试从云端下载 template_id={template_id}")

    try:
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table('user_templates').select(
            'id, file_path, file_bucket'
        ).eq('id', template_id).execute()

        if not response.data or len(response.data) == 0:
            logger.warning(f"[UltimateRender] 数据库中未找到模板记录: {template_id}")
            return None

        template = response.data[0]
        file_path = template.get('file_path')
        file_bucket = template.get('file_bucket')

        if not file_path or not file_bucket:
            logger.warning(f"[UltimateRender] 模板记录缺少 file_path 或 file_bucket: {template}")
            return None

        from service.storage_service import download_template_file

        file_data = download_template_file(file_bucket, file_path)

        if not file_data:
            logger.warning(f"[UltimateRender] 从 Storage 下载失败: bucket={file_bucket}, path={file_path}")
            return None

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"[UltimateRender] 模板已下载并缓存: {local_path}")
        return local_path

    except Exception as e:
        logger.warning(f"[UltimateRender] 获取远程模板异常: {e}")
        import traceback
        logger.debug(traceback.format_exc())

    return None


def _render_with_smart_engine(slides_data: list, template_id: str) -> io.BytesIO:
    """
    使用智能排版引擎渲染 PPT
    
    核心优势：
    1. 从模板深度提取视觉样式基因
    2. 根据内容类型智能选择最佳版式
    3. 完整继承字体、颜色、间距等格式
    4. 支持自适应缩放和自动换行
    """
    from utils.smart_layout_engine import SmartStyleExtractor, generate_smart_ppt
    
    # 解析模板路径
    template_path = None
    if template_id:
        template_path = _resolve_template_path_for_smart(template_id)
    
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_id}")
    
    # 转换数据格式
    converted_slides = []
    for slide_dict in slides_data:
        content = slide_dict.get('content', [])
        if isinstance(content, str):
            content = [content] if content.strip() else []
        elif not isinstance(content, list):
            content = []
        
        converted_slide = {
            'title': slide_dict.get('title', ''),
            'subtitle': slide_dict.get('subtitle', ''),
            'content': content,
            'page_type': slide_dict.get('page_type', 
                                     slide_dict.get('type', 'content'))
        }
        converted_slides.append(converted_slide)
    
    # 调用智能排版引擎
    result = generate_smart_ppt(
        template_path=template_path,
        slides_data=converted_slides
    )
    
    return result


def _resolve_template_path_for_smart(template_id: str) -> Optional[str]:
    """为智能引擎解析模板路径（支持本地文件 + Supabase 云端下载）"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_path = os.path.join(base_dir, 'data', 'templates', f"{template_id}.pptx")

    if os.path.exists(local_path):
        logger.info(f"[SmartRender] 使用本地缓存: {local_path}")
        return local_path

    logger.info(f"[SmartRender] 本地未找到，尝试从云端下载 template_id={template_id}")

    try:
        from repository.supabase_client import get_supabase_client
        supabase = get_supabase_client()

        response = supabase.table('user_templates').select(
            'id, file_path, file_bucket'
        ).eq('id', template_id).execute()

        if not response.data or len(response.data) == 0:
            logger.warning(f"[SmartRender] 数据库中未找到模板记录: {template_id}")
            return None

        template = response.data[0]
        file_path = template.get('file_path')
        file_bucket = template.get('file_bucket')

        if not file_path or not file_bucket:
            logger.warning(f"[SmartRender] 模板记录缺少 file_path 或 file_bucket: {template}")
            return None

        from service.storage_service import download_template_file

        file_data = download_template_file(file_bucket, file_path)

        if not file_data:
            logger.warning(f"[SmartRender] 从 Storage 下载失败: bucket={file_bucket}, path={file_path}")
            return None

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(file_data)

        logger.info(f"[SmartRender] 模板已下载并缓存: {local_path}")
        return local_path

    except Exception as e:
        logger.warning(f"[SmartRender] 获取远程模板异常: {e}")
        import traceback
        logger.debug(traceback.format_exc())

    return None

@router.post("/coursewares/render")
async def render_endpoint(http_request: Request, user_id: str = Depends(get_current_user)):
    """
    正式生成 PPT 课件接口 — 优化后第三步
    
    使用增强版渲染器，支持：
    - 图片占位符
    - 表格填充
    - 图表生成
    - 模板变量替换
    
    优化：添加超时控制和异步处理，使用宽松验证模式
    """
    try:
        raw_body = await http_request.json()
        logger.info(f"[渲染API] 收到原始请求: title={raw_body.get('title')}, slides_count={len(raw_body.get('slides', []))}, template_id={raw_body.get('template_id')}")
        
        title = raw_body.get('title', '未命名课件')
        template_id = raw_body.get('template_id')
        lesson_plan = raw_body.get('lesson_plan')
        interaction = raw_body.get('interaction')
        slides_raw_input = raw_body.get('slides', [])
        
        logger.info(f"[渲染API] 开始为用户 {user_id} 渲染 PPT: {title}, 模板: {template_id}, 幻灯片数: {len(slides_raw_input)}")
        start_time = datetime.now()
        
        if not slides_raw_input or len(slides_raw_input) == 0:
            raise HTTPException(status_code=400, detail="幻灯片内容为空，无法生成PPT")
        
        slides_data = []
        for idx, slide in enumerate(slides_raw_input):
            try:
                slide_dict = dict(slide) if isinstance(slide, dict) else {}
                
                slide_dict['variables'] = slide_dict.get('variables') or {}
                slide_dict['images'] = slide_dict.get('images') or []
                slide_dict['tables'] = slide_dict.get('tables') or []
                slide_dict['charts'] = slide_dict.get('charts') or []
                
                if not slide_dict.get('title'):
                    slide_dict['title'] = f"第{idx + 1}页"
                
                if not slide_dict.get('page_type'):
                    slide_dict['page_type'] = slide_dict.get('type', 'content')
                
                content = slide_dict.get('content', [])
                if isinstance(content, str):
                    slide_dict['content'] = [content] if content.strip() else []
                elif not isinstance(content, list):
                    slide_dict['content'] = []
                
                slides_data.append(slide_dict)
            except Exception as e:
                logger.warning(f"[渲染API] 处理第{idx + 1}页数据时出错: {e}, 使用默认值")
                slides_data.append({
                    'title': f"第{idx + 1}页",
                    'content': [],
                    'page_type': 'content',
                    'variables': {},
                    'images': [],
                    'tables': [],
                    'charts': []
                })
        
        future = _executor.submit(_render_ppt_task, slides_data, template_id)
        
        try:
            pptx_bytes = future.result(timeout=PPT_RENDER_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.error(f"[渲染API] PPT渲染超时（超过 {PPT_RENDER_TIMEOUT} 秒）")
            raise HTTPException(status_code=504, detail="PPT渲染超时，请稍后重试")
        except Exception as e:
            logger.error(f"[渲染API] PPT渲染任务异常: {e}")
            raise HTTPException(status_code=500, detail=f"PPT渲染失败: {str(e)}")
        
        if not pptx_bytes:
            raise HTTPException(status_code=500, detail="PPT渲染结果为空")
        
        file_name = f"{title}.pptx"
        upload_res = upload_ppt_to_public_bucket(user_id, file_name, pptx_bytes)
        
        if not upload_res or not upload_res.get("success"):
            # 如果上传失败，尝试直接保存到本地作为最后的手段
            logger.warning(f"[渲染API] 文件上传失败，尝试保存到本地临时目录")
            try:
                import tempfile
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'temp_exports')
                os.makedirs(temp_dir, exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                local_path = os.path.join(temp_dir, f"{timestamp}_{file_name}")
                with open(local_path, 'wb') as f:
                    f.write(pptx_bytes)
                file_url = f"/local/temp_exports/{timestamp}_{file_name}"
                upload_res = {"url": file_url, "success": True, "is_local": True}
                logger.info(f"[渲染API] 文件已保存到本地: {local_path}")
            except Exception as save_err:
                raise HTTPException(status_code=500, detail=f"文件保存失败: {str(save_err)}")
            
        file_url = upload_res.get("url")
        
        if not file_url:
            raise HTTPException(status_code=500, detail="文件已上传但无法获取下载链接")
        
        record = insert_courseware(
            user_id=user_id,
            title=title,
            slides=slides_data,
            lesson_plan=lesson_plan,
            interaction=interaction,
            template_id=template_id,
            file_url=file_url
        )
        
        if not record:
            logger.warning(f"[渲染API] 记录写入数据库失败，但文件已上传: {file_url}")
            
        insert_export(
            user_id=user_id,
            title=title,
            fmt="PPTX",
            size=f"{len(pptx_bytes) / 1024:.1f}KB",
            file_url=file_url
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[渲染API] PPT渲染完成，耗时: {elapsed:.2f}秒, 文件大小: {len(pptx_bytes)}字节")
            
        return {
            "status": "success",
            "courseware_id": record.get("id") if record else None,
            "file_url": file_url,
            "title": title
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[渲染API] JSON解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"请求体格式错误: 请发送有效的JSON数据")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"渲染并保存课件失败: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"渲染失败: {str(e)}")

@router.post("/coursewares/render/docx")
async def render_docx_endpoint(request: DocxRenderRequest, user_id: str = Depends(get_current_user)):
    """
    教案 DOCX 渲染并存储接口
    """
    try:
        logger.info(f"开始为用户 {user_id} 渲染教案: {request.title}")
        
        # 1. 生成 DOCX 二进制流
        docx_io = generate_docx_stream(request.lesson_plan)
        docx_bytes = docx_io.getvalue()
        
        # 2. 上传到 Supabase Storage
        file_name = f"{request.title}.docx"
        upload_res = upload_ppt_to_public_bucket(user_id, file_name, docx_bytes)
        
        if not upload_res or not upload_res.get("success"):
            raise HTTPException(status_code=500, detail="教案上传到Supabase存储失败")
            
        file_url = upload_res.get("url")
        
        # 3. 写入导出记录表 (exports)
        insert_export(
            user_id=user_id,
            title=request.title,
            fmt="DOCX",
            size="自动计算",
            file_url=file_url
        )
            
        return {
            "status": "success",
            "file_url": file_url,
            "title": request.title
        }
        
    except Exception as e:
        logger.error(f"渲染并保存教案失败: {e}")
        raise HTTPException(status_code=500, detail=f"渲染教案失败: {str(e)}")


@router.post("/coursewares/preview")
async def preview_rendered_ppt(http_request: Request, user_id: str = Depends(get_current_user)):
    """
    预览渲染后的 PPT 幻灯片
    
    渲染 PPT 并返回幻灯片图片列表（base64格式），用于前端实时预览
    使用宽松验证模式，兼容前端各种数据格式
    """
    temp_file_path = None
    try:
        raw_body = await http_request.json()
        logger.info(f"[预览API] 收到原始请求: title={raw_body.get('title')}, slides_count={len(raw_body.get('slides', []))}, template_id={raw_body.get('template_id')}")
        
        title = raw_body.get('title', '未命名课件')
        template_id = raw_body.get('template_id')
        slides_raw = raw_body.get('slides', [])
        
        if not slides_raw or len(slides_raw) == 0:
            raise HTTPException(status_code=400, detail="幻灯片内容为空")
        
        logger.info(f"[预览API] 开始为用户 {user_id} 预览渲染 PPT: {title}, 幻灯片数: {len(slides_raw)}, 模板ID: {template_id}")
        start_time = datetime.now()
        
        slides_data = []
        for idx, slide in enumerate(slides_raw):
            try:
                slide_dict = dict(slide) if isinstance(slide, dict) else {}
                slide_dict['variables'] = slide_dict.get('variables') or {}
                slide_dict['images'] = slide_dict.get('images') or []
                slide_dict['tables'] = slide_dict.get('tables') or []
                slide_dict['charts'] = slide_dict.get('charts') or []
                
                if not slide_dict.get('title'):
                    slide_dict['title'] = f"第{idx + 1}页"
                
                if not slide_dict.get('page_type'):
                    slide_dict['page_type'] = slide_dict.get('type', 'content')
                
                content = slide_dict.get('content', [])
                if isinstance(content, str):
                    slide_dict['content'] = [content] if content.strip() else []
                elif not isinstance(content, list):
                    slide_dict['content'] = []
                
                slides_data.append(slide_dict)
                logger.debug(f"[预览API] 第{idx + 1}页处理成功: title={slide_dict['title']}, type={slide_dict['page_type']}")
            except Exception as e:
                logger.warning(f"[预览API] 处理第{idx + 1}页数据时出错: {e}, 原始数据: {str(slide)[:200]}")
                slides_data.append({
                    'title': f"第{idx + 1}页",
                    'content': [],
                    'page_type': 'content',
                    'variables': {},
                    'images': [],
                    'tables': [],
                    'charts': []
                })
        
        future = _executor.submit(_render_ppt_task, slides_data, template_id)
        
        try:
            pptx_bytes = future.result(timeout=PPT_RENDER_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise HTTPException(status_code=504, detail="PPT渲染超时")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PPT渲染失败: {str(e)}")
        
        if not pptx_bytes:
            raise HTTPException(status_code=500, detail="PPT渲染结果为空")
        
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as temp_file:
            temp_file.write(pptx_bytes)
            temp_file_path = temp_file.name
        
        logger.info(f"[预览API] 临时文件已创建: {temp_file_path}")
        
        try:
            slides_preview = SlideRenderer.render_pptx_to_images(temp_file_path)
            logger.info(f"[预览API] 幻灯片渲染完成: {len(slides_preview)} 页")
            
            expected_count = len(slides_data)
            if len(slides_preview) > expected_count:
                logger.info(f"[预览API] 过滤多余幻灯片: {len(slides_preview)} -> {expected_count}")
                slides_preview = slides_preview[:expected_count]
        except Exception as render_err:
            logger.error(f"[预览API] 幻灯片渲染失败: {render_err}")
            slides_preview = []
            for idx, slide_data in enumerate(slides_data):
                slides_preview.append({
                    'slide_num': idx + 1,
                    'title': slide_data.get('title', f'第 {idx + 1} 页'),
                    'content_preview': '\n'.join(slide_data.get('content', []))[:200],
                    'image': None
                })
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[预览API] 预览渲染完成，耗时: {elapsed:.2f}秒")
        
        return {
            "status": "success",
            "title": title,
            "total_slides": len(slides_preview),
            "slides": slides_preview,
            "render_time": elapsed
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[预览API] JSON解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"请求体格式错误: 请发送有效的JSON数据")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[预览API] 预览渲染失败: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"预览渲染失败: {str(e)}")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"[预览API] 临时文件已删除: {temp_file_path}")
            except Exception as e:
                logger.warning(f"[预览API] 删除临时文件失败: {e}")


@router.post("/coursewares/render-with-style")
async def render_with_template_style_endpoint(
    http_request: Request, 
    user_id: str = Depends(get_current_user)
):
    """
    基于模板样式生成 PPT - 新端点
    
    功能：
    1. 根据用户选择的模板ID加载对应样式
    2. 使用 TemplateStyleCloner 完整克隆模板风格
    3. 填充用户提供的内容
    4. 返回风格完全一致的 PPT
    
    特点：
    - 只改变内容，不改变任何视觉风格
    - 自动继承母版、版式、颜色主题、字体规则
    - 智能选择最佳版式匹配内容类型
    
    Request Body:
    {
        "template_id": "uuid-xxx",          // 必填：选择的模板ID
        "title": "我的演示文稿",              // 必填：PPT标题
        "slides": [                          // 幻灯片列表
            {
                "title": "封面标题",
                "subtitle": "副标题",
                "page_type": "cover",         // cover/toc/content/summary/ending 等
                "content": []
            },
            {
                "title": "第一章",
                "content": ["要点1", "要点2"],
                "page_type": "content"
            }
        ]
    }
    """
    temp_file_path = None
    try:
        raw_body = await http_request.json()
        
        template_id = raw_body.get('template_id')
        title = raw_body.get('title', '未命名课件')
        slides_data = raw_body.get('slides', [])
        
        if not template_id:
            raise HTTPException(status_code=400, detail="缺少必要参数: template_id")
        
        if not slides_data or len(slides_data) == 0:
            raise HTTPException(status_code=400, detail="幻灯片内容为空")
        
        logger.info(f"[StyleRender] 用户 {user_id} 请求基于模板生成:")
        logger.info(f"[StyleRender]   模板ID: {template_id}")
        logger.info(f"[StyleRender]   标题: {title}")
        logger.info(f"[StyleRender]   幻灯片数: {len(slides_data)}")
        start_time = datetime.now()
        
        # 调用样式生成服务
        from service.template_style_service import generate_ppt_with_template_style
        
        pptx_bytes = generate_ppt_with_template_style(
            template_id=template_id,
            slides_content=slides_data
        )
        
        pptx_data = pptx_bytes.getvalue()
        
        if not pptx_data or len(pptx_data) == 0:
            raise HTTPException(status_code=500, detail="PPT生成结果为空")
        
        # 保存到 Storage
        file_name = f"{title}.pptx"
        upload_res = upload_ppt_to_public_bucket(user_id, file_name, pptx_data)
        
        if upload_res and upload_res.get("success"):
            file_url = upload_res.get("url")
            
            record = insert_courseware(
                user_id=user_id,
                title=title,
                slides=slides_data,
                lesson_plan=None,
                interaction=None,
                template_id=template_id,
                file_url=file_url
            )
            
            insert_export(
                user_id=user_id,
                title=title,
                fmt="PPTX",
                size=f"{len(pptx_data) / 1024:.1f}KB",
                file_url=file_url
            )
        else:
            raise HTTPException(status_code=500, detail="PPT上传到Supabase存储失败，请检查存储配置")
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"[StyleRender] 样式化PPT生成完成:")
        logger.info(f"   耗时: {elapsed:.2f}秒")
        logger.info(f"   大小: {len(pptx_data) / 1024:.1f}KB")
        logger.info(f"   URL: {file_url or 'N/A'}")
        
        return {
            "status": "success",
            "message": "基于模板样式的PPT已成功生成",
            "courseware_id": record.get("id") if 'record' in dir() and record else None,
            "file_url": file_url,
            "title": title,
            "template_used": template_id,
            "render_method": "template_style_cloning",
            "file_size_kb": round(len(pptx_data) / 1024, 1),
            "slide_count": len(slides_data),
            "render_time": elapsed
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[StyleRender] JSON解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"请求体格式错误: 请发送有效的JSON数据")
    
    except HTTPException:
        raise
    
    except ValueError as e:
        logger.error(f"[StyleRender] 参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"[StyleRender] 生成失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"基于模板样式生成失败: {str(e)}")


@router.get("/coursewares/template/{template_id}/style-info")
async def get_template_style_info(template_id: str, user_id: str = Depends(get_current_user)):
    """
    获取模板的样式基因信息（用于前端展示）
    
    Returns:
        模板的完整样式信息，包括：
        - 颜色方案（主色调、强调色等）
        - 字体设置（中文字体、西文字体）
        - 版式列表（可用布局及其占位符）
        - 提取状态和时间
    """
    try:
        from service.template_style_service import load_template_style_from_db
        
        style_gene = load_template_style_from_db(template_id)
        
        if not style_gene:
            # 尝试实时提取
            local_template_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data', 'templates'
            )
            local_path = os.path.join(local_template_dir, f"{template_id}.pptx")
            
            if os.path.exists(local_path):
                from service.template_style_service import TemplateStyleExtractor
                extractor = TemplateStyleExtractor()
                style_gene = extractor.extract_from_file(local_path, template_id)
                
                # 保存到数据库
                from service.template_style_service import extract_and_save_template_style
                extract_and_save_template_style(local_path, template_id)
            else:
                return {
                    "status": "error",
                    "message": "模板不存在或无法访问",
                    "style_extracted": False
                }
        
        return {
            "status": "success",
            "template_id": template_id,
            "style_extracted": True,
            "extracted_at": style_gene.extracted_at,
            "style_info": {
                "theme": style_gene.theme,
                "total_layouts": style_gene.total_layouts,
                "total_placeholders": style_gene.total_placeholders,
                "layouts": style_gene.layouts
            },
            "preview_colors": {
                "primary": style_gene.theme.get('colors', {}).get('accent1'),
                "secondary": style_gene.theme.get('colors', {}).get('accent2'),
                "background": style_gene.theme.get('colors', {}).get('light1'),
                "text": style_gene.theme.get('colors', {}).get('dark1')
            } if style_gene.theme else {},
            "fonts": style_gene.theme.get('fonts', {}) if style_gene.theme else {}
        }
        
    except Exception as e:
        logger.error(f"[StyleInfo] 获取样式信息失败: {e}")
        return {
            "status": "error",
            "message": f"获取样式信息失败: {str(e)}",
            "style_extracted": False
        }


@router.post("/coursewares/preview-with-style")
async def preview_with_template_style(
    http_request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    预览基于模板样式的PPT（不保存，仅用于前端实时预览）
    
    与 /coursewares/render-with-style 类似，但：
    - 不保存到数据库
    - 不上传到 Storage
    - 返回幻灯片预览图片列表
    - 用于用户确认效果后再正式生成
    """
    temp_file_path = None
    try:
        raw_body = await http_request.json()
        
        template_id = raw_body.get('template_id')
        title = raw_body.get('title', '预览课件')
        slides_data = raw_body.get('slides', [])
        
        if not template_id:
            raise HTTPException(status_code=400, detail="缺少必要参数: template_id")
        
        if not slides_data or len(slides_data) == 0:
            raise HTTPException(status_code=400, detail="幻灯片内容为空")
        
        logger.info(f"[StylePreview] 预览请求: template={template_id}, slides={len(slides_data)}")
        start_time = datetime.now()
        
        # 生成 PPTX
        from service.template_style_service import generate_ppt_with_template_style
        
        pptx_io = generate_ppt_with_template_style(
            template_id=template_id,
            slides_content=slides_data
        )
        
        pptx_bytes = pptx_io.getvalue()
        
        # 保存为临时文件用于渲染预览图
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as temp_file:
            temp_file.write(pptx_bytes)
            temp_file_path = temp_file.name
        
        # 渲染幻灯片预览图
        slides_preview = SlideRenderer.render_pptx_to_images(temp_file_path)
        
        expected_count = len(slides_data)
        if len(slides_preview) > expected_count:
            slides_preview = slides_preview[:expected_count]
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info(f"[StylePreview] 预览完成: {len(slides_preview)}页, {elapsed:.2f}秒")
        
        return {
            "status": "success",
            "title": title,
            "template_id": template_id,
            "total_slides": len(slides_preview),
            "slides": slides_preview,
            "render_time": elapsed,
            "preview_note": "此预览使用模板的完整视觉风格生成"
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"[StylePreview] JSON解析失败: {e}")
        raise HTTPException(status_code=400, detail="请求体格式错误")
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"[StylePreview] 预览失败: {type(e).__name__}: {e}")
        
        # 降级：返回文本预览
        fallback_slides = []
        for idx, slide in enumerate(slides_data):
            fallback_slides.append({
                'slide_num': idx + 1,
                'title': slide.get('title', f'第{idx+1}页'),
                'content_preview': '\n'.join(slide.get('content', []))[:200],
                'image': None
            })
        
        return {
            "status": "partial_success",
            "title": title,
            "total_slides": len(fallback_slides),
            "slides": fallback_slides,
            "warning": f"图片渲染失败: {str(e)}，已降级为文本预览"
        }
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass
