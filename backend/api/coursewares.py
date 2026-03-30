from fastapi import APIRouter, Depends, HTTPException
from schema.chat_schema import DecomposeRequest, SlideGenerateRequest, PPTRenderRequest, DocxRenderRequest
from service.llm_service import decompose_topic, generate_single_slide
from repository.supabase_client import insert_courseware, upload_courseware_to_storage, insert_export
from core.auth import get_current_user
from service.template_service import TemplateService
from utils.ppt_template_renderer import render_ppt_with_template
from service.export_service import generate_docx_stream
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

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
        return {"tasks": tasks}
    except Exception as e:
        logger.error(f"拆解大纲失败: {e}")
        return {"tasks": [], "error": str(e)}

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

@router.post("/coursewares/render")
async def render_endpoint(request: PPTRenderRequest, user_id: str = Depends(get_current_user)):
    """
    正式生成 PPT 课件接口 — 优化后第三步
    """
    try:
        logger.info(f"开始为用户 {user_id} 渲染 PPT: {request.title}, 模板: {request.template_id}")
        
        # 1. 执行渲染生成二进制流
        pptx_io = render_ppt_with_template(request.slides, request.template_id)
        pptx_bytes = pptx_io.getvalue()
        
        # 2. 上传到 Supabase Storage
        file_name = f"{request.title}.pptx"
        upload_res = upload_courseware_to_storage(user_id, file_name, pptx_bytes)
        
        if not upload_res:
            raise HTTPException(status_code=500, detail="文件上传存储失败")
            
        file_url = upload_res.get("url")
        
        # 3. 写入数据库记录 (coursewares 表)
        # 将 Pydantic 列表转为原生列表用于 JSON 存储
        slides_raw = [s.dict() for s in request.slides]
        
        record = insert_courseware(
            user_id=user_id,
            title=request.title,
            slides=slides_raw,
            lesson_plan=request.lesson_plan,
            interaction=request.interaction,
            template_id=request.template_id,
            file_url=file_url
        )
        
        if not record:
            raise HTTPException(status_code=500, detail="记录写入数据库失败")
            
        # 4. 同时写入导出记录表 (exports)，确保前端导出界面可见
        insert_export(
            user_id=user_id,
            title=request.title,
            fmt="PPTX",
            size="自动计算",
            file_url=file_url
        )
            
        return {
            "status": "success",
            "courseware_id": record.get("id"),
            "file_url": file_url,
            "title": request.title
        }
        
    except Exception as e:
        logger.error(f"渲染并保存课件失败: {e}")
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
        upload_res = upload_courseware_to_storage(user_id, file_name, docx_bytes)
        
        if not upload_res:
            raise HTTPException(status_code=500, detail="教案上传存储失败")
            
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
