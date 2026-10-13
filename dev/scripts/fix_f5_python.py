# -*- coding: utf-8 -*-
"""① 确认 _f5tts_venv_python 到底是什么（是不是"忽略探测结果"的那个）
   ② 把第 668 行改成用探到的 f5_py
   ③ 验证：全局 python 能否完整 import，并能真正把服务起起来（模型加载成功）
"""
import io
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"E:\university\order\python\pet\AIpet-Murasame-main"
RUN = os.path.join(ROOT, "run.py")
GLOBAL = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

print("=== ① _f5tts_venv_python 的定义 ===")
ls = io.open(RUN, encoding="utf-8", errors="replace").read().split("\n")
for i, l in enumerate(ls, 1):
    if "_f5tts_venv_python" in l:
        print("   %5d| %s" % (i, l.rstrip()[:112]))
# 打印它的定义体
m = next((i for i, l in enumerate(ls) if l.startswith("def _f5tts_venv_python")), None)
if m is not None:
    for j in range(m, min(len(ls), m + 22)):
        print("   %5d| %s" % (j + 1, ls[j].rstrip()[:112]))

print()
print("=== ② 改 668 行：用探到的 f5_py，而不是 _f5tts_venv_python() ===")
t = io.open(RUN, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")
OLD = """        proc = subprocess.Popen(
            [_f5tts_venv_python(), "-m", "longtext.f5tts_server"],"""
NEW = """        # ★ 2026-10-14 修：这里原来写的是 _f5tts_venv_python()，**把上面探测的结果丢掉了** ——
        #   探测（_find_f5tts_python）明明找到了"能 import f5_tts"的解释器（例如系统 Python），
        #   启动时却又回去用 runtime\\venv，于是必然报 "No module named 'f5_tts'"。
        #   主人 2026-10-14 贴的日志就是这个现象。现在改为**用探到的那个**。
        proc = subprocess.Popen(
            [f5_py, "-m", "longtext.f5tts_server"],"""
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    io.open(RUN, "w", encoding="utf-8", newline="\n").write(t)
    print("   ✓ 已改")
else:
    print("   ✗ 锚点未命中")
import py_compile  # noqa: E402
try:
    py_compile.compile(RUN, doraise=True)
    print("   ✓ py_compile OK")
except Exception as e:
    print("   ✗ py_compile:", e)
    sys.exit(1)

print()
print("=== ③ 全局 python 完整 import（f5_tts.api + torch）===")
r = subprocess.run([GLOBAL, "-c",
                    "from f5_tts.api import F5TTS\nimport torch\n"
                    "print('OK f5_tts.api 可用; torch', torch.__version__)"],
                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=ENV, timeout=900)
out = ((r.stdout or "") + (r.stderr or ""))
for l in out.split("\n")[-8:]:
    if l.strip():
        print("   " + l.strip()[:130])
print("   退出码 =", r.returncode)

print()
print("=== ④ 真起一次服务（用全局 python；等模型加载）===")
flags = 0x00000010 | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x4000)
proc = subprocess.Popen([GLOBAL, "-m", "longtext.f5tts_server"], cwd=ROOT, env=ENV,
                        creationflags=flags)
print("   PID =", proc.pid, "（新控制台；下面看它能否监听 9881）")


def port_open(port=9881):
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "(Get-NetTCPConnection -LocalPort %d -State Listen "
                        "-ErrorAction SilentlyContinue | Measure-Object).Count" % port],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=180)
    return (r.stdout or "").strip() == "1"


ok = False
for i in range(24):          # 最多等 2 分钟（模型加载 + 设备探测）
    time.sleep(5)
    if proc.poll() is not None:
        print("   ✗ 进程第 %d 秒退出了（退出码 %s）" % ((i + 1) * 5, proc.returncode))
        break
    if port_open():
        print("   ✓ 第 %d 秒：9881 已监听 —— **服务真的起来了**" % ((i + 1) * 5))
        ok = True
        break
if not ok and proc.poll() is None:
    print("   ⚠ 2 分钟内没监听到（可能还在加载模型）")

print()
print("=== ⑤ 收工：停掉测试进程 ===")
subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
time.sleep(3)
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "(Get-NetTCPConnection -LocalPort 9881 -State Listen -ErrorAction "
                    "SilentlyContinue | Measure-Object).Count"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
print("   9881 监听数 =", (r.stdout or "").strip(), "（0 = 已停 ✓）")
