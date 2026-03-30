import os
from dotenv import load_dotenv

# 显式指定 .env 文件路径 - 从项目根目录查找
backend_dir = os.path.dirname(__file__)
project_root = os.path.dirname(os.path.dirname(backend_dir))
env_path = os.path.join(project_root, '.env')

print(f"[INFO] 项目根目录: {project_root}")
print(f"[INFO] 加载 .env 文件: {env_path}")
print(f"[INFO] .env 文件存在: {os.path.exists(env_path)}")

load_dotenv(env_path)

class Settings:
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # NOTE: 大模型配置 — 仅使用 Moonshot / Kimi
    LLM_PROVIDER: str = "moonshot"
    LLM_API_KEY: str = os.getenv("MOONSHOT_API_KEY", "")
    LLM_API_BASE: str = os.getenv("MOONSHOT_API_BASE", "https://api.moonshot.cn/v1")
    LLM_MODEL: str = os.getenv("MOONSHOT_MODEL", "moonshot-v1-32k")
    
    # JWT 认证配置
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-环保署-豆沙包-教师助手")

settings = Settings()

# 验证关键配置
if not settings.LLM_API_KEY:
    print("[WARN] 警告: MOONSHOT_API_KEY 未配置")
else:
    print(f"[OK] MOONSHOT_API_KEY 已加载: {settings.LLM_API_KEY[:20]}...")

if not settings.SUPABASE_URL:
    print("[WARN] 警告: SUPABASE_URL 未配置")
else:
    print(f"[OK] SUPABASE_URL 已加载")



