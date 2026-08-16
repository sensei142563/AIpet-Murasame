@echo off
chcp 65001 >nul
title AIpet 丛雨AI桌宠 - 启动器
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
"%PYTHON_CMD%" run.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。如果是首次使用，请先运行 install.bat
    pause
)