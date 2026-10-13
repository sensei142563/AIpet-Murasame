# -*- coding: utf-8 -*-
"""按 run.py 的方式（新控制台 + BELOW_NORMAL）再验一次，并截图那个窗口。
   目的：确认不是偶发；顺带拿到"新窗口长什么样"的证据。
"""
import io
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
GSV = os.path.join(ROOT, "GPT-SoVITS")
PY = os.path.join(GSV, "runtime", "python.exe")
WRAP = os.path.join(ROOT, "tool", "tts_console.py")
CFG = os.path.join(ROOT, "data", "tts_console.json")
LOG = os.path.join(ROOT, "data", "tts_service.log")
MYPID = str(os.getpid())

# 把日志清空（便于判断"这一次"写了什么）
try:
    os.remove(LOG)
except Exception:
    pass


def port():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-NetTCPConnection -LocalPort 9880 -State Listen "
                        "-ErrorAction SilentlyContinue | Measure-Object).Count"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    return (r.stdout or "").strip()


def pyprocs():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    return [l.strip() for l in (r.stdout or "").split("\n")
            if l.strip() and "|" in l and MYPID not in l.split("|")[0]]


print("=== 正式复验：完全按 run.py 的方式启动 ===")
flags = 0x00000010 | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
p = subprocess.Popen([PY, WRAP, CFG, "--", "api.py",
                      "-s", "SoVITS_weights/murasame-sovits.pth",
                      "-g", "GPT_weights/murasame-gpt.ckpt"],
                     cwd=GSV, creationflags=flags)
print("   外壳 PID =", p.pid)
for i in range(12):
    time.sleep(5)
    if port() == "1":
        print("   第 %d 秒：9880 已监听 ✓" % ((i + 1) * 5))
        break
    if p.poll() is not None:
        print("   ✗ 外壳第 %d 秒就退出了（退出码 %s）" % ((i + 1) * 5, p.returncode))
        break

print("   9880 监听数 =", port(), " | 外壳存活 =", "是" if p.poll() is None else "否")
print()
print("=== 进程树 ===")
for l in pyprocs():
    print("   ", l[:120])

print()
print("=== 日志（这次）===")
if os.path.isfile(LOG):
    ls = [x for x in io.open(LOG, encoding="utf-8", errors="replace").read().split("\n") if x.strip()]
    print("   共 %d 行" % len(ls))
    for x in ls[:12]:
        print("   >", x[:112])
else:
    print("   ✗ 没有日志（外壳没起来）")

print()
print("=== 窗口截图（整个桌面，找那个标题为『AIpet 语音服务』的窗口）===")
shot = subprocess.run(["powershell", "-NoProfile", "-Command",
                       "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                       "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
                       "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
                       "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                       "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
                       "$out='E:\\university\\order\\python\\pet\\AIpet-Murasame-main\\dev\\ppt\\out\\tts-console-shot.png';"
                       "$bmp.Save($out,[System.Drawing.Imaging.ImageFormat]::Png);"
                       "Write-Output $out"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                      timeout=300)
print("   ", (shot.stdout or "").strip().split("\n")[-1])

print()
print("=== 窗口标题列表 ===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
                    "Select-Object -ExpandProperty MainWindowTitle"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
for l in (r.stdout or "").split("\n"):
    l = l.strip()
    if l:
        print("   |", l[:96], "  ←★" if "语音服务" in l else "")

print()
print("=== 收工：/T 杀掉外壳，查残留 ===")
subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
time.sleep(5)
left = pyprocs()
print("   残留 python：%d 个 %s" % (len(left), "（干净 ✓）" if not left else "✗"))
for l in left:
    print("   !", l[:118])
print("   9880 监听数 =", port())
print("   日志末尾：")
if os.path.isfile(LOG):
    ls = [x for x in io.open(LOG, encoding="utf-8", errors="replace").read().split("\n") if x.strip()]
    for x in ls[-3:]:
        print("   >", x[:112])
