from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from schema.extra_schema import ExportCreate, PPTExportRequest, DocxExportRequest
from repository.supabase_client import get_exports, insert_export, delete_export
from service.export_service import generate_pptx_stream, generate_docx_stream
from core.auth import get_current_user

router = APIRouter()

@router.get("/exports")
async def list_exports(user_id: str = Depends(get_current_user)):
    return get_exports(user_id)

@router.post("/exports")
async def create_export(request: ExportCreate, user_id: str = Depends(get_current_user)):
    res = insert_export(user_id, request.title, request.format, request.size, request.file_url)
    return {"status": "success", "data": res}

@router.post("/exports/download/pptx")
async def download_pptx(request: PPTExportRequest, user_id: str = Depends(get_current_user)):
    """
    生成并下载 PPTX 文件（支持模板母版）
    """
    stream = generate_pptx_stream(request.slides, template_id=request.template_id)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=courseware.pptx"}
    )

@router.post("/exports/download/docx")
async def download_docx(request: DocxExportRequest, user_id: str = Depends(get_current_user)):
    """
    生成并下载 DOCX 教案文件
    """
    stream = generate_docx_stream(request.lessonPlan)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=lesson_plan.docx"}
    )

@router.delete("/exports/{export_id}")
async def remove_export(export_id: str, user_id: str = Depends(get_current_user)):
    """
    逻辑删除或物理删除导出记录
    """
    res = delete_export(export_id, user_id)
    if res is None:
        raise HTTPException(status_code=404, detail="记录不存在或无权删除")
    return {"status": "success", "message": "已删除导出记录"}
