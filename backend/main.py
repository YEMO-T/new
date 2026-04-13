from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="豆沙包教师助手 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """应用启动时预加载资源"""
    logger.info("[STARTUP] 🚀 应用正在启动...")
    
    try:
        from service.vector_service import preload_embedding_model
        preload_embedding_model()
        logger.info("[STARTUP] ✅ Embedding模型预加载完成")
    except Exception as e:
        logger.warning(f"[STARTUP] ⚠️ Embedding模型预加载失败（将在首次使用时加载）: {e}")
    
    logger.info("[STARTUP] ✅ 应用启动完成")

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Backend service is running"}

@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器错误：{str(exc)}"}
    )

from api import auth, chat, coursewares, knowledge, templates, templates_v2, exports, ppt_templates
from api import voice
from api import rag_knowledge, rag_chat, smart_answer
from api import vectorization_health
from api import ppt_generate

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(coursewares.router, prefix="/api", tags=["Coursewares"])
app.include_router(knowledge.router, prefix="/api", tags=["Knowledge"])
app.include_router(templates.router, prefix="/api", tags=["Templates"])
app.include_router(templates_v2.router)
app.include_router(exports.router, prefix="/api", tags=["Exports"])
app.include_router(ppt_templates.router)
app.include_router(ppt_generate.router)
app.include_router(rag_knowledge.router, prefix="/api", tags=["RAG Knowledge"])
app.include_router(rag_chat.router, prefix="/api", tags=["RAG Chat"])
app.include_router(smart_answer.router, prefix="/api", tags=["Smart Answer"])
app.include_router(vectorization_health.router, prefix="/api", tags=["Vectorization Health"])

if voice is not None:
    app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
else:
    logger.warning("voice 模块未加载，语音转文字功能不可用")

@app.get("/")
def read_root():
    return {"message": "Welcome to 豆沙包教师助手 API"}
