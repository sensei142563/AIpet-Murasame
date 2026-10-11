# -*- coding: utf-8 -*-
"""生成 dev/热点连接.bat（GBK+CRLF，无括号块）+ 立刻跑一遍 hotspot_ready.py 记录输出。"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
BAT = os.path.join(MAIN, "dev", "热点连接.bat")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

BODY = """@echo off
setlocal
chcp 936 >nul
title AIpet 热点连接（手机开热点 - 电脑连上 - 打通链路）

set ADB=E:\\Android\\SDK\\platform-tools\\adb.exe
set PY=C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python310\\python.exe
set REPO=E:\\university\\order\\python\\pet\\AIpet-Murasame-main

echo ============================================================
echo  AIpet 热点连接
echo  顺序：手机先开热点 到 电脑连上该热点 到 再跑本脚本
echo ============================================================
echo.

if not exist "%PY%" goto NOPY
if not exist "%REPO%\\dev\\scripts\\hotspot_ready.py" goto NOHELPER

echo [1/4] 放行防火墙端口 28565 与 9881（会弹 UAC，请点 是）
netsh advfirewall firewall add rule name="AIpet 28565" dir=in action=allow protocol=TCP localport=28565 >nul 2>&1
netsh advfirewall firewall add rule name="AIpet 9881" dir=in action=allow protocol=TCP localport=9881 >nul 2>&1
echo      已尝试放行（没弹 UAC 说明不是管理员，可右键本脚本以管理员身份运行）
echo.

echo [2/4] 探测本机局域网地址 与 三个服务端口
"%PY%" "%REPO%\\dev\\scripts\\hotspot_ready.py"
echo.

echo [3/4] 尝试无线 adb：自动用默认网关（热点下网关就是手机）建立反向转发
echo      这样手机 App 里的 127.0.0.1 地址完全不用改
set GW=
for /f "tokens=1" %%g in ('powershell -NoProfile -Command "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 ^| Sort-Object RouteMetric ^| Select-Object -First 1).NextHop"') do set GW=%%g
if "%GW%"=="" goto NOGW
echo      识别到网关（手机热点地址）：%GW%
"%ADB%" connect %GW%:5555
"%ADB%" -s %GW%:5555 reverse tcp:28565 tcp:28565
"%ADB%" -s %GW%:5555 reverse tcp:9881 tcp:9881
echo      ---- 当前转发 ----
"%ADB%" -s %GW%:5555 reverse --list
goto DONE

:NOGW
echo      没识别到默认网关，跳过无线 adb
goto DONE

:DONE
echo.
echo [4/4] 若上面无线 adb 没成功，改用直连方式（在手机 App 设置里改两处地址）：
echo         Jev 电脑地址   = http://电脑局域网IP:28565
echo         语音服务地址   = http://电脑局域网IP:9881
echo      电脑局域网IP 见上面第 2 步打印（热点下通常是 192.168.43.x 里的那个）
echo.
pause
exit /b 0

:NOPY
echo [x] 找不到 python: %PY%
pause
exit /b 1

:NOHELPER
echo [x] 找不到 %REPO%\\dev\\scripts\\hotspot_ready.py
pause
exit /b 1
"""

io.open(BAT, "w", encoding="gbk", newline="").write(
    BODY.replace("\r\n", "\n").replace("\n", "\r\n"))
raw = io.open(BAT, "rb").read()
print("✓ 已写 dev\\热点连接.bat  %d B，双 CR = %s（应为 False）" % (len(raw), b"\r\r" in raw))

print()
print("=== 立刻跑一遍 hotspot_ready.py（这就是脚本第 2 步会打印的内容）===")
r = subprocess.run([PY, "-u", os.path.join(MAIN, "dev", "scripts", "hotspot_ready.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   cwd=MAIN, timeout=600)
for l in (r.stdout or r.stderr).splitlines():
    print("   " + l)
