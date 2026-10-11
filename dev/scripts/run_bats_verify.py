# -*- coding: utf-8 -*-
"""用 Python 调这两个 bat（避免 pwsh 中文路径问题），然后轮询端口 / 健康检查 / 日志尾部。"""
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
BAT1 = os.path.join(DEV, "一键启动-本地Jev与语音.bat")
BAT2 = os.path.join(DEV, "手机连电脑-一键重连.bat")


def run_bat(p, label):
    print("=== 运行 %s ===" % label)
    r = subprocess.run(["cmd", "/c", p], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=900)
    out = (r.stdout or b"").decode("gbk", errors="replace")
    err = (r.stderr or b"").decode("gbk", errors="replace")
    for line in (out + err).splitlines():
        if line.strip():
            print("   | " + line[:150])
    print("   rc=%d" % r.returncode)
    return r.returncode


def port_open(host, port, t=1.0):
    try:
        with socket.create_connection((host, port), timeout=t):
            return True
    except Exception:
        return False


def http(url, t=5):
    try:
        with urllib.request.urlopen(url, timeout=t) as f:
            return f.status, f.read(600).decode("utf-8", errors="replace")
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


run_bat(BAT2, "手机连电脑-一键重连.bat")
print()
rc1 = run_bat(BAT1, "一键启动-本地Jev与语音.bat")
print()

print("=== 等端口就绪（最多 150 秒）===")
deadline = time.time() + 150
state = {}
while time.time() < deadline:
    state = {p: port_open("127.0.0.1", p) for p in (8765, 9881, 28565)}
    print("   %s  8765=%s 9881=%s 28565=%s" % (time.strftime("%H:%M:%S"),
          state[8765], state[9881], state[28565]))
    if all(state.values()):
        break
    time.sleep(10)

print()
print("=== 健康检查 ===")
st, body = http("http://127.0.0.1:8765/api/health")
print("   NanoJev /api/health  HTTP=%s" % st)
print("   " + body.replace("\n", " ")[:400])
st2, body2 = http("http://127.0.0.1:28565/docs")
print("   api.py  /docs        HTTP=%s" % st2)

print()
print("=== adb reverse 列表 ===")
r = subprocess.run([r"E:\Android\SDK\platform-tools\adb.exe", "reverse", "--list"],
                   capture_output=True, text=True, timeout=120)
print("   " + (r.stdout or r.stderr or "").strip().replace("\n", "\n   "))

print()
print("=== 日志文件（新位置 dev\\logs）===")
for n in ("api.log", "nanojev.log", "f5tts.log"):
    p = os.path.join(LOGDIR, n)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        tail = io.open(p, encoding="utf-8", errors="replace").read().splitlines()[-6:]
        print("   %s  %d B" % (n, sz))
        for t in tail:
            print("      " + t[:140])
    else:
        print("   %s  ✗ 不存在" % n)
