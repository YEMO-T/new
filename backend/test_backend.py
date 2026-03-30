#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后端功能检查脚本
检查所有关键模块和API是否正常工作
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("🔍 后端功能检查工具")
print("=" * 60)

# ============ 1. 检查环境配置 ============
print("\n1️⃣  检查环境配置...")
from dotenv import load_dotenv
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print("   ✅ .env 文件已加载")
else:
    print("   ⚠️  .env 文件不存在")

# ============ 2. 检查必要的依赖 ============
print("\n2️⃣  检查必要的依赖包...")
required_packages = {
    'fastapi': 'FastAPI 框架',
    'uvicorn': 'ASGI 服务器',
    'pydantic': '数据验证',
    'supabase': 'Supabase 客户端',
    'python_pptx': 'PPT 解析',
    'openai': 'LLM 客户端',
    'jwt': 'JWT 认证',
}

missing_packages = []
for package, description in required_packages.items():
    try:
        __import__(package)
        print(f"   ✅ {package:20} - {description}")
    except ImportError:
        print(f"   ❌ {package:20} - {description} (未安装)")
        missing_packages.append(package)

if missing_packages:
    print(f"\n   ⚠️  缺少依赖包: {', '.join(missing_packages)}")
    print(f"   运行: pip install {' '.join(missing_packages)}")

# ============ 3. 检查后端模块 ============
print("\n3️⃣  检查后端模块...")
modules_to_check = {
    'backend.api.auth': 'Auth API',
    'backend.api.chat': 'Chat API',
    'backend.api.coursewares': 'Coursewares API',
    'backend.api.knowledge': 'Knowledge API',
    'backend.api.templates': 'Templates API',
    'backend.api.templates_v2': 'Templates V2 API',
    'backend.api.exports': 'Exports API',
    'backend.service.llm_service': 'LLM Service',
    'backend.service.template_service': 'Template Service',
    'backend.service.ppt_parser': 'PPT Parser',
    'backend.repository.supabase_client': 'Supabase Client',
}

module_errors = {}
for module_name, description in modules_to_check.items():
    try:
        __import__(module_name)
        print(f"   ✅ {description:20} ({module_name})")
    except Exception as e:
        error_msg = str(e)[:60]
        print(f"   ❌ {description:20} - {error_msg}")
        module_errors[module_name] = str(e)

# ============ 4. 检查配置参数 ============
print("\n4️⃣  检查配置参数...")
config_vars = {
    'SUPABASE_URL': 'Supabase URL',
    'SUPABASE_KEY': 'Supabase Key',
    'LLM_API_BASE': 'LLM API 地址',
    'LLM_API_KEY': 'LLM API 密钥',
    'LLM_MODEL': 'LLM 模型名',
}

missing_vars = []
for var_name, description in config_vars.items():
    value = os.getenv(var_name)
    if value:
        # 隐藏敏感信息
        if 'KEY' in var_name or 'PASSWORD' in var_name:
            display_value = f"{value[:10]}..." if len(value) > 10 else "***"
        else:
            display_value = value
        print(f"   ✅ {var_name:20} = {display_value}")
    else:
        print(f"   ⚠️  {var_name:20} (未配置)")
        missing_vars.append(var_name)

# ============ 5. 检查数据库连接 ============
print("\n5️⃣  检查数据库连接...")
try:
    from backend.repository import supabase_client
    client = supabase_client.get_client()
    
    # 尝试执行简单查询
    try:
        result = client.table('users').select('id').limit(1).execute()
        print(f"   ✅ Supabase 连接成功")
        print(f"   ✅ 能够查询 users 表")
    except Exception as e:
        if "JWT" in str(e) or "auth" in str(e).lower():
            print(f"   ⚠️  Supabase 连接成功，但需要认证")
            print(f"      (这是正常的，公开数据需要 RLS 策略)")
        else:
            print(f"   ❌ 数据库查询失败: {str(e)[:60]}")
except Exception as e:
    print(f"   ❌ Supabase 连接失败: {str(e)[:60]}")

# ============ 6. 检查 FastAPI 应用 ============
print("\n6️⃣  检查 FastAPI 应用...")
try:
    from backend.main import app
    print(f"   ✅ FastAPI 应用加载成功")
    
    # 检查已注册的路由
    routes = [route.path for route in app.routes]
    api_routes = [r for r in routes if r.startswith('/api')]
    print(f"   ✅ 已注册 {len(routes)} 个路由")
    print(f"   ✅ API 路由: {len(api_routes)} 个")
    
    # 列出一些关键路由
    key_routes = ['/api/health', '/api/auth/login', '/api/chat', '/api/templates']
    for route in key_routes:
        if any(r.startswith(route) for r in routes):
            print(f"      - {route} ✅")
        else:
            print(f"      - {route} ❌")
except Exception as e:
    print(f"   ❌ FastAPI 应用加载失败: {str(e)[:100]}")
    if module_errors:
        print(f"\n   关键模块加载错误:")
        for mod, err in module_errors.items():
            print(f"      - {mod}: {err[:80]}")

# ============ 7. 功能测试 ============
print("\n7️⃣  功能测试...")
try:
    from fastapi.testclient import TestClient
    from backend.main import app
    
    client = TestClient(app)
    
    # 测试健康检查
    print("   测试健康检查接口...")
    response = client.get("/api/health")
    if response.status_code == 200:
        print(f"   ✅ GET /api/health - {response.json()}")
    else:
        print(f"   ❌ GET /api/health - 状态码 {response.status_code}")
    
    # 测试根路由
    print("   测试根路由...")
    response = client.get("/")
    if response.status_code == 200:
        print(f"   ✅ GET / - {response.json()}")
    else:
        print(f"   ❌ GET / - 状态码 {response.status_code}")
        
except Exception as e:
    print(f"   ❌ 功能测试失败: {str(e)}")

# ============ 总结 ============
print("\n" + "=" * 60)
print("📋 检查总结")
print("=" * 60)

if missing_packages:
    print(f"\n⚠️  需要安装依赖包:")
    print(f"   pip install {' '.join(missing_packages)}")
    
if missing_vars:
    print(f"\n⚠️  需要配置环境变量:")
    for var in missing_vars:
        print(f"   - {var}")

if module_errors:
    print(f"\n❌ 模块加载错误:")
    for mod, err in module_errors.items():
        print(f"   {mod}")
        print(f"   └─ {err[:100]}")

print("\n✨ 检查完成！")
print("\n建议:")
print("   1. 确保所有依赖已安装")
print("   2. 确保 .env 文件配置完整")
print("   3. 如果需要数据库，运行迁移脚本")
print("   4. 运行: uvicorn backend.main:app --reload")
print("\n" + "=" * 60)
