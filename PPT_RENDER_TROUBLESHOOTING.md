# PPT渲染失败排查指南

## 🚨 快速诊断步骤

### 步骤1：检查浏览器控制台

打开浏览器开发者工具（F12），查看Console标签页，寻找以下信息：

```javascript
// 查找这些关键日志
[handlePreviewRendered] 开始渲染预览, 幻灯片数: X
[previewRenderedPptx] 发送预览请求: {...}
[previewRenderedPptx] 预览成功: {...}
// 或错误信息
[handlePreviewRendered] API错误详情: {...}
```

### 步骤2：检查网络请求

在开发者工具的Network标签页中：
1. 筛选 `preview` 请求
2. 查看请求状态码：
   - ✅ 200: 成功
   - ❌ 422: 请求体格式错误
   - ❌ 500: 服务器内部错误
   - ❌ 401: 未授权
   - ❌ 504: 网关超时

### 步骤3：检查后端服务

```bash
# 确认后端服务正在运行
curl http://localhost:8000/api/health

# 或在浏览器中访问
http://localhost:8000/docs
```

---

## 🔍 常见错误和解决方案

### 错误1：422 Unprocessable Content

**原因：** 请求体格式不符合后端要求

**检查清单：**
- [ ] 请求体包含 `slides` 数组（不是 `slideCount`）
- [ ] 字段名使用下划线：`template_id`（不是 `templateId`）
- [ ] `content` 是数组类型
- [ ] 所有必填字段都存在

**解决方案：**

```typescript
// ✅ 正确的请求体格式
{
  "slides": [
    {
      "title": "第1页",
      "content": ["内容1", "内容2"],
      "page_type": "content",
      "type": "content",
      "layout_suggestion": "bullet_points",
      "variables": {},
      "images": [],
      "tables": [],
      "charts": []
    }
  ],
  "title": "课件标题",
  "template_id": "模板ID或null"
}
```

**如何验证：**
在浏览器控制台运行：
```javascript
console.log('[请求体]', JSON.stringify({
  slides: normalizedSlides,
  title: title,
  template_id: templateId
}, null, 2));
```

---

### 错误2：超时错误

**原因：** 渲染时间过长（默认180秒）

**解决方案：**

1. **增加超时时间**
```typescript
// 在 src/services/api.ts 中修改
const RENDER_TIMEOUT = 300000; // 改为5分钟
```

2. **优化幻灯片内容**
   - 减少每页的内容量
   - 简化图表和表格
   - 减少图片数量

3. **检查后端性能**
```bash
# 查看后端日志
tail -f backend.log

# 检查后端资源使用
top
```

---

### 错误3：网络错误

**原因：** 后端服务未启动或网络不通

**解决方案：**

1. **检查后端服务**
```bash
# 启动后端服务
cd backend
python main.py

# 或使用uvicorn
uvicorn main:app --reload --port 8000
```

2. **检查API地址**
```typescript
// 在 src/services/api.ts 中确认
const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api';
```

3. **检查CORS配置**
在后端添加CORS中间件：
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 错误4：认证错误 (401)

**原因：** 未登录或token过期

**解决方案：**

1. **检查token**
```javascript
// 在浏览器控制台运行
console.log('Token:', localStorage.getItem('auth_token'));
```

2. **重新登录**
```javascript
// 清除旧token
localStorage.removeItem('auth_token');
// 重新登录
```

3. **检查token是否有效**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/user/me
```

---

### 错误5：服务器内部错误 (500)

**原因：** 后端代码错误或配置问题

**解决方案：**

1. **查看后端日志**
```bash
# 查看详细错误堆栈
tail -100 backend.log

# 或在控制台查看
python main.py
```

2. **检查后端依赖**
```bash
pip install -r requirements.txt
```

3. **检查数据库连接**
```bash
# 测试数据库连接
python -c "from database import engine; engine.connect()"
```

---

## 🛠️ 调试工具

### 1. 完整的调试函数

在浏览器控制台运行：

```javascript
// 调试PPT渲染
async function debugPPTRender() {
  const slides = window.slides; // 从全局变量获取
  const title = slides[0]?.title || '测试课件';
  
  console.log('=== 开始调试 ===');
  console.log('幻灯片数量:', slides.length);
  console.log('第一张幻灯片:', slides[0]);
  
  try {
    const response = await fetch('http://localhost:8000/api/coursewares/preview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
      },
      body: JSON.stringify({
        slides: slides,
        title: title,
        template_id: null
      })
    });
    
    console.log('响应状态:', response.status);
    console.log('响应头:', response.headers);
    
    const data = await response.json();
    console.log('响应数据:', data);
    
    if (!response.ok) {
      console.error('错误详情:', data);
    }
  } catch (error) {
    console.error('请求失败:', error);
  }
}

debugPPTRender();
```

### 2. 检查幻灯片数据

```javascript
// 验证幻灯片格式
function validateSlides(slides) {
  slides.forEach((slide, index) => {
    console.log(`幻灯片 ${index + 1}:`, {
      title: slide.title,
      contentType: typeof slide.content,
      isArray: Array.isArray(slide.content),
      contentLength: Array.isArray(slide.content) ? slide.content.length : 'N/A'
    });
  });
}

validateSlides(window.slides);
```

### 3. 测试后端连接

```javascript
// 测试后端健康状态
async function testBackend() {
  try {
    const response = await fetch('http://localhost:8000/api/health');
    console.log('后端状态:', response.status);
    const data = await response.json();
    console.log('健康检查:', data);
  } catch (error) {
    console.error('后端连接失败:', error);
  }
}

testBackend();
```

---

## 📊 性能优化建议

### 1. 减少幻灯片数量

```typescript
// 分批渲染
const batchSize = 5;
for (let i = 0; i < slides.length; i += batchSize) {
  const batch = slides.slice(i, i + batchSize);
  await previewRenderedPptx(batch, title, templateId);
}
```

### 2. 简化内容

```typescript
// 限制每页内容量
const maxContentPerSlide = 10;
slides.forEach(slide => {
  if (Array.isArray(slide.content) && slide.content.length > maxContentPerSlide) {
    slide.content = slide.content.slice(0, maxContentPerSlide);
  }
});
```

### 3. 使用缓存

```typescript
// 缓存渲染结果
const cache = new Map();

async function previewWithCache(slides, title, templateId) {
  const key = JSON.stringify({ slides, title, templateId });
  
  if (cache.has(key)) {
    console.log('使用缓存结果');
    return cache.get(key);
  }
  
  const result = await previewRenderedPptx(slides, title, templateId);
  cache.set(key, result);
  return result;
}
```

---

## 🎯 完整的故障排查流程

```
开始
  ↓
检查浏览器控制台
  ↓
有错误信息？
  ├─ 是 → 根据错误类型处理
  └─ 否 → 检查网络请求
           ↓
       查看请求状态码
           ↓
       200？→ 检查响应数据
       422？→ 检查请求体格式
       500？→ 检查后端日志
       401？→ 检查认证token
       超时？→ 增加超时时间
           ↓
       问题解决？
           ├─ 是 → 完成
           └─ 否 → 联系技术支持
```

---

## 📞 获取帮助

如果以上步骤都无法解决问题，请提供以下信息：

1. **浏览器控制台完整日志**
2. **网络请求详情**（Request和Response）
3. **后端日志**
4. **幻灯片数据示例**
5. **环境信息**：
   - 操作系统
   - Node.js版本
   - 浏览器版本
   - 后端框架版本

---

## ✅ 预防措施

1. **定期检查后端服务状态**
2. **监控渲染时间和成功率**
3. **实施请求重试机制**
4. **添加用户友好的错误提示**
5. **记录详细的错误日志**

---

## 🔗 相关文档

- [API错误处理文档](./errorUtils.ts)
- [请求管理器文档](./requestManager.ts)
- [PPT预览组件文档](../components/PPTPreviewView.tsx)
- [后端API文档](http://localhost:8000/docs)
