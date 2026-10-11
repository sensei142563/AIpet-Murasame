# -*- coding: utf-8 -*-
"""① 给三个服务窗口加 chcp 65001 + PYTHONIOENCODING=utf-8（中文可读，日志也是 UTF-8）
   ② 以分离进程启动 NanoJev 并写日志  ③ 轮询 8765 健康检查确认真的起来了。"""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
LOGDIR = os.path.join(DEV, "logs")
BAT1 = os.path.join(DEV, "一键启动-本地Jev与语音.bat")
NANO = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

# ① 修 bat：让每个服务窗口用 UTF-8（控制台 + python 输出）
s = io.open(BAT1, encoding="gbk").read()
n1 = s.count('cmd /c "cd /d ')
s = s.replace('cmd /c "cd /d ', 'cmd /c "chcp 65001 >nul && cd /d ')
n2 = s.count("&& %PY%")
s = s.replace("&& %PY%", "&& set PYTHONIOENCODING=utf-8 && %PY%")
io.open(BAT1, "w", encoding="gbk", newline="").write(s.replace("\r\n", "\n").replace("\n", "\r\n"))
print("✓ bat 已加 chcp 65001（%d 处）与 PYTHONIOENCODING=utf-8（%d 处）" % (n1, n2))

# ② 分离启动 NanoJev
os.makedirs(LOGDIR, exist_ok=True)
logp = os.path.join(LOGDIR, "nanojev.log")
lf = io.open(logp, "wb")
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
p = subprocess.Popen(
    [PY, "-u", r"scripts\serve_decisions.py",
     "--checkpoint-dir", r"checkpoints\NanoJev-unified",
     "--web-root", "web", "--port", "8765", "--precision", "bf16"],
    cwd=NANO, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    creationflags=DETACHED, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
)
print("✓ 已启动 NanoJev pid=%d，日志 → %s" % (p.pid, logp))
print("   等待就绪（模型加载约 10~30 秒）...")
ok = False
for i in range(18):
    time.sleep(5)
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            pass
    except Exception:
        print("   %s  %ds  端口还没开" % (time.strftime("%H:%M:%S"), (i + 1) * 5))
        continue
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as f:
            body = f.read(400).decode("utf-8", errors="replace")
        print("   %s  ✓ /api/health → %s" % (time.strftime("%H:%M:%S"), body.strip()))
        ok = True
        break
    except Exception as e:
        print("   %s  端口开了但健康检查还没好：%s" % (time.strftime("%H:%M:%S"), e))

print()
print("=== 三个端口最终状态 ===")
for port in (8765, 9881, 28565):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            print("   %d  ✓ 在监听" % port)
    except Exception:
        print("   %d  ✗ 没在听" % port)
print()
print("=== nanojev.log 尾部 ===")
if os.path.exists(logp):
    for l in io.open(logp, encoding="utf-8", errors="replace").read().splitlines()[-8:]:
        print("   | " + l[:150])
print()
print("广告：NanoJev 就绪 =", ok)
