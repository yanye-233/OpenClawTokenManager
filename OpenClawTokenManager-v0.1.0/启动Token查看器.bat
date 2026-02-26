@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查 requests
python -c "import requests" 2>nul
if errorlevel 1 (
    echo [提示] 安装 requests...
    pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
)

set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8

REM 使用 start 启动，不显示 CMD 窗口
start "" pythonw "OpenClawTokenViewer.py"
