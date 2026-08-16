@echo off
chcp 65001 >nul
title 微信 ClawBot AIpet - 启动器
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
echo 提示：首次运行需扫码登录（二维码会自动打开，微信「我-设置-插件」需开启 ClawBot）
"%PYTHON_CMD%" run_wechat.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。如果是首次使用，请先运行 install.bat
    pause
)
