import logging
import hashlib
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import HTTPException
from core.config import settings
from repository.supabase_client import get_user_by_email, create_user

logger = logging.getLogger(__name__)

# 使用统一的 JWT 配置
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30  # 延长到 30 天（原来是 7 天）

# ===================== 已修复：采用 SHA-256 预哈希 + 直接调用 bcrypt 库 =====================
# 由于 passlib 在当前环境下即便是处理 64 位 SHA-256 哈希仍会报错，改为直接驱动 bcrypt 底层库。
def _get_prehashed_password(password: str) -> str:
    """使用 SHA-256 对原始密码进行预哈希，确保输入 bcrypt 的长度固定为 64 字节"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _hash_password(plain_password: str) -> str:
    """将明文密码哈希化（先 SHA-256，后 bcrypt）"""
    prehashed = _get_prehashed_password(plain_password)
    # bcrypt 要求输入为 bytes
    password_bytes = prehashed.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8") # 转为字符串存储到数据库

def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    try:
        prehashed = _get_prehashed_password(plain_password)
        password_bytes = prehashed.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False
# ==============================================================================================


def _create_access_token(user_id: str, email: str) -> str:
    """
    生成 JWT Token，有效期 30 天
    """
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)
    print(f"[OK] 生成 Token: {token[:30]}...")
    print(f"[KEY] 使用 Secret Key: {settings.JWT_SECRET_KEY[:20]}...")
    return token


async def register_user(username: str, email: str, password: str) -> dict:
    """
    注册新用户业务逻辑：
    1. 检查邮箱是否已存在
    2. 哈希密码
    3. 写入 Supabase users 表
    4. 返回 token 和用户信息
    """
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已被注册，请直接登录")

    hashed_pwd = _hash_password(password)
    new_user = create_user(email=email, username=username, hashed_password=hashed_pwd)

    if not new_user:
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")

    token = _create_access_token(user_id=str(new_user["id"]), email=email)
    return {
        "token": token,
        "user": {
            "id": str(new_user["id"]),
            "username": new_user["username"],
            "email": new_user["email"],
            "role": new_user.get("role", "teacher")
        }
    }


async def login_user(email: str, password: str) -> dict:
    """
    登录验证业务逻辑：
    1. 查询用户
    2. 验证密码哈希
    3. 返回 token 和用户信息
    """
    user = get_user_by_email(email)
    if not user:
        # NOTE: 故意不区分"用户不存在"和"密码错误"，防止邮箱枚举攻击
        raise HTTPException(status_code=401, detail="邮箱或密码不正确，请重新输入")

    if not _verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="邮箱或密码不正确，请重新输入")

    token = _create_access_token(user_id=str(user["id"]), email=email)
    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "teacher")
        }
    }