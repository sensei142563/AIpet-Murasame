@echo off
setlocal
chcp 936 >nul
title AIpet 本地 Jev + 语音 一键启动

rem ================= 路径（如与实际不符只改这一段）=================
set REPO=E:\university\order\python\pet\AIpet-Murasame-main
set NANOREPO=E:\university\order\python\pet\_audit_fish9269\repros\NanoJev
set ADB=E:\Android\SDK\platform-tools\adb.exe
set PY=C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe
set DEV=4BD9K24C06021770
set LOGDIR=%REPO%\dev\logs
rem ===============================================================

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo ==========================================================
echo   AIpet 本地 Jev + 语音 一键启动
echo ==========================================================
echo   1) NanoJev 本地判断模型  127.0.0.1:8765
echo   2) F5-TTS 语音合成       127.0.0.1:9881
echo   3) api.py 电脑端接口     0.0.0.0:28565  (含 /jev/choose)
echo   日志写到：%LOGDIR%
echo ==========================================================
echo.

if not exist "%PY%" (
  echo [x] 找不到 python: %PY%
  echo     请确认已安装 Python 3.10，或改本脚本里的 PY 变量
  pause
  exit /b 1
)
if not exist "%REPO%\api.py" (
  echo [x] 找不到 %REPO%\api.py
  pause
  exit /b 1
)
if not exist "%NANOREPO%\scripts\serve_decisions.py" (
  echo [x] 找不到 NanoJev 服务脚本
  echo     %NANOREPO%\scripts\serve_decisions.py
  pause
  exit /b 1
)

echo [1/5] 启动 NanoJev (8765) ...
start "NanoJev-8765" /min cmd /c "chcp 65001 >nul && cd /d %NANOREPO% && set PYTHONIOENCODING=utf-8 && %PY% -u scripts\serve_decisions.py --checkpoint-dir checkpoints\NanoJev-unified --web-root web --port 8765 --precision bf16 > %LOGDIR%\nanojev.log 2>&1"

echo [2/5] 启动 F5-TTS (9881) ...
start "F5TTS-9881" /min cmd /c "chcp 65001 >nul && cd /d %REPO% && set PYTHONIOENCODING=utf-8 && %PY% -u longtext\f5tts_server.py > %LOGDIR%\f5tts.log 2>&1"

echo [3/5] 启动 api.py (28565) ...
echo         必须带 TYPESAFE_BASE_URL，否则 /jev/choose 会报 no key
start "api-28565" /min cmd /c "chcp 65001 >nul && cd /d %REPO% && set TYPESAFE_BASE_URL=http://127.0.0.1:8765/api/evaluate && set PYTHONIOENCODING=utf-8 && %PY% -u -m uvicorn api:app --host 0.0.0.0 --port 28565 > %LOGDIR%\api.log 2>&1"

echo [4/5] 等 40 秒让模型加载（NanoJev 首次加载较慢）...
timeout /t 40 /nobreak >nul

echo     端口监听情况（有输出就是起来了）：
netstat -ano | findstr ":8765" | findstr LISTENING
netstat -ano | findstr ":9881" | findstr LISTENING
netstat -ano | findstr ":28565" | findstr LISTENING

echo.
echo [5/5] 建立 USB 反向转发（手机用 127.0.0.1 访问电脑）...
"%ADB%" -s %DEV% reverse --remove-all >nul 2>&1
"%ADB%" -s %DEV% reverse tcp:28565 tcp:28565
"%ADB%" -s %DEV% reverse tcp:9881 tcp:9881
"%ADB%" -s %DEV% reverse --list

echo.
echo ==========================================================
echo  完成。手机端「设置」里填：
echo     Jev 电脑地址  = http://127.0.0.1:28565
echo     语音服务地址  = http://127.0.0.1:9881
echo.
echo  想确认 Jev 真的被用上了：
echo    浏览器打开 http://127.0.0.1:8765/api/health
echo      应看到 {"ready": true, ..., "provider_calls": 0}
echo      provider_calls = 0 意思是全程本地、没调任何云服务
echo    或双击运行 dev\看日志-开三个窗口.bat 看实时日志
echo ==========================================================
echo.
echo  注意：本窗口可以关；关掉不影响已启动的服务。
pause
