@echo off
chcp 65001 >nul
title AIpet 丛雨AI桌宠 - 首次安装
setlocal
cd /d "%~dp0"

echo ============================================
echo    AIpet 丛雨AI桌宠 - 首次安装引导
echo ============================================
echo.

rem ---------- 1. 查找 Python ----------
set "PYTHON_CMD="
where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD goto :no_python

rem ---------- 2. 检查 Python 版本 -------
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :low_python

echo [1/5] Python 版本检查通过
%PYTHON_CMD% --version

rem ---------- 3. 创建虚拟环境 ----------
set "VENV_PYTHON=%~dp0runtime\venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" (
    echo [2/5] 虚拟环境已存在，跳过创建
) else (
    echo [2/5] 创建项目虚拟环境 runtime\venv ...
    %PYTHON_CMD% -m venv "%~dp0runtime\venv"
    if errorlevel 1 goto :venv_fail
    echo        虚拟环境创建成功
)

rem ---------- 4. 安装依赖 ----------
echo [3/5] 安装基础依赖（首次约 10-20 分钟，请耐心等待）...
"%VENV_PYTHON%" -m pip install --upgrade pip >nul 2>&1
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :install_fail
echo        基础依赖安装完成

echo [4/5] 安装 CPU 版 PyTorch（云端对话也必需）...
"%VENV_PYTHON%" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :install_fail
echo        PyTorch 安装完成

rem ---------- 4.5 修 MSVC 运行时冲突（桌宠"卡退"的根因）----------
rem PyQt5-Qt5 5.15.2 的 Qt5\bin 自带一套 14.26（VS2017）的 msvcp140/vcruntime140…，
rem 而 torch ≥2.x 的 c10.dll 需要更新的运行时：先 import PyQt5 再 import torch 时，
rem c10.dll 初始化失败（WinError 1114 / 0xC0000005，事件日志里崩在 MSVCP140.dll）。
rem 桌宠正好是"Qt + torch 同进程" → 必崩、且没有 traceback。
rem 修法：把那几个**旧于系统**的文件改名让位（只动比系统旧的，幂等、可回滚）。
echo [4.5/5] 检查 MSVC 运行时冲突（PyQt5 自带旧版会让 torch 起不来）...
"%VENV_PYTHON%" -c "from tool.msvc_runtime import fix_if_needed as f; f(log=lambda m: print('        ' + m))"

rem ---------- 5. 生成 config.json ----------
if exist "config.json" (
    echo [5/5] config.json 已存在，跳过
) else (
    echo [5/5] 生成 config.json ...
    copy /y "config.example.json" "config.json" >nul
    echo        已生成 config.json
    echo.
    echo        ⚠ 请用记事本打开 config.json 填写：
    echo           - APIKEY.deepseek （DeepSeek 密钥）
    echo           - APIKEY.qwen     （通义千问密钥）
    echo           - user_name       （你的名字）
    echo        然后保存，再运行「启动桌宠.bat」
)

echo.
echo ============================================
echo    安装完成！接下来：
echo    1. 编辑 config.json 填入 API Key（如已填可跳过）
echo    2. 双击「启动桌宠.bat」开始使用
echo    3. F5-TTS 语音为可选功能，见 README
echo ============================================
echo.
pause
exit /b 0

:no_python
echo [错误] 未找到 Python！
echo   请先安装 Python 3.10 或更高版本：https://www.python.org/downloads/
echo   安装时务必勾选 "Add Python to PATH"
pause
exit /b 1

:low_python
echo [错误] Python 版本过低（需要 3.10+）
%PYTHON_CMD% --version
pause
exit /b 1

:venv_fail
echo [错误] 虚拟环境创建失败
pause
exit /b 1

:install_fail
echo [错误] 依赖安装失败！请检查网络后重试
pause
exit /b 1