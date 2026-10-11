# -*- coding: utf-8 -*-
"""按通配符找 bat（不怕改名）：① 给服务窗口加 UTF-8 中文支持 ② 分离启动 NanoJev 并验证 8765。"""
import glob
import io
import os
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev"
LOGDIR = os.path.join(DEV, "logs")
NANO = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"


def find(*pats):
    for pat in pats:
        hits = [p for p in glob.glob(os.path.join(DEV, pat)) if p.lower().endswith(".bat")]
        if hits:
            return hits[0]
    return None


bat_start = find("*Jev*.bat", "*启动*.bat")
bat_recon = find("*重连*.bat", "*连电脑*.bat")
bat_logs = find("*看日志*.bat", "*日志*.bat")
print("=== 找到的 bat ===")
for k, v in (("启动", bat_start), ("重连", bat_recon), ("看日志", bat_logs)):
    print("   %-6s %s" % (k, os.path.basename(v) if v else "✗ 没找到"))

if bat_start:
    s = io.open(bat_start, encoding="gbk").read()
    n1 = s.count('cmd /c "cd /d ')
    s = s.replace('cmd /c "cd /d ', 'cmd /c "chcp 65001 >nul && cd /d ')
    n2 = s.count("&& %PY%")
    s = s.replace("&& %PY%", "&& set PYTHONIOENCODING=utf-8 && %PY%")
    io.open(bat_start, "w", encoding="gbk", newline="").write(
        s.replace("\r\n", "\n").replace("\n", "\r\n"))
    print("✓ 已在启动 bat 里加 chcp 65001（%d 处）+ PYTHONIOENCODING=utf-8（%d 处）→ 窗口和日志都是 UTF-8" % (n1, n2))

os.makedirs(LOGDIR, exist_ok=True)

print()
print("=== 当前端口 ===")
for port in (8765, 9881, 28565):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            print("   %d ✓ 在听" % port)
    except Exception:
        print("   %d ✗ 没在听" % port)

need_nano = True
try:
    with socket.create_connection(("127.0.0.1", 8765), timeout=1):
        need_nano = False
except Exception:
    pass

if need_nano:
    logp = os.path.join(LOGDIR, "nanojev.log")
    lf = io.open(logp, "wb")
    DETACHED = 0x00000008 | 0x00000200
    p = subprocess.Popen(
        [PY, "-u", r"scripts\serve_decisions.py",
         "--checkpoint-dir", r"checkpoints\NanoJev-unified",
         "--web-root", "web", "--port", "8765", "--precision", "bf16"],
        cwd=NANO, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        creationflags=DETACHED, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    print()
    print("✓ 已分离启动 NanoJev pid=%d → 日志 %s" % (p.pid, logp))
    print("   等待就绪（加载模型 10~40 秒）...")
    for i in range(20):
        time.sleep(5)
        try:
            with socket.create_connection(("127.0.0.1", 8765), timeout=1):
                pass
        except Exception:
            print("   %s  %2ds  端口未开" % (time.strftime("%H:%M:%S"), (i + 1) * 5))
            continue
        try:
            with urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=5) as f:
                body = f.read(400).decode("utf-8", errors="replace")
            print("   %s  ✓ /api/health → %s" % (time.strftime("%H:%M:%S"), body.strip()))
            break
        except Exception as e:
            print("   %s  端口开了，健康检查稍后重试（%s）" % (time.strftime("%H:%M:%S"), e))
else:
    print()
    print("（NanoJev 已在运行，跳过启动）")

print()
print("=== 最终端口 ===")
allok = True
for port in (8765, 9881, 28565):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            print("   %d ✓ 在听" % port)
    except Exception:
        print("   %d ✗ 没在听" % port)
        allok = False
print()
print("=== nanojev.log 尾部 ===")
p2 = os.path.join(LOGDIR, "nanojev.log")
if os.path.exists(p2):
    for l in io.open(p2, encoding="utf-8", errors="replace").read().splitlines()[-6:]:
        print("   | " + l[:150])
print()
print("结论：三个服务全在 =", allok)
