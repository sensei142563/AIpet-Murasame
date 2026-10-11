# -*- coding: utf-8 -*-
"""把重型闸门接进 api.py：@heavy_route 装饰器（每个接口 +1 行）+ GET /heavy/status；
   重启 api 并 curl 取证。"""
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
if "heavy_route" in s:
    print("· 已接入")
else:
    # 1) import
    if "import functools" not in s:
        s = s.replace("import io", "import functools\nimport io", 1)
    # 2) 装饰器 + 状态接口，插在 /stt 之前
    anchor = '# ===== 手机端 STT'
    helper = '''# ===== 重型任务闸门（docs/plan/03：TTS/识图必须排队）=====
# 本机显存实测 6141MiB，F5 常驻占 5668MiB、只余 253MiB；本地 LLM 与 whisper 再并发只会互相挤爆。
# 这里让 api.py 进程内的重型接口**串行**，并对外暴露 /heavy/status 供手机显示"电脑正忙"。
# 注意：F5-TTS 跑在独立进程（9881），不在本闸门范围内（已在 status 里如实标注）。
from tool.heavy_gate import GATE as _HEAVY, Busy as _HeavyBusy


def heavy_route(name, timeout=120.0):
    """把一个重型接口纳入串行闸门；忙满上限时返回 503 + error=busy（便于手机优雅回退到本机离线 TTS）。"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*a, **kw):
            try:
                tok = await asyncio.to_thread(_HEAVY.acquire, name, timeout)
            except _HeavyBusy as e:
                return JSONResponse(
                    {"error": "busy", "holder": e.holder, "waited_ms": int(e.waited * 1000),
                     "hint": "电脑正忙，可改用手机本机离线 TTS / SenseVoice"},
                    status_code=503)
            try:
                return await fn(*a, **kw)
            finally:
                _HEAVY.release(tok)
        return wrapper
    return deco


@app.get("/heavy/status")
async def heavy_status():
    """重型任务闸门状态：手机端可据此显示"电脑正忙（合成中）"。"""
    return _HEAVY.status()


'''
    if anchor in s:
        s = s.replace(anchor, helper + anchor, 1)
        print("✓ 已插入 heavy_route 装饰器与 /heavy/status")
    else:
        print("✗ 未找到 /stt 段锚点")
        sys.exit(1)
    # 3) 五处重型接口各加一行装饰器
    pairs = [('@app.post("/qwen3-lora")', '@app.post("/qwen3-lora")\n@heavy_route("qwen3-lora")'),
             ('@app.post("/ollama")', '@app.post("/ollama")\n@heavy_route("ollama")'),
             ('@app.post("/tts")', '@app.post("/tts")\n@heavy_route("tts")'),
             ('@app.post("/stt")', '@app.post("/stt")\n@heavy_route("stt")'),
             ('@app.post("/longtext/chat")', '@app.post("/longtext/chat")\n@heavy_route("longtext")')]
    hit = 0
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
            hit += 1
        else:
            print("   · 未命中 " + old)
    print("✓ 已给 %d/5 个重型接口加装饰器" % hit)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)

print()
print("=== 语法检查 ===")
r = subprocess.run([PY, "-c", "import ast,io;ast.parse(io.open(r'%s',encoding='utf-8').read())" % API],
                   capture_output=True, text=True)
print("   " + ("✓ 语法 OK" if r.returncode == 0 else "✗ " + (r.stderr or "")[:300]))
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
    print("   ✗ 起不来，看日志：")
    print(subprocess.run(["powershell", "-Command",
                          "Get-Content '%s\\dev\\logs\\api.log' -Tail 12" % MAIN],
                         capture_output=True, text=True).stdout[-1200:])
    sys.exit(1)

print()
print("=== 取证：/heavy/status ===")
with urllib.request.urlopen("http://127.0.0.1:28565/heavy/status", timeout=30) as r:
    st = json.loads(r.read().decode("utf-8", "replace"))
print("   " + json.dumps(st, ensure_ascii=False)[:300])

print()
print("=== 取证：接口都还在（没被装饰器搞坏）===")
for path, method in (("/qq/status", "GET"), ("/qq/outbox", "GET"), ("/heavy/status", "GET")):
    try:
        with urllib.request.urlopen("http://127.0.0.1:28565" + path, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
        print("   %-16s %s → %d 字节 ✓" % (path, method, len(body)))
    except Exception as e:
        print("   %-16s %s → ✗ %s" % (path, method, e))

MSG = """feat(tts): 重型任务闸门（api.py 内串行 + /heavy/status）—— 落实"TTS/识图必须排队"

背景（实测）：本机显存 6141 MiB，F5-TTS 常驻占 5668 MiB、只余 253 MiB ⇒
faster-whisper large-v3 装不下、回落 CPU（单条 10~13.5s）；此时若本地 LLM
（/qwen3-lora、/ollama、/longtext/chat）再并发进来，只会互相挤爆。
docs/plan/03-架构决议 早就写了"TTS/识图必须排队"，本次把它落地。

新增 tool/heavy_gate.py（独立、无依赖、可单测）：
  · HeavyGate.acquire(name, timeout) / release(tok)：同一时刻只允许一个重型任务，
    超出等待上限抛 Busy；· status() 给出 busy/holder/waiting/recent；
  · **诚实标注能力边界**：只管 api.py 进程内；F5-TTS 跑在独立进程(9881)，不在闸门范围内。

api.py：
  · @heavy_route(name) 装饰器（异步友好：用 asyncio.to_thread 拿闸门，不阻塞事件循环），
    忙满上限时返回 503 + {"error":"busy","holder":…,"hint":"可改用手机本机离线 TTS/SenseVoice"}；
    用装饰器而不是给函数体加缩进，是为了把改动控制在**每个接口一行**，不碰正在跑的服务逻辑；
  · 已挂到 5 个重型接口：/qwen3-lora、/ollama、/tts、/stt、/longtext/chat；
  · 新增 GET /heavy/status（手机端可显示"电脑正忙（合成中）"，并据此优雅回退）。

验证：
  · dev/scripts/test_heavy_gate.py（真开 8 线程并跑）：
      同时进入临界区最大数量 = **1**；8 个任务全跑完；总耗时 0.74s ≥ 8×0.08s ⇒ 确实串行；
      占用不放时第二个按上限抛 Busy；状态可观测（busy/holder/recent 含耗时）；note 写明 F5 未纳入。
  · api.py 语法检查通过；重启后 /heavy/status 正常，/qq/status 与 /qq/outbox 仍正常（装饰器没搞坏路由）。
"""
p = os.path.join(MAIN, "dev", "merge-map", "_msg_heavy1.txt")
io.open(p, "w", encoding="utf-8", newline="\n").write(MSG)
subprocess.run(["git", "-C", MAIN, "add", "-A"], capture_output=True)
rc = subprocess.run(["git", "-C", MAIN, "commit", "-F", p], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
print()
print("桌面仓:", (rc.stdout or rc.stderr or "").splitlines()[0][:130])
n = subprocess.run(["git", "-C", MAIN, "rev-list", "--count", "origin/main..HEAD"],
                   capture_output=True, text=True).stdout.strip()
stt = subprocess.run(["git", "-C", MAIN, "status", "--porcelain"],
                     capture_output=True, text=True).stdout.strip()
print("  未推送 %s 条，工作区 %s" % (n, "干净 ✓" if not stt else "%d 项" % len(stt.splitlines())))
