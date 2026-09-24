@echo off
chcp 65001 >nul
title AIpet 长文本模式 - 一键清理重启
setlocal
cd /d "%~dp0"

rem 优先使用项目虚拟环境，否则回退系统 Python
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    rem venv 完整性探针：目录在 ≠ 依赖齐。装到一半/装错位置的 venv 会架空
    rem 已装好库的系统 Python（例：venv 缺 PyQt5/torch → 桌宠启动即崩）。
    rem find_spec 只查不导入，毫秒级，不触发 DLL 加载。
    "%VENV_PYTHON%" -c "import sys,importlib.util as u;sys.exit(0 if u.find_spec('PyQt5') and u.find_spec('torch') else 1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [警告] 检测到 runtime\venv 存在但不完整（缺少核心库 PyQt5/torch）。
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
