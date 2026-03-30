from fastapi import APIRouter
from schema.auth_schema import RegisterRequest, LoginRequest, AuthResponse
from service.auth_service import register_user, login_user

# 必须定义这个 router，名字不能错！
router = APIRouter()

@router.post("/register", response_model=AuthResponse)
async def register_endpoint(request: RegisterRequest):
    result = await register_user(
        username=request.username,
        email=request.email,
        password=request.password
    )
    return result

@router.post("/login", response_model=AuthResponse)
async def login_endpoint(request: LoginRequest):
    result = await login_user(email=request.email, password=request.password)
    return result