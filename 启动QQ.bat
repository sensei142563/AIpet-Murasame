@echo off
chcp 65001 >nul
title QQ AIpet - 丛雨 QQ 聊天模块
setlocal
cd /d "%~dp0"

rem 优先使用项目虚拟环境，否则回退系统 Python
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    set "PYTHON_CMD=%VENV_PYTHON%"
) else (
    set "PYTHON_CMD=python"
)

echo 使用 Python: %PYTHON_CMD%
echo 提示：请确保 NapCat 已启动（首次使用请先运行 start_napcat.bat 扫码登录）
"%PYTHON_CMD%" run_qq.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。如果是首次使用，请先运行 install.bat
    pause
)