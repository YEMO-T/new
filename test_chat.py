import requests
import json

# 测试登录
login_url = "http://localhost:8000/api/auth/login"
login_data = {
    "email": "563375411@qq.com",
    "password": "2580ab"
}

print("🔐 测试登录...")
response = requests.post(login_url, json=login_data)
print(f"状态码: {response.status_code}")
print(f"响应: {response.json()}")

if response.status_code == 200:
    token = response.json().get("token")
    print(f"✅ 登录成功，Token: {token[:20]}...")
    
    # 测试对话
    chat_url = "http://localhost:8000/api/chat"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    chat_data = {
        "prompt": "你好，请帮我生成一个小学数学课件大纲",
        "history": [],
        "user_id": response.json()["user"]["id"]
    }
    
    print("\n💬 测试对话...")
    response = requests.post(chat_url, json=chat_data, headers=headers, stream=True)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ 对话接口响应成功，流式数据:")
        for line in response.iter_lines():
            if line:
                print(line.decode('utf-8'))
    else:
        print(f"❌ 对话接口错误: {response.text}")
else:
    print("❌ 登录失败")
