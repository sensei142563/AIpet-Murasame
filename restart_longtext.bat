@echo off
chcp 65001 >nul
title AIpet 长文本模式 - 一键清理重启
setlocal
cd /d "%~dp0"

rem 优先使用项目虚拟环境，否则回退系统 Python
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    set "PYTHON_CMD=python"
)

echo ============================================
echo   AIpet 长文本模式 - 一键清理重启
echo ============================================
echo.

echo [1/3] 关闭旧进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *F5-TTS*" >nul 2>&1
timeout /t 1 /nobreak >nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *AIpet*" >nul 2>&1
timeout /t 1 /nobreak >nul

echo [2/3] 清理 __pycache__ 缓存...
"%PYTHON_CMD%" -c "import shutil, glob; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True) if 'site-packages' not in p and '.venv' not in p]"
echo     缓存清理完成

echo [3/3] 启动 AIpet ...
echo.
"%PYTHON_CMD%" run.py

pause
