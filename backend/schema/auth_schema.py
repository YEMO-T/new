from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class RegisterRequest(BaseModel):
    """用户注册请求体"""
    username: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v

    @field_validator("username")
    @classmethod
    def username_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("用户名不能为空")
        return v.strip()


class LoginRequest(BaseModel):
    """用户登录请求体"""
    email: EmailStr
    password: str


class UserInfo(BaseModel):
    """返回给前端的用户信息（不含密码）"""
    id: str
    username: str
    email: str
    role: str


class AuthResponse(BaseModel):
    """认证成功后的响应"""
    token: str
    user: UserInfo
