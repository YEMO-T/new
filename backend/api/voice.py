from fastapi import APIRouter, UploadFile, File, HTTPException
from service.voice_service import voice_service
from schema.voice_schema import TranscribeResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_voice(file: UploadFile = File(...)):
    """
    语音转文字接口
    1. 接收前端上传的音频文件 (webm, mp3, wav等)
    2. 调用 VoiceService 进行音频识别
    3. 返回识别后的文本、时长等元数据
    """
    # 简单的格式校验
    allowed_extensions = {".webm", ".mp3", ".wav", ".m4a", ".aac"}
    filename = file.filename or "audio.webm"
    ext = filename[filename.rfind("."):].lower()
    
    if ext not in allowed_extensions:
        logger.warning(f"上传了不支持的文件格式: {ext}")
        # 不强制拦截，让 pydub 尝试处理，若失败再返回错误
    
    try:
        # 读取二进制数据
        file_content = await file.read()
        if not file_content:
             raise HTTPException(status_code=400, detail="音频文件为空")

        # 调用语音识别服务
        text, duration = await voice_service.transcribe(file_content, filename)
        
        if not text:
            # 识别出空文本
            return TranscribeResponse(
                text="[未能识别出文字]", 
                duration=duration,
                language="zh"
            )

        return TranscribeResponse(
            text=text,
            duration=duration,
            language="zh"
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"语音识别 API 失败: {error_msg}")
        
        # 针对常见环境错误的友好提示
        if "ffmpeg" in error_msg.lower():
            raise HTTPException(
                status_code=500, 
                detail="后端环境缺失 FFmpeg，请联系管理员配置环境系统变量。"
            )
        
        raise HTTPException(
            status_code=500, 
            detail=f"语音识别服务暂时不可用: {error_msg}"
        )
