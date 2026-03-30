@echo off
cd /d "%~dp0"
echo 正在启动后端服务...
set PYTHONPATH=%cd%
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause
