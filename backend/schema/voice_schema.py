from pydantic import BaseModel
from typing import Optional

class TranscribeResponse(BaseModel):
    """
    语音转文字响应模型
    """
    text: str                # 识别出的文本内容
    duration: float          # 音频时长（秒）
    confidence: Optional[float] = None # 识别置信度（部分引擎支持）
    language: Optional[str] = None    # 识别出的语言
