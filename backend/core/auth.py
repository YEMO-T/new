"""JWT 认证中间件和依赖注入"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings
from datetime import datetime, timedelta, timezone

security = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 720

def create_access_token(user_id: str) -> str:
    """生成 JWT Token"""
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """验证 JWT Token 并返回 user_id"""
    if not credentials:
        print("[ERR] 缺少认证头")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证头")
    token = credentials.credentials
    print(f"[AUTH] 验证 Token: {token[:30]}...")
    print(f"[KEY] 使用 Secret Key: {settings.JWT_SECRET_KEY[:20]}...")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            print("[ERR] Token 中缺少 user_id")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
        print(f"[OK] Token 验证成功，user_id: {user_id}")
        return user_id
    except jwt.ExpiredSignatureError:
        print("[ERR] Token 已过期")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证令牌已过期")
    except jwt.InvalidTokenError as e:
        print(f"[ERR] Token 无效: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

def get_current_user(user_id: str = Depends(verify_token)) -> str:
    """依赖注入：获取当前用户 ID"""
    return user_id
