from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional
from service.voice_service import voice_service
from schema.voice_schema import TranscribeResponse
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mp3",
    "audio/mpeg", "audio/mp4", "audio/aac", "audio/x-m4a",
    "audio/flac", "audio/opus", "application/octet-stream",
}
SUPPORTED_LANGUAGES = {
    "zh", "en", "ja", "ko", "fr", "de", "es", "pt", "ru", "ar",
    "hi", "it", "th", "vi", "tr", "pl", "nl", "sv", "id", "ms",
}

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_voice(
    file: UploadFile = File(...),
    language: Optional[str] = Query(None, description="指定语言代码，如 zh/en/ja，不传则自动检测")
):
    """
    语音转文字接口 v2.1
    
    接收前端上传的音频文件，调用 Whisper 进行语音识别。
    支持 webm/mp3/wav/m4a/aac/ogg/flac/opus 格式。
    """
    filename = file.filename or "audio.webm"
    content_type = (file.content_type or "").strip().lower()
    
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(f"[语音转写] 非标准音频 Content-Type: {content_type}，将尝试处理")

    if language and language.lower() not in SUPPORTED_LANGUAGES:
        logger.warning(f"[语音转写] 非常见语言代码: {language}，将传递给Whisper自动处理")

    logger.info(f"[语音转写] 收到请求: filename={filename}, content_type={content_type}")

    try:
        file_content = await file.read()
        
        if not file_content:
            raise HTTPException(status_code=400, detail="上传的音频文件为空，请重新录音")

        actual_size = len(file_content)
        logger.info(f"[语音转写] 文件大小: {actual_size / 1024:.1f}KB")
        
        if actual_size > MAX_AUDIO_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"音频文件过大({actual_size / 1024 / 1024:.1f}MB)，上限50MB"
            )

        if actual_size < 1024:
            raise HTTPException(
                status_code=400,
                detail="录音时间过短，未检测到有效语音，请重新录制（建议录音1秒以上）"
            )

        t0 = time.time()
        text, duration = await voice_service.transcribe(file_content, filename, language=language)
        elapsed = time.time() - t0
        
        logger.info(f"[语音转写] 完成: 耗时={elapsed:.2f}s, 文本长度={len(text)}, 时长={duration:.1f}s")

        if not text or not text.strip():
            return TranscribeResponse(
                text="",
                duration=duration,
                confidence=None,
                language=language,
                message="未能识别出文字内容，可能是录音过短或环境噪音过大"
            )

        return TranscribeResponse(
            text=text.strip(),
            duration=round(duration, 2),
            language=language,
            message="success"
        )

    except ValueError as e:
        logger.warning(f"[语音转写] 参数校验失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except RuntimeError as e:
        err_msg = str(e)
        logger.error(f"[语音转写] 模型错误: {err_msg}")
        if "模型尚未就绪" in err_msg or "加载" in err_msg:
            raise HTTPException(
                status_code=503,
                detail="语音识别模型正在初始化中，请稍后重试（约5-10秒）"
            )
        raise HTTPException(status_code=500, detail=f"语音模型异常: {err_msg}")

    except HTTPException:
        raise
    
    except Exception as e:
        err_msg = str(e)
        logger.error(f"[语音转写] 未预期错误: {err_msg}", exc_info=True)

        if "ffmpeg" in err_msg.lower() and ("找不到" in err_msg or "not found" in err_msg.lower()):
            raise HTTPException(
                status_code=500,
                detail="服务器缺少FFmpeg组件，请联系管理员安装。访问 https://ffmpeg.org/download.html 下载。"
            )
        
        if "whisper" in err_msg.lower():
            raise HTTPException(
                status_code=500,
                detail="语音识别引擎异常，请稍后重试"
            )
        
        raise HTTPException(
            status_code=500,
            detail=f"语音识别服务暂时不可用: {err_msg[:120]}"
        )
