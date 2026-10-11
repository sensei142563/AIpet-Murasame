# -*- coding: utf-8 -*-
"""重启 api（加载新加的 /qq/outbox），然后重跑手机 QQ 页的替代验收。"""
import io
import os
import re
import socket
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

print("=== 重启 api.py ===")
for line in subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout.splitlines():
    if ":28565" in line and "LISTENING" in line:
        p = line.split()[-1]
        if p.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", p], capture_output=True)
            print("   停旧 api", p)
time.sleep(2)
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["TYPESAFE_BASE_URL"] = "http://127.0.0.1:8765/api/evaluate"
subprocess.Popen([PY, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"],
                 cwd=MAIN, stdout=open(os.path.join(MAIN, "dev", "logs", "api.log"), "ab"),
                 stderr=subprocess.STDOUT, env=env, creationflags=0x00000008 | 0x00000200)
for i in range(20):
    time.sleep(2)
    try:
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ 就绪 %ds" % (i * 2 + 2))
            break
    except Exception:
        pass

print()
r = subprocess.run([sys.executable, "-u", os.path.join(MAIN, "dev", "scripts",
                                                       "verify_qq_screen_offline.py")],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
out = (r.stdout or "") + (r.stderr or "")
i = out.find("=== ② 重放")
print(out[i:] if i >= 0 else out[-2200:])
