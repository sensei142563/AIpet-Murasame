@echo off
setlocal
chcp 65001 >nul
title AIpet 实时日志（三个窗口）

set LOGDIR=E:\university\order\python\pet\AIpet-Murasame-main\dev\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%LOGDIR%\api.log" echo (等待服务写入...) > "%LOGDIR%\api.log"
if not exist "%LOGDIR%\nanojev.log" echo (等待服务写入...) > "%LOGDIR%\nanojev.log"
if not exist "%LOGDIR%\f5tts.log" echo (等待服务写入...) > "%LOGDIR%\f5tts.log"

echo 正在打开三个实时日志窗口（api=手机来的请求 / nanojev=本地模型在算 / f5tts=语音合成）
start "日志-api(手机请求)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 -Encoding UTF8 %LOGDIR%\api.log
start "日志-nanojev(本地模型)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 -Encoding UTF8 %LOGDIR%\nanojev.log
start "日志-f5tts(语音)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 -Encoding UTF8 %LOGDIR%\f5tts.log
echo 已打开。关掉这些窗口不影响服务。
timeout /t 3 /nobreak >nul
