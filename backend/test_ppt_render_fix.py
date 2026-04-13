"""
PPT 渲染功能修复验证脚本
用于测试 /api/coursewares/preview 和 /api/coursewares/render 端点
"""

import requests
import json
import sys
import io

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:8000/api"

def get_auth_token():
    """获取认证 token"""
    login_url = f"{BASE_URL}/auth/login"
    payload = {
        "email": "test@test.com",
        "password": "123456"
    }
    
    try:
        response = requests.post(login_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token = data.get("token") or data.get("access_token")
            print(f"[✓] 登录成功, token: {token[:20]}...")
            return token
        else:
            print(f"[✗] 登录失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"[✗] 登录请求异常: {e}")
        return None

def test_preview_endpoint(token):
    """测试预览端点"""
    print("\n" + "="*60)
    print("[TEST] 测试 PPT 预览端点 (/coursewares/preview)")
    print("="*60)
    
    url = f"{BASE_URL}/coursewares/preview"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 模拟前端发送的数据格式（与 api.ts 中 previewRenderedPptx 一致）
    test_payload = {
        "title": "测试课件 - 验证修复",
        "template_id": None,
        "slides": [
            {
                "title": "封面页",
                "content": ["这是一个测试封面", "用于验证 422 错误修复"],
                "page_type": "title",
                "type": "title",
                "layout_suggestion": "title",
                "imagePrompt": None,
                "variables": {},
                "images": [],
                "tables": [],
                "charts": []
            },
            {
                "title": "内容页",
                "content": ["第一点：Python 是一门优秀的编程语言", 
                           "第二点：FastAPI 是一个高性能的 Web 框架",
                           "第三点：Pydantic 提供了强大的数据验证"],
                "page_type": "content",
                "type": "content",
                "layout_suggestion": "bullet_points",
                "imagePrompt": None,
                "variables": {},
                "images": [],
                "tables": [],
                "charts": []
            },
            {
                "title": "结束页",
                "content": ["谢谢观看！"],
                "page_type": "end",
                "type": "end",
                "layout_suggestion": "simple",
                "imagePrompt": None,
                "variables": {},
                "images": [],
                "tables": [],
                "charts": []
            }
        ]
    }
    
    print(f"\n[INFO] 发送请求:")
    print(f"  - URL: {url}")
    print(f"  - Title: {test_payload['title']}")
    print(f"  - Slides count: {len(test_payload['slides'])}")
    print(f"  - Template ID: {test_payload['template_id']}")
    
    try:
        response = requests.post(url, headers=headers, json=test_payload, timeout=120)
        
        print(f"\n[RESULT] 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[✓] 预览成功!")
            print(f"  - Status: {data.get('status')}")
            print(f"  - Title: {data.get('title')}")
            print(f"  - Total slides: {data.get('total_slides')}")
            print(f"  - Render time: {data.get('render_time', 'N/A')}s")
            
            slides = data.get('slides', [])
            if slides:
                print(f"\n[SLIDES] 幻灯片预览:")
                for i, slide in enumerate(slides[:3]):
                    print(f"  [{i+1}] {slide.get('title', 'N/A')}: image={'有' if slide.get('image') else '无'}")
            
            return True
            
        elif response.status_code == 422:
            print(f"[✗] 422 验证错误 (未完全修复)!")
            try:
                error_data = response.json()
                print(f"  - Detail: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"  - Response: {response.text[:500]}")
            return False
            
        elif response.status_code == 401:
            print(f"[✗] 401 认证失败，请检查 token")
            return False
            
        else:
            print(f"[!] 其他状态码: {response.status_code}")
            print(f"  - Response: {response.text[:300]}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"[✗] 请求超时 (120秒)")
        return False
    except Exception as e:
        print(f"[✗] 请求异常: {type(e).__name__}: {e}")
        return False

def test_render_endpoint(token):
    """测试渲染端点"""
    print("\n" + "="*60)
    print("[TEST] 测试 PPT 渲染端点 (/coursewares/render)")
    print("="*60)
    
    url = f"{BASE_URL}/coursewares/render"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    test_payload = {
        "title": "正式渲染测试课件",
        "template_id": None,
        "lesson_plan": None,
        "interaction": None,
        "slides": [
            {
                "title": "第一章",
                "content": ["这是正式渲染测试", "验证完整流程"],
                "page_type": "content",
                "type": "content",
                "layout_suggestion": "bullet_points",
                "imagePrompt": None,
                "variables": {},
                "images": [],
                "tables": [],
                "charts": []
            }
        ]
    }
    
    print(f"\n[INFO] 发送渲染请求...")
    
    try:
        response = requests.post(url, headers=headers, json=test_payload, timeout=120)
        
        print(f"\n[RESULT] 响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[✓] 渲染成功!")
            print(f"  - Status: {data.get('status')}")
            print(f"  - File URL: {data.get('file_url', 'N/A')[:50]}...")
            return True
            
        elif response.status_code == 422:
            print(f"[✗] 422 验证错误!")
            try:
                error_data = response.json()
                print(f"  - Detail: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"  - Response: {response.text[:500]}")
            return False
        else:
            print(f"[!] 状态码: {response.status_code} - {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"[✗] 请求异常: {e}")
        return False

def main():
    print("=" * 60)
    print("PPT 渲染功能修复验证工具")
    print("=" * 60)
    
    # 1. 获取 token
    token = get_auth_token()
    if not token:
        print("\n[FAIL] 无法获取认证 token，终止测试")
        sys.exit(1)
    
    # 2. 测试预览端点
    preview_ok = test_preview_endpoint(token)
    
    # 3. 测试渲染端点
    render_ok = test_render_endpoint(token)
    
    # 4. 总结
    print("\n" + "=" * 60)
    print("[SUMMARY] 测试结果总结")
    print("=" * 60)
    print(f"  Preview Endpoint: {'✓ PASS' if preview_ok else '✗ FAIL'}")
    print(f"  Render Endpoint:  {'✓ PASS' if render_ok else '✗ FAIL'}")
    
    if preview_ok and render_ok:
        print("\n[SUCCESS] 所有测试通过! PPT 渲染功能已修复 ✓")
        return 0
    else:
        print("\n[WARNING] 部分测试未通过，请检查日志获取详细信息")
        return 1

if __name__ == "__main__":
    exit(main())
