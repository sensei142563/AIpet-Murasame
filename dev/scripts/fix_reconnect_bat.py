# -*- coding: utf-8 -*-
"""诊断并重写「重连」bat：改成无括号块的平铺写法（goto 标签），GBK+CRLF，然后实测运行。"""
import glob
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"

hits = [p for p in glob.glob(os.path.join(DEV, "*重连*.bat")) + glob.glob(os.path.join(DEV, "*连电脑*.bat"))]
if not hits:
    print("✗ 没找到重连 bat")
    sys.exit(1)
bat = hits[0]
print("=== 找到：%s ===" % os.path.basename(bat))

raw = io.open(bat, "rb").read()
print("前 12 字节:", " ".join("%02X" % x for x in raw[:12]),
      "（末尾应为 0D 0A，非 0D 0D 0A）")
old = raw.decode("gbk", errors="replace")
print()
print("=== 旧内容里在括号块中出现 ')' 的 echo 行（这就是崩掉的原因）===")
inblock = 0
for i, line in enumerate(old.splitlines(), 1):
    s = line.strip()
    if s.startswith("if ") and "(" in s:
        inblock = 1
    if inblock and s.lower().startswith("echo") and ")" in s:
        print("   第 %d 行: %s" % (i, s[:100]))
    if inblock and s == ")":
        inblock = 0

NEW = """@echo off
setlocal
title AIpet 手机 连 电脑 重连

set ADB=E:\\Android\\SDK\\platform-tools\\adb.exe
set DEV=4BD9K24C06021770

echo ============================================
echo  AIpet-Murasame  手机 连 电脑  重连
echo  USB 反向端口转发：绕开校园网客户端隔离
echo ============================================
echo.

if not exist "%ADB%" goto NOADB

echo [1/4] 检查设备 ...
"%ADB%" -s %DEV% get-state >nul 2>&1
if not errorlevel 1 goto HAVE_DEV
echo     用序列号 %DEV% 连不上，改试默认设备 ...
"%ADB%" get-state >nul 2>&1
if not errorlevel 1 goto HAVE_DEFAULT
echo.
echo [x] 手机未连接。请确认：
echo     1. USB 线插好
echo     2. 手机已开启 开发者选项 - USB 调试
echo     3. 手机上弹出的 允许 USB 调试 已点允许
goto ENDPAUSE

:HAVE_DEV
echo     设备在线: %DEV%
echo [2/4] 清理旧转发 ...
"%ADB%" -s %DEV% reverse --remove-all >nul 2>&1
echo [3/4] 建立转发 28565 Jev 与 9881 语音 ...
"%ADB%" -s %DEV% reverse tcp:28565 tcp:28565
"%ADB%" -s %DEV% reverse tcp:9881 tcp:9881
echo [4/4] 当前转发列表：
"%ADB%" -s %DEV% reverse --list
goto DONE

:HAVE_DEFAULT
echo     设备在线: 默认设备
echo [2/4] 清理旧转发 ...
"%ADB%" reverse --remove-all >nul 2>&1
echo [3/4] 建立转发 28565 Jev 与 9881 语音 ...
"%ADB%" reverse tcp:28565 tcp:28565
"%ADB%" reverse tcp:9881 tcp:9881
echo [4/4] 当前转发列表：
"%ADB%" reverse --list
goto DONE

:NOADB
echo [x] 找不到 adb: %ADB%
goto ENDPAUSE

:DONE
echo.
echo 完成。手机端 设置 里填：
echo    Jev 电脑地址   = http://127.0.0.1:28565
echo    语音服务地址   = http://127.0.0.1:9881
echo.
echo 提示：拔线、重启手机、重启电脑后都要重新运行本脚本。
echo.

:ENDPAUSE
pause
"""

io.open(bat, "w", encoding="gbk", newline="").write(
    NEW.replace("\r\n", "\n").replace("\n", "\r\n"))
raw2 = io.open(bat, "rb").read()
print()
print("=== 新文件 ===")
print("   %s  %d B" % (os.path.basename(bat), len(raw2)))
print("   前 12 字节:", " ".join("%02X" % x for x in raw2[:12]))
bad_cr = b"\r\r" in raw2
print("   行尾:", "✗ 有双 CR" if bad_cr else "✓ 单个 CRLF")
txt = raw2.decode("gbk", errors="replace")
print("   含括号块:", "(" in txt.replace("(x)", ""), "（应为 False）")
print("   前 6 行 GBK 解码:")
for l in txt.split("\r\n")[:6]:
    print("      " + l)

print()
print("=== 实测运行（stdin 接空，pause 会自动跳过；模拟双击）===")
r = subprocess.run(["cmd", "/c", bat], stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
out = (r.stdout or b"").decode("gbk", errors="replace")
err = (r.stderr or b"").decode("gbk", errors="replace")
for l in (out + err).splitlines():
    if l.strip():
        print("   | " + l[:150])
print("   rc =", r.returncode)
