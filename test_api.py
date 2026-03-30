import sys
import os
sys.path.append(os.path.abspath("backend"))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

response = client.post("/api/chat", json={"prompt": "hello", "history": []})
print(response.status_code)
print(response.json())
