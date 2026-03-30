import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from schema.chat_schema import ChatRequest, PPTGenerateRequest, PPTSlide
from service.llm_service import chat_with_llm_stream, chat_with_llm, generate_ppt_structure_direct
from utils.ppt_generator import generate_pptx
from repository.supabase_client import insert_message, get_messages, insert_export, clear_chat_history
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat")
async def chat_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    对话接口（流式 SSE）：
    - 前端通过 EventSource / fetch stream 接收逐 token 数据
    - 每个 token 以 "data: <text>\n\n" 格式推送
    - 流结束时推送 "data: [DONE]\n\n"
    """
    # NOTE: 保存用户最新的一条消息到数据库
    if request.history:
        last_msg = request.history[-1]
        if last_msg.role == "user":
            insert_message(user_id=user_id, role="user", content=last_msg.content)

    accumulated_response = []

    async def event_generator():
        """SSE 事件生成器，逐 token 推送到前端"""
        try:
            # 传递 user_id 以支持 RAG 检索
            async for token in chat_with_llm_stream(request.prompt, request.history, user_id):
                accumulated_response.append(token)
                # 将 token 序列化为 JSON 字符串，保证特殊字符安全传输
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            # 针对常见 API 错误进行友好化处理
            if "Insufficient Balance" in error_msg or "402" in error_msg:
                friendly_err = "大模型服务余额不足，请检查账户或更换 API Key"
            elif "Authentication" in error_msg or "401" in error_msg:
                friendly_err = "API 认证失败，请检查密钥配置"
            else:
                friendly_err = f"生成出错：{error_msg}"
            
            logger.error(f"流式对话出错: {error_msg}")
            yield f"data: {json.dumps({'error': friendly_err}, ensure_ascii=False)}\n\n"
        finally:
            # NOTE: 流结束后保存完整的 AI 回复到数据库
            full_response = "".join(accumulated_response)
            if full_response:
                insert_message(user_id=user_id, role="assistant", content=full_response)
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁止 Nginx 缓冲，确保实时推送
        }
    )

@router.get("/chat/history")
async def get_history_endpoint(user_id: str = Depends(get_current_user)):
    """获取指定用户的历史对话记录"""
    messages = get_messages(user_id)
    return {"messages": messages}


@router.post("/chat/simple")
async def chat_simple_endpoint(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    非流式对话备用接口（用于不支持 SSE 的场景）
    """
    ai_response_text = await chat_with_llm(request.prompt, request.history, user_id)

    if ai_response_text:
        insert_message(user_id=user_id, role="assistant", content=ai_response_text)

    return {"message": ai_response_text}


@router.post("/chat/generate-ppt")
async def generate_ppt_endpoint(request: PPTGenerateRequest, user_id: str = Depends(get_current_user)):
    """
    一键生成 PPT: 需求解析 -> 结构化数据 -> PPT 渲染 -> 下载
    """
    try:
        # 1. 调用 AI 获取 PPT 结构化内容 (JSON)
        ai_structure = await generate_ppt_structure_direct(request, user_id)
        
        # 异常检查: 如果 AI 返回了错误标记
        if "_error" in ai_structure:
            err_msg = ai_structure["_error"]
            logger.error(f"AI 生成 PPT 结构失败: {err_msg}")
            raise HTTPException(status_code=500, detail=f"AI 生成 PPT 内容异常: {err_msg}")

        slides_raw = ai_structure.get("slides", [])
        if not slides_raw:
            raise HTTPException(status_code=500, detail="AI 返回了空的 PPT 大纲")

        # 2. 转换为 Pydantic 对象，确保数据符合规范
        validated_slides = []
        for s in slides_raw:
            try:
                validated_slides.append(PPTSlide(**s))
            except Exception as e:
                logger.warning(f"跳过格式错误的幻灯片数据: {e}")

        if not validated_slides:
             raise HTTPException(status_code=500, detail="幻灯片数据格式化失败")

        # 3. 后端渲染文件 (不存本地，直接在内存流中处理)
        pptx_io = generate_pptx(validated_slides)

        # 4. 记录导出记录到 Supabase (便于统计)
        insert_export(user_id, f"{request.theme} (AI直出)", "PPTX", "自动计算")

        # 5. 返回下载流 (StreamingResponse)
        filename = f"PPT_{request.theme}.pptx"
        return StreamingResponse(
            pptx_io,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"PPT 全链路生成出错: {e}")
        raise HTTPException(status_code=500, detail="服务器在渲染 PPT 时遇到了预期外的问题")


@router.delete("/chat/history")
async def clear_history_endpoint(user_id: str = Depends(get_current_user)):
    """
    清空当前用户的对话记录
    """
    res = clear_chat_history(user_id)
    if res is None:
        raise HTTPException(status_code=500, detail="清空历史记录失败")
    return {"message": "已成功开启新一轮对话"}
