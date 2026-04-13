# 🚨 PPT渲染失败 - 快速修复指南

## ⚡ 3步快速诊断

### 步骤1：打开浏览器控制台
按 `F12` 打开开发者工具，切换到 Console 标签页

### 步骤2：运行诊断命令
在控制台输入并回车：
```javascript
runDiagnostics()
```

### 步骤3：查看结果
根据诊断结果采取相应措施

---

## 🔧 快速修复命令

### 一键修复
```javascript
quickFix()
```
自动检查并修复常见问题

### 测试后端连接
```javascript
testBackend()
```

### 测试PPT渲染
```javascript
testPPTRender()
```

---

## 📊 常见错误速查表

| 错误代码 | 原因 | 快速解决方案 |
|---------|------|-------------|
| 422 | 请求体格式错误 | 运行 `fixSlideData(slides)` |
| 401 | 未授权 | 重新登录 |
| 500 | 服务器错误 | 检查后端日志 |
| 504 | 网关超时 | 增加超时时间 |
| Network Error | 后端未启动 | 启动后端服务 |

---

## 🛠️ 手动修复步骤

### 问题1：422错误

**原因：** 请求体格式不正确

**解决：**
```javascript
// 1. 检查幻灯片数据
console.log(slides)

// 2. 修复数据格式
const fixedSlides = fixSlideData(slides)

// 3. 重新测试
testPreview(fixedSlides, "测试课件")
```

### 问题2：401错误

**原因：** Token过期或无效

**解决：**
```javascript
// 1. 清除旧token
localStorage.removeItem('auth_token')

// 2. 重新登录
// 在界面上点击登录按钮

// 3. 验证token
console.log(localStorage.getItem('auth_token'))
```

### 问题3：网络错误

**原因：** 后端服务未启动

**解决：**
```bash
# 启动后端服务
cd backend
python main.py

# 或使用uvicorn
uvicorn main:app --reload --port 8000
```

### 问题4：超时错误

**原因：** 渲染时间过长

**解决：**
```typescript
// 在 src/services/api.ts 中修改
const RENDER_TIMEOUT = 300000; // 改为5分钟
```

---

## 📱 实时监控

### 监控渲染性能
```javascript
// 在控制台运行
const startTime = Date.now();
testPPTRender().then(() => {
  console.log(`渲染耗时: ${Date.now() - startTime}ms`);
});
```

### 监控网络请求
在开发者工具的 Network 标签页中：
1. 筛选 `preview` 请求
2. 查看 Timing 标签
3. 关注 Waiting (TTFB) 时间

---

## 🎯 完整诊断流程

```
开始
  ↓
运行 runDiagnostics()
  ↓
查看诊断结果
  ↓
┌─────────────┐
│ 认证问题？   │ → 重新登录
└─────────────┘
  ↓
┌─────────────┐
│ 后端问题？   │ → 启动后端服务
└─────────────┘
  ↓
┌─────────────┐
│ 数据问题？   │ → 运行 fixSlideData()
└─────────────┘
  ↓
┌─────────────┐
│ 渲染问题？   │ → 查看详细错误日志
└─────────────┘
  ↓
运行 testPPTRender()
  ↓
成功？ → 完成
失败？ → 查看后端日志
```

---

## 💡 预防措施

### 1. 定期检查
```javascript
// 每次渲染前运行
runDiagnostics()
```

### 2. 数据验证
```javascript
// 验证幻灯片格式
slides.forEach((slide, i) => {
  if (!slide.title) console.warn(`幻灯片${i+1}缺少标题`);
  if (!slide.content) console.warn(`幻灯片${i+1}缺少内容`);
});
```

### 3. 错误处理
```javascript
try {
  await testPPTRender();
} catch (error) {
  console.error('渲染失败:', error);
  // 自动运行诊断
  runDiagnostics();
}
```

---

## 📞 获取帮助

如果以上方法都无法解决，请提供：

1. **诊断结果**
```javascript
runDiagnostics()
// 复制控制台输出
```

2. **错误详情**
```javascript
testPPTRender()
// 复制错误信息
```

3. **环境信息**
- 操作系统
- 浏览器版本
- Node.js版本

---

## 🔗 相关文档

- [完整排查指南](./PPT_RENDER_TROUBLESHOOTING.md)
- [API错误处理](./src/utils/errorUtils.ts)
- [请求管理器](./src/utils/requestManager.ts)

---

## ✅ 成功标志

当看到以下输出时，表示问题已解决：

```
✅ [认证] 已登录
✅ [后端连接] 后端服务正常
✅ [幻灯片数据] 找到 X 张幻灯片，X 张有效
✅ [网络延迟] 响应时间: Xms
✅ [PPT渲染测试] 渲染成功
```

---

## 🎉 快速命令汇总

```javascript
// 诊断
runDiagnostics()          // 完整诊断

// 修复
quickFix()               // 一键修复
fixSlideData(slides)     // 修复数据

// 测试
testBackend()            // 测试后端
testPPTRender()          // 测试渲染

// 监控
console.log(slides)      // 查看数据
console.log(localStorage.getItem('auth_token'))  // 查看token
```

---

**记住：遇到问题先运行 `quickFix()`！** 🚀
