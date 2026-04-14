from pydantic import BaseModel
from typing import Optional

class TranscribeResponse(BaseModel):
    text: str
    duration: float
    confidence: Optional[float] = None
    language: Optional[str] = None
    message: Optional[str] = None
