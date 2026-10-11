# -*- coding: utf-8 -*-
"""把 heavy_route 的定义从 /stt 之前移到 app=FastAPI() 之后（必须在第一个使用点之前）。"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
API = os.path.join(MAIN, "api.py")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
start = s.find("# ===== 重型任务闸门")
end = s.find("@app.get(\"/heavy/status\")")
if start < 0 or end < 0:
    print("✗ 找不到闸门块")
    sys.exit(1)
# 状态接口单独留着（放哪都行），装饰器定义搬走
block_end = s.find("# ===== 手机端 STT", start)
block = s[start:block_end]
# 拆出：装饰器定义（heavy_route）与状态接口
dec_start = block.find("def heavy_route(")
dec_end = block.find("@app.get(\"/heavy/status\")")
dec = block[:dec_end]
status = block[dec_end:]
# 从原处移除整个块
s = s[:start] + s[block_end:]
# 插到 app = FastAPI() 之后
anchor = "app = FastAPI()"
if anchor not in s:
    print("✗ 找不到 FastAPI() 锚点")
    sys.exit(1)
s = s.replace(anchor, anchor + "\n\n\n" + dec.rstrip() + "\n\n\n" + status.rstrip() + "\n", 1)
io.open(API, "w", encoding="utf-8", newline="\n").write(s)
print("✓ 已把 heavy_route 定义与 /heavy/status 移到 FastAPI() 之后")

print()
r = subprocess.run([PY, "-c", "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % API],
                   capture_output=True, text=True)
print("   语法: " + ("✓ OK" if r.returncode == 0 else "✗ " + (r.stderr or "")[:200]))
if r.returncode != 0:
    sys.exit(1)

print()
print("=== 重启 api ===")
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
ready = False
for i in range(25):
    time.sleep(2)
    try:
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ 就绪 %ds" % (i * 2 + 2)); ready = True; break
    except Exception:
        pass
if not ready:
    print("   ✗ 起不来：")
    print(subprocess.run(["powershell", "-Command",
                          "Get-Content '%s\\dev\\logs\\api.log' -Tail 10" % MAIN],
                         capture_output=True, text=True).stdout[-900:])
    sys.exit(1)

print()
print("=== 取证 ===")
for path in ("/heavy/status", "/qq/status", "/qq/outbox"):
    try:
        with urllib.request.urlopen("http://127.0.0.1:28565" + path, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
        print("   %-16s → %s" % (path, body[:170]))
    except Exception as e:
        print("   %-16s → ✗ %s" % (path, e))

MSG = """fix(tts): heavy_route 定义位置前移 —— 首个使用点(118 行)在定义(320 行)之前导致 NameError

上一提交把装饰器定义插在 /stt 之前（≈320 行），但第一个用到它的 /qwen3-lora 在 118 行，
启动即 NameError: name 'heavy_route' is not defined。
改为把 heavy_route 定义与 /heavy/status 一起放在 app = FastAPI() 之后（所有路由之前）。

验证：语法检查通过；重启 api 就绪；/heavy/status、/qq/status、/qq/outbox 均正常返回。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_heavy2.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
