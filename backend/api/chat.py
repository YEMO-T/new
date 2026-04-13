import json
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse
from schema.chat_schema import ChatRequest, PPTGenerateRequest, PPTSlide
from service.llm_service import chat_with_llm_stream, chat_with_llm, generate_ppt_structure_direct
from utils.ppt_generator import generate_pptx, generate_ppt_from_template, get_template_local_path
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
    - 集成RAG知识库自动检索
    - 添加心跳机制防止连接超时断开
    """
    if request.history:
        last_msg = request.history[-1]
        if last_msg.role == "user":
            insert_message(user_id=user_id, role="user", content=last_msg.content)

    accumulated_response = []

    async def event_generator():
        """SSE 事件生成器，逐 token 推送到前端，带心跳保活"""
        heartbeat_interval = 15  # 每15秒发送一次心跳
        try:
            async for token in chat_with_llm_stream(request.prompt, request.history, user_id):
                accumulated_response.append(token)
                payload = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            logger.info("[SSE] 客户端断开连接 (CancelledError)")
            yield f"data: {json.dumps({'error': '连接已关闭'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            if "Insufficient Balance" in error_msg or "402" in error_msg:
                friendly_err = "大模型服务余额不足，请检查账户或更换 API Key"
            elif "Authentication" in error_msg or "401" in error_msg:
                friendly_err = "API 认证失败，请检查密钥配置"
            elif "AbortError" in error_msg or "BodyStreamDiffers" in error_msg:
                friendly_err = "连接中断，请重试"
            else:
                friendly_err = f"生成出错：{error_msg}"
            
            logger.error(f"流式对话出错: {error_msg}")
            yield f"data: {json.dumps({'error': friendly_err}, ensure_ascii=False)}\n\n"
        finally:
            full_response = "".join(accumulated_response)
            if full_response:
                try:
                    insert_message(user_id=user_id, role="assistant", content=full_response)
                except Exception as save_err:
                    logger.warning(f"[SSE] 保存对话记录失败: {save_err}")
            yield "data: [DONE]\n\n"

    async def event_generator_with_heartbeat():
        """带心跳的SSE生成器"""
        generator = event_generator()
        
        while True:
            try:
                done, awaitable = asyncio.wait(
                    [asyncio.ensure_future(generator.__anext__()), 
                     asyncio.sleep(heartbeat_interval)],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    if task is list(done)[0]:
                        result = task.result()
                        yield result
                        
                        if "[DONE]" in result or '"error"' in result:
                            return
                    else:
                        pass
                
            except StopAsyncIteration:
                break
            except Exception as e:
                if isinstance(e, StopAsyncIteration):
                    break
                
                for task in asyncio.all_tasks():
                    if not task.done() and task != asyncio.current_task():
                        task.cancel()
                        
                yield f": heartbeat\n\n"
                continue

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream; charset=utf-8",
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
    一键生成 PPT: 需求解析 -> 结构化数据 -> PPT渲染 -> 下载
    支持模板渲染：如果提供 template_id，将使用模板样式生成PPT
    """
    template_id = getattr(request, 'template_id', None)
    
    try:
        ai_structure = await generate_ppt_structure_direct(request, user_id, template_id)
        
        if "_error" in ai_structure:
            err_msg = ai_structure["_error"]
            logger.error(f"AI 生成 PPT 结构失败: {err_msg}")
            raise HTTPException(status_code=500, detail=f"AI 生成 PPT 内容异常: {err_msg}")

        slides_raw = ai_structure.get("slides", [])
        if not slides_raw:
            raise HTTPException(status_code=500, detail="AI 返回了空的 PPT 大纲")

        validated_slides = []
        for s in slides_raw:
            try:
                validated_slides.append(PPTSlide(**s))
            except Exception as e:
                logger.warning(f"跳过格式错误的幻灯片数据: {e}")

        if not validated_slides:
             raise HTTPException(status_code=500, detail="幻灯片数据格式化失败")

        pptx_io = generate_pptx(validated_slides, template_id)
        
        insert_export(user_id, f"{request.theme} (AI直出{'+' + template_id[:8] if template_id else ''})", "PPTX", "自动计算")

        filename = f"PPT_{request.theme}.pptx"
        return StreamingResponse(
            pptx_io,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
                "X-Template-Used": template_id or "default"
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"PPT 全链路生成出错: {e}")
        raise HTTPException(status_code=500, detail=f"服务器在渲染 PPT 时遇到了预期外的问题: {str(e)}")


@router.delete("/chat/history")
async def clear_history_endpoint(user_id: str = Depends(get_current_user)):
    """
    清空当前用户的对话记录
    """
    res = clear_chat_history(user_id)
    if res is None:
        raise HTTPException(status_code=500, detail="清空历史记录失败")
    return {"message": "已成功开启新一轮对话"}
