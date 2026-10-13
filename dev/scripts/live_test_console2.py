# -*- coding: utf-8 -*-
"""修完后重测：真启动一次，验证 ① 窗口标题 ② 控制台只有横幅 ③ 日志里有 api.py 输出
   ④ 9880 起来了 ⑤ /T 收掉后不留孤儿。
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
GSV = os.path.join(ROOT, "GPT-SoVITS")
PY = os.path.join(GSV, "runtime", "python.exe")
WRAP = os.path.join(ROOT, "tool", "tts_console.py")
LOG = os.path.join(ROOT, "data", "tts_service.log")
MYPID = str(os.getpid())


def pyprocs():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    out = []
    for l in (r.stdout or "").split("\n"):
        l = l.strip()
        if l and "|" in l and MYPID not in l.split("|")[0]:
            out.append(l)
    return out


def port_listening():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-NetTCPConnection -LocalPort 9880 -State Listen -ErrorAction "
                        "SilentlyContinue | Measure-Object).Count"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    return (r.stdout or "").strip()


if os.path.isfile(LOG):
    try:
        os.remove(LOG)
    except Exception:
        pass

print("=== ① 启动（新控制台，和 run.py 一样的方式）===")
flags = 0x00000010 | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
p = subprocess.Popen([PY, WRAP, os.path.join(ROOT, "data", "tts_console.json"), "--",
                      "api.py",
                      "-s", "SoVITS_weights/murasame-sovits.pth",
                      "-g", "GPT_weights/murasame-gpt.ckpt"],
                     cwd=GSV, creationflags=flags)
print("   外壳 PID =", p.pid)

print("   等 45 秒（api.py 要加载模型；它刷的东西都进日志，不进窗口）…")
for _ in range(9):
    time.sleep(5)
    n = port_listening()
    if n == "1":
        break

print()
print("=== ② 进程树 ===")
for l in pyprocs():
    print("   ", l[:120])

print()
print("=== ③ 9880 端口监听数 ===", port_listening(), "（1 = 服务起来了 ✓）")

print()
print("=== ④ 日志（服务本体的输出应该全在这儿）===")
if os.path.isfile(LOG):
    txt = io.open(LOG, encoding="utf-8", errors="replace").read()
    ls = [x for x in txt.split("\n") if x.strip()]
    print("   共 %d 行 / %d 字节" % (len(ls), os.path.getsize(LOG)))
    for x in ls[:6]:
        print("   >", x[:112])
    if len(ls) > 10:
        print("   > …")
        for x in ls[-4:]:
            print("   >", x[:112])
else:
    print("   ✗ 没有日志")

print()
print("=== ⑤ 窗口标题（用 UIA 读那个控制台窗口）===")
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process | Where-Object { $_.MainWindowTitle -ne '' } | "
                    "Select-Object -First 12 -ExpandProperty MainWindowTitle"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   timeout=300)
for l in (r.stdout or "").split("\n"):
    l = l.strip()
    if l:
        tag = "  ← 这个是语音服务窗口" if ("语音服务" in l or "GPT-SoVITS" in l) else ""
        print("   |", l[:100], tag)

print()
print("=== ⑥ 收工：taskkill /T /F 外壳 → 查残留 ===")
subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
time.sleep(5)
left = pyprocs()
print("   残留 python：%d 个" % len(left))
for l in left:
    print("   !", l[:120])
print("   ⇒", "干净 ✓（不留孤儿）" if not left else "仍有残留 ✗")
print("   9880 监听数：", port_listening())
