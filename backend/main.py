from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback

# 只导入必要的模块，避免sentence_transformers导入错误
try:
    from api import chat, coursewares, auth, knowledge, templates, exports, templates_v2, voice
except Exception as e:
    print(f"导入API模块失败: {e}")
    traceback.print_exc()

app = FastAPI(title="豆沙包教师助手 API", version="1.0.0")

# 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ========== 健康检查接口 ==========
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Backend service is running"}
# =================================

# ========== 全局异常捕获 ==========
@app.exception_handler(Exception)
async def catch_all_exceptions(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器错误：{str(exc)}"}
    )
# =================================

# 注册路由
try:
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(chat.router, prefix="/api", tags=["Chat"])
    app.include_router(coursewares.router, prefix="/api", tags=["Coursewares"])
    app.include_router(knowledge.router, prefix="/api", tags=["Knowledge"])
    app.include_router(templates.router, prefix="/api", tags=["Templates"])
    app.include_router(templates_v2.router)
    app.include_router(exports.router, prefix="/api", tags=["Exports"])
    app.include_router(voice.router, prefix="/api/voice", tags=["Voice"])
except Exception as e:
    print(f"注册路由失败: {e}")
    traceback.print_exc()

@app.get("/")
def read_root():
    return {"message": "Welcome to 豆沙包教师助手 API"}
