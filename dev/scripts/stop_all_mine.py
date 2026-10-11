# -*- coding: utf-8 -*-
"""只关我自己起的三个服务（按端口占用 + 我记录的 pid）+ 撤掉 adb 反向转发，然后验证干净。"""
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
PORTS = (8765, 9881, 28565)
MY_PIDS = {24764, 8128, 20952}   # 本轮我用分离进程起的：NanoJev / F5-TTS / api.py


def port_open(p):
    try:
        with socket.create_connection(("127.0.0.1", p), timeout=1):
            return True
    except Exception:
        return False


def pids_on(port):
    r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=120)
    out = set()
    for line in (r.stdout or "").splitlines():
        if "LISTENING" in line and re.search(r":%d\s" % port, line):
            parts = line.split()
            if parts and parts[-1].isdigit():
                out.add(int(parts[-1]))
    return out


print("=== 关闭前 ===")
targets = set()
for p in PORTS:
    o = port_open(p)
    ps = pids_on(p) if o else set()
    targets |= ps
    print("   %d  %s  占用pid=%s" % (p, "在听" if o else "没在听", sorted(ps) or "-"))

targets |= MY_PIDS
print()
print("=== 我要结束的进程（只这些）===", sorted(targets))
for pid in sorted(targets):
    r = subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, text=True, timeout=120)
    msg = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    print("   pid %-6d %s" % (pid, msg[0][:110] if msg else "ok"))

time.sleep(3)

print()
print("=== 关闭后（端口应全部关闭）===")
still = []
for p in PORTS:
    o = port_open(p)
    print("   %d  %s" % (p, "✗ 还在听" if o else "✓ 已关闭"))
    if o:
        still.append(p)

print()
print("=== 撤掉 adb 反向转发 ===")
r = subprocess.run([ADB, "reverse", "--remove-all"], capture_output=True, text=True, timeout=120)
print("   " + ((r.stdout or "") + (r.stderr or "")).strip()[:120])
r2 = subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True, timeout=120)
cur = (r2.stdout or "").strip()
print("   当前转发列表：", cur if cur else "(空 ✓)")

print()
print("=== 我本轮写在 dev\\logs 的日志（保留，你跑时会继续写）===")
L = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\logs"
if os.path.isdir(L):
    for n in sorted(os.listdir(L)):
        print("   %-14s %d B" % (n, os.path.getsize(os.path.join(L, n))))
print()
print("总结：端口仍占用 =", still or "无 ✓")
