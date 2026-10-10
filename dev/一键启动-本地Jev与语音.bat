@echo off
chcp 65001 >nul
setlocal
title AIpet Jev 一键启动（本地判断 + 语音）

set REPO=E:\university\order\python\pet\AIpet-Murasame-main
set NANO=E:\university\order\python\pet\_audit_fish9269\repros\NanoJev
set ADB=E:\Android\SDK\platform-tools\adb.exe
set AUD=E:\university\order\python\pet\_audit_fish9269

echo ==========================================================
echo  AIpet 本地 Jev + 语音 一键启动
echo ==========================================================
echo  会依次启动三样东西：
echo    1) NanoJev 本地判断模型   (127.0.0.1:8765)   ← 真正做"选择题"的模型
echo    2) F5-TTS 语音合成        (127.0.0.1:9881)   ← 丛雨/诺瓦 音色
echo    3) api.py 电脑端接口      (0.0.0.0:28565)    ← 手机调用的入口（内含 /jev/choose）
echo  然后建立手机到电脑的 USB 反向转发（28565 与 9881）
echo ==========================================================
echo.

echo [1/4] 启动 NanoJev（8765）...
start "NanoJev-8765" /min cmd /c "cd /d %NANO% && python -u scripts\serve_decisions.py --checkpoint-dir checkpoints\NanoJev-unified --web-root web --port 8765 --precision bf16 > %AUD%\_nanojev_bat.log 2>&1"

echo [2/4] 启动 F5-TTS（9881）...
start "F5TTS-9881" /min cmd /c "cd /d %REPO% && python -u -m longtext.f5tts_server > %AUD%\_f5_bat.log 2>&1"

echo [3/4] 启动 api.py（28565，含 /jev/choose）...
echo         注意：必须带上 TYPESAFE_BASE_URL，否则 /jev/choose 会说 "no key"
start "api-28565" /min cmd /c "cd /d %REPO% && set TYPESAFE_BASE_URL=http://127.0.0.1:8765/api/evaluate && python -u -m uvicorn api:app --host 0.0.0.0 --port 28565 > %AUD%\_api_bat.log 2>&1"

echo [4/4] 等待服务就绪 ...
timeout /t 30 /nobreak >nul

echo     探测端口 ...
netstat -ano | findstr ":8765" | findstr LISTENING
netstat -ano | findstr ":9881" | findstr LISTENING
netstat -ano | findstr ":28565" | findstr LISTENING

echo.
echo     建立 USB 反向转发（手机用 127.0.0.1 访问电脑）...
"%ADB%" reverse tcp:28565 tcp:28565
"%ADB%" reverse tcp:9881  tcp:9881
"%ADB%" reverse --list

echo.
echo ==========================================================
echo  启动完成。手机端设置里应填：
echo     Jev 电脑地址  = http://127.0.0.1:28565
echo     语音服务地址  = http://127.0.0.1:9881
echo.
echo  怎么确认"Jev 真的被用上了"：
echo     看 %AUD%\_api_bat.log        里是否有  POST /jev/choose   （手机来调）
echo     看 %AUD%\_nanojev_bat.log    里是否有  POST /api/evaluate （本地模型在算）
echo     浏览器打开 http://127.0.0.1:8765/api/health 应看到
echo         {"ready": true, ..., "provider_calls": 0}   ← 0 = 全程本地、没调任何云服务
echo ==========================================================
pause
