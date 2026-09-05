@echo off
chcp 65001 >nul
title 微信 ClawBot AIpet - 启动器
setlocal
cd /d "%~dp0"

rem 优先使用项目虚拟环境，否则回退系统 Python
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    rem venv 完整性探针：目录在 ≠ 依赖齐。装到一半/装错位置的 venv 会架空
    rem 已装好库的系统 Python（例：venv 缺 requests/Crypto → 微信 iLink 启动即崩）。
    rem find_spec 只查不导入，毫秒级，不触发 DLL 加载。
    "%VENV_PYTHON%" -c "import sys,importlib.util as u;sys.exit(0 if u.find_spec('requests') and u.find_spec('Crypto') and u.find_spec('qrcode') else 1)" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [警告] 检测到 runtime\venv 存在但不完整（缺少核心库 requests/Crypto/qrcode）。
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
echo 提示：首次运行需扫码登录（二维码会自动打开，微信「我-设置-插件」需开启 ClawBot）
"%PYTHON_CMD%" run_wechat.py
if errorlevel 1 (
    echo.
    echo [错误] 启动失败。如果是首次使用，请先运行 install.bat
    pause
)
