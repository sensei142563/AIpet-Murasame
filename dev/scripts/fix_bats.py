# -*- coding: utf-8 -*-
"""重写两个 bat（GBK + CRLF + python 绝对路径 + 日志落盘）+ 新增「看日志」bat；写前逐项校验路径。"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = r"E:\university\order\python\pet\AIpet-Murasame-main"
DEV = os.path.join(REPO, "dev")
NANOREPO = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev"
AUD = r"E:\university\order\python\pet\_audit_fish9269"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
DEV_SERIAL = "4BD9K24C06021770"

print("=== 写之前逐项校验 ===")
checks = {
    "repo": REPO,
    "NanoJev 目录": NANOREPO,
    "NanoJev 服务脚本": os.path.join(NANOREPO, "scripts", "serve_decisions.py"),
    "NanoJev 模型目录": os.path.join(NANOREPO, "checkpoints", "NanoJev-unified"),
    "NanoJev web 目录": os.path.join(NANOREPO, "web"),
    "api.py": os.path.join(REPO, "api.py"),
    "f5tts_server.py": os.path.join(REPO, "longtext", "f5tts_server.py"),
    "adb": ADB,
    "python": PY,
}
bad = []
for k, v in checks.items():
    e = os.path.exists(v)
    print("   %-20s %s  %s" % (k, "[有]" if e else "[无]", v))
    if not e:
        bad.append(k)

# F5 用 -m 还是直接跑文件：看它有没有相对导入
f5 = os.path.join(REPO, "longtext", "f5tts_server.py")
f5_rel = False
if os.path.exists(f5):
    head = io.open(f5, encoding="utf-8", errors="replace").read(6000)
    f5_rel = bool(re.search(r"^\s*from\s+\.", head, re.M))
f5_cmd = ("%PY% -u -m longtext.f5tts_server" if f5_rel
          else "%PY% -u longtext\\f5tts_server.py")
print("   F5 启动方式：", "包形式(-m，因有相对导入)" if f5_rel else "直接跑文件")
if bad:
    print("✗ 以下路径不存在，请先确认：", bad)
    sys.exit(1)

EOL = "\r\n"


def w(name, text):
    p = os.path.join(DEV, name)
    io.open(p, "w", encoding="gbk", newline=EOL).write(text.replace("\n", EOL))
    b = io.open(p, "rb").read(24)
    print("   ✓ %s  %d B  首字节 %s" % (name, os.path.getsize(p),
          " ".join("%02X" % x for x in b[:12])))
    return p


BAT1 = """@echo off
setlocal
title AIpet 本地 Jev + 语音 一键启动

rem ================= 路径（如与实际不符只改这一段）=================
set REPO=E:\\university\\order\\python\\pet\\AIpet-Murasame-main
set NANOREPO=E:\\university\\order\\python\\pet\\_audit_fish9269\\repros\\NanoJev
set ADB=E:\\Android\\SDK\\platform-tools\\adb.exe
set PY=C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe
set DEV=4BD9K24C06021770
set LOGDIR=%REPO%\\dev\\logs
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
if not exist "%REPO%\\api.py" (
  echo [x] 找不到 %REPO%\\api.py
  pause
  exit /b 1
)
if not exist "%NANOREPO%\\scripts\\serve_decisions.py" (
  echo [x] 找不到 NanoJev 服务脚本
  echo     %NANOREPO%\\scripts\\serve_decisions.py
  pause
  exit /b 1
)

echo [1/5] 启动 NanoJev (8765) ...
start "NanoJev-8765" /min cmd /c "cd /d %NANOREPO% && %PY% -u scripts\\serve_decisions.py --checkpoint-dir checkpoints\\NanoJev-unified --web-root web --port 8765 --precision bf16 > %LOGDIR%\\nanojev.log 2>&1"

echo [2/5] 启动 F5-TTS (9881) ...
start "F5TTS-9881" /min cmd /c "cd /d %REPO% && %PY% -u F5CMD > %LOGDIR%\\f5tts.log 2>&1"

echo [3/5] 启动 api.py (28565) ...
echo         必须带 TYPESAFE_BASE_URL，否则 /jev/choose 会报 no key
start "api-28565" /min cmd /c "cd /d %REPO% && set TYPESAFE_BASE_URL=http://127.0.0.1:8765/api/evaluate && %PY% -u -m uvicorn api:app --host 0.0.0.0 --port 28565 > %LOGDIR%\\api.log 2>&1"

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
echo    或双击运行 dev\\看日志-开三个窗口.bat 看实时日志
echo ==========================================================
echo.
echo  注意：本窗口可以关；关掉不影响已启动的服务。
pause
"""

BAT2 = """@echo off
setlocal
title AIpet 手机 连 电脑 一键重连

set ADB=E:\\Android\\SDK\\platform-tools\\adb.exe
set DEV=4BD9K24C06021770

echo ============================================
echo  AIpet-Murasame  手机 连 电脑  一键重连
echo  (USB 反向端口转发：绕开校园网客户端隔离)
echo ============================================
echo.

if not exist "%ADB%" (
  echo [x] 找不到 adb: %ADB%
  pause
  exit /b 1
)

echo [1/4] 检查设备 ...
"%ADB%" -s %DEV% get-state >nul 2>&1
if errorlevel 1 (
  echo     指定序列号 %DEV% 连不上，试默认设备 ...
  "%ADB%" get-state >nul 2>&1
  if errorlevel 1 (
    echo.
    echo [x] 手机未连接。请确认：
    echo      1) USB 线插好
    echo      2) 手机已开启「开发者选项 - USB 调试」
    echo      3) 手机弹出的「允许 USB 调试」已点允许
    pause
    exit /b 1
  )
  set DEVP=
) else (
  set DEVP=-s %DEV%
)

echo [2/4] 清理旧转发 ...
"%ADB%" %DEVP% reverse --remove-all >nul 2>&1

echo [3/4] 建立转发 28565(Jev) 与 9881(语音) ...
"%ADB%" %DEVP% reverse tcp:28565 tcp:28565
"%ADB%" %DEVP% reverse tcp:9881 tcp:9881

echo [4/4] 当前转发列表：
"%ADB%" %DEVP% reverse --list

echo.
echo 完成。手机端「设置」里填：
echo    Jev 电脑地址   = http://127.0.0.1:28565
echo    语音服务地址   = http://127.0.0.1:9881
echo.
echo 提示：拔线、重启手机、重启电脑后都要重新运行本脚本。
echo.
pause
"""

BAT3 = """@echo off
setlocal
title AIpet 实时日志（三个窗口）

set LOGDIR=E:\\university\\order\\python\\pet\\AIpet-Murasame-main\\dev\\logs
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
if not exist "%LOGDIR%\\api.log" echo (等待服务写入...) > "%LOGDIR%\\api.log"
if not exist "%LOGDIR%\\nanojev.log" echo (等待服务写入...) > "%LOGDIR%\\nanojev.log"
if not exist "%LOGDIR%\\f5tts.log" echo (等待服务写入...) > "%LOGDIR%\\f5tts.log"

echo 正在打开三个实时日志窗口（api=手机来的请求 / nanojev=本地模型在算 / f5tts=语音合成）
start "日志-api(手机请求)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 %LOGDIR%\\api.log
start "日志-nanojev(本地模型)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 %LOGDIR%\\nanojev.log
start "日志-f5tts(语音)" cmd /k powershell -NoExit -Command Get-Content -Wait -Tail 30 %LOGDIR%\\f5tts.log
echo 已打开。关掉这些窗口不影响服务。
timeout /t 3 /nobreak >nul
"""

print()
print("=== 写入（GBK + CRLF）===")
BAT1 = BAT1.replace("F5CMD", f5_cmd.replace("%PY% ", "").strip())
w("一键启动-本地Jev与语音.bat", BAT1)
w("手机连电脑-一键重连.bat", BAT2)
w("看日志-开三个窗口.bat", BAT3)
print()
print("✓ 三个 bat 已写好（GBK 编码 + CRLF 换行，python 用绝对路径）")
