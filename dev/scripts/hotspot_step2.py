# -*- coding: utf-8 -*-
"""起三服务（分离进程 + 日志）→ 等待就绪 → 逐端口验证 127.0.0.1 与局域网 IP → 开 adb tcpip 5555 并重建转发。"""
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
NANO = r"E:\university\order\python\pet\_audit_fish9269\repros\NanoJev"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
ADB = r"E:\Android\SDK\platform-tools\adb.exe"
LOG = os.path.join(MAIN, "dev", "logs")
DEV = "4BD9K24C06021770"
os.makedirs(LOG, exist_ok=True)

DETACHED = 0x00000008 | 0x00000200


def spawn(cmd, cwd, logname, env_extra=None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    f = open(os.path.join(LOG, logname), "wb")
    p = subprocess.Popen(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env,
                         creationflags=DETACHED, close_fds=True)
    print("   起 %-14s pid=%d  日志 dev/logs/%s" % (logname, p.pid, logname))
    return p.pid


def probe(ip, port, t=1.5):
    try:
        with socket.create_connection((ip, port), timeout=t):
            return True
    except Exception:
        return False


def sh(*a, t=300):
    return subprocess.run([ADB, "shell", *a], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=t).stdout or ""


print("=== ① 起三个服务（分离进程）===")
spawn([PY, "-u", "scripts\\serve_decisions.py", "--checkpoint-dir", "checkpoints\\NanoJev-unified",
       "--web-root", "web", "--port", "8765", "--precision", "bf16"], NANO, "nanojev.log")
spawn([PY, "-u", "longtext\\f5tts_server.py"], MAIN, "f5tts.log")
spawn([PY, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"], MAIN, "api.log",
      {"TYPESAFE_BASE_URL": "http://127.0.0.1:8765/api/evaluate"})

print()
print("=== ② 等待就绪（NanoJev 首次约 20s，F5 约 40s）===")
ips = []
try:
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { $_.IPAddress }"],
                       capture_output=True, text=True, timeout=120)
    ips = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
except Exception:
    pass
print("   局域网候选:", ips or "(无)")

for round_ in range(1, 13):
    time.sleep(10)
    st = {p: probe("127.0.0.1", p) for p in (8765, 9881, 28565)}
    print("   %2ds: 8765=%s 9881=%s 28565=%s" % (round_ * 10,
          "✓" if st[8765] else "·", "✓" if st[9881] else "·", "✓" if st[28565] else "·"))
    if all(st.values()):
        break

print()
print("=== ③ 逐端口验证：127.0.0.1 vs 局域网 IP（关键：证明绑到了 0.0.0.0）===")
ok = True
for port, name in ((8765, "NanoJev"), (9881, "F5-TTS"), (28565, "api.py")):
    loop = probe("127.0.0.1", port)
    lan = {ip: probe(ip, port) for ip in ips}
    lanok = [ip for ip, v in lan.items() if v]
    print("   %-6d %-8s 127.0.0.1=%s  局域网=%s" % (
        port, name, "✓" if loop else "✗", ("、".join(lanok) + " ✓" if lanok else "✗ 不通")))
    if not loop:
        ok = False

print()
print("=== ④ 开无线 adb（5555）并重建 USB 转发 ===")
r = subprocess.run([ADB, "tcpip", "5555"], capture_output=True, text=True, timeout=120)
print("   adb tcpip 5555:", ((r.stdout or "") + (r.stderr or "")).strip()[:80])
time.sleep(6)
subprocess.run([ADB, "wait-for-device"], timeout=180)
print("   设备:", subprocess.run([ADB, "devices"], capture_output=True, text=True,
                              timeout=60).stdout.replace("\n", " ").strip()[:120])
for p in (28565, 9881):
    subprocess.run([ADB, "-s", DEV, "reverse", "tcp:%d" % p, "tcp:%d" % p], capture_output=True, timeout=120)
print("   reverse:", subprocess.run([ADB, "reverse", "--list"], capture_output=True, text=True,
                                   timeout=60).stdout.replace("\n", " | ").strip()[:150])
print()
print("总结:", "服务已就绪 ✓（局域网 IP 可直连）" if ok else "有服务没起来 ✗")
