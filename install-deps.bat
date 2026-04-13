@echo off
echo 🚀 开始安装所有依赖...

echo 📦 安装Markdown相关依赖...
call npm install react-markdown remark-gfm remark-math rehype-katex katex

echo 📦 安装Antd相关依赖...
call npm install antd @ant-design/cssinjs

echo 📦 安装其他必要依赖...
call npm install lucide-react motion clsx tailwind-merge

echo ✅ 所有依赖安装完成！
echo.
echo 📝 接下来请：
echo 1. 重启开发服务器: npm run dev
echo 2. 清除浏览器缓存
echo 3. 检查控制台是否还有警告
echo.
echo 🎉 完成！
pause
