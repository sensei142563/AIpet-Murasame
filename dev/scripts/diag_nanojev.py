# -*- coding: utf-8 -*-
"""直接前台跑 NanoJev 启动命令（30 秒超时），把真实报错抓出来。"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
NANO = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
CMD = [PY, "-u", r"scripts\serve_decisions.py",
       "--checkpoint-dir", r"checkpoints\NanoJev-unified",
       "--web-root", "web", "--port", "8765", "--precision", "bf16"]

print("=== 工作目录 ===")
print("   ", NANO, "[存在]" if os.path.isdir(NANO) else "[不存在]")
print("=== 目录内容（前 15 项）===")
for i, n in enumerate(sorted(os.listdir(NANO))[:15]):
    print("   ", n)
print()
print("=== 前台运行（最多 30 秒，观察启动输出）===")
try:
    r = subprocess.run(CMD, cwd=NANO, capture_output=True, timeout=30)
    out = (r.stdout or b"")
    err = (r.stderr or b"")
    print("   rc =", r.returncode)
except subprocess.TimeoutExpired as e:
    out = e.stdout or b""
    err = e.stderr or b""
    print("   → 30 秒未退出（说明它在正常常驻运行 ✓）")


def dec(b):
    for enc in ("utf-8", "gbk"):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode("utf-8", errors="replace")


print("=== stdout ===")
for l in dec(out).splitlines()[:30]:
    print("   | " + l[:160])
print("=== stderr ===")
for l in dec(err).splitlines()[:30]:
    print("   | " + l[:160])
