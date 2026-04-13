# 🚀 快速参考卡片

## 一、立即安装依赖

```bash
# Windows用户
.\install-deps.bat

# Mac/Linux用户
bash install-deps.sh

# 或手动安装
npm install react-markdown remark-gfm remark-math rehype-katex katex antd @ant-design/cssinjs
```

## 二、替换Markdown组件

### ❌ 旧代码（会报错）
```tsx
<ReactMarkdown>{content}</ReactMarkdown>
```

### ✅ 新代码（已修复）
```tsx
<SafeMarkdown>{content}</SafeMarkdown>
```

## 三、导入语句

```tsx
// 在文件顶部添加
import SafeMarkdown from './components/common/SafeMarkdown';
```

## 四、支持的内容类型

| 类型 | 示例 | 处理方式 |
|------|------|----------|
| 字符串 | `"文本"` | 直接渲染 |
| 数组 | `["段落1", "段落2"]` | 用换行连接 |
| 对象 | `{text: "内容"}` | JSON序列化 |
| null/undefined | `null` | 显示空字符串 |

## 五、常见问题解决

### 问题1：仍然看到类型错误
**解决：** 确保所有`<ReactMarkdown>`都替换为`<SafeMarkdown>`

### 问题2：Antd警告仍存在
**解决：**
```bash
npm install antd @ant-design/cssinjs
npm run dev  # 重启服务器
```

### 问题3：样式不正确
**解决：**
```tsx
<SafeMarkdown proseClass="prose prose-lg">
  {content}
</SafeMarkdown>
```

## 六、高级用法

### 自定义样式
```tsx
<SafeMarkdown
  className="my-custom-class"
  proseClass="prose prose-xl prose-green"
>
  {content}
</SafeMarkdown>
```

### 处理AI文本
```tsx
import { processAIText } from './utils/textUtils';

const processed = processAIText(aiGeneratedText);
<SafeMarkdown>{processed}</SafeMarkdown>
```

### 提取关键点
```tsx
import { extractKeyPoints } from './utils/textUtils';

const points = extractKeyPoints(text);
// 返回: ["要点1", "要点2", "要点3"]
```

## 七、文件清单

| 文件 | 用途 |
|------|------|
| `SafeMarkdown.tsx` | 安全的Markdown组件 |
| `textUtils.ts` | 文本处理工具 |
| `ErrorBoundary.tsx` | 错误边界组件 |
| `ThemeProvider.tsx` | Antd主题配置 |
| `install-deps.bat/sh` | 依赖安装脚本 |

## 八、验证步骤

1. ✅ 安装依赖
2. ✅ 替换组件
3. ✅ 重启服务器
4. ✅ 清除浏览器缓存
5. ✅ 检查控制台无警告

## 九、性能优化

- ✅ 文本处理函数都是纯函数
- ✅ 错误边界防止整个应用崩溃
- ✅ 自动缓存处理结果

## 十、获取帮助

- 📖 完整文档: `MARKDOWN_FIX_GUIDE.md`
- 🧪 测试示例: `src/components/TestMarkdown.tsx`
- 📦 依赖说明: `INSTALL_DEPS.md`
