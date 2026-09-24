@echo off
chcp 65001 >nul
title AIpet 丛雨AI桌宠 - 图形启动器（PCL）
setlocal
cd /d "%~dp0"

rem 优先使用项目虚拟环境，否则回退系统 Python
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    rem venv 完整性探针：启动器只 import PyQt5（不 import torch）→ 只查 PyQt5。
    rem 缺 PyQt5 的 venv 一定是装了一半/装错位置，换成系统 Python 试一次并给指引。
    "%VENV_PYTHON%" -c "import sys,importlib.util as u;sys.exit(0 if u.find_spec('PyQt5') else 1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [警告] 检测到 runtime\venv 里没有 PyQt5。
        echo        可能原因：install.bat 中途失败/中断，或依赖装到了别的 Python。
        echo        处理办法：重新运行 install.bat 修复；或删除 runtime\venv 后改用系统 Python。
        echo        现在改用系统 Python 尝试启动...
        echo.
        set "PYTHON_CMD=python"
    ) else (
        set "PYTHON_CMD=%VENV_PYTHON%"
    )
) else (
    set "PYTHON_CMD=python"
)

echo 使用 Python: %PYTHON_CMD%
"%PYTHON_CMD%" run_launcher.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。如果是首次使用，请先运行 install.bat
    pause
)
