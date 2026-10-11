# -*- coding: utf-8 -*-
"""分离启动 F5(9881) 与 api(28565)，轮询端口；然后真调 NanoJev /api/evaluate 与 api 的 openapi，验证整条链。"""
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = r"E:\university\order\python\pet\AIpet-Murasame-main"
LOGDIR = os.path.join(REPO, "dev", "logs")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"
DETACHED = 0x00000008 | 0x00000200
os.makedirs(LOGDIR, exist_ok=True)


def up(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def start(name, args, env_extra=None, cwd=REPO):
    logp = os.path.join(LOGDIR, name)
    lf = io.open(logp, "wb")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if env_extra:
        env.update(env_extra)
    p = subprocess.Popen([PY, "-u"] + args, cwd=cwd, stdout=lf, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, creationflags=DETACHED, env=env)
    print("   ✓ 启动 %s pid=%d → %s" % (name, p.pid, logp))
    return p


print("=== 当前状态 ===")
for port, nm in ((8765, "NanoJev"), (9881, "F5-TTS"), (28565, "api.py")):
    print("   %-8s %d  %s" % (nm, port, "✓ 在听" if up(port) else "✗ 没在听"))

print()
print("=== 补齐缺失的服务 ===")
if not up(9881):
    start("f5tts.log", [r"longtext\f5tts_server.py"])
else:
    print("   F5 已在运行")
if not up(28565):
    start("api.log", ["-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"],
          env_extra={"TYPESAFE_BASE_URL": "http://127.0.0.1:8765/api/evaluate"})
else:
    print("   api 已在运行")

print()
print("=== 等 F5 与 api 就绪（最多 120 秒；F5 首次加载模型较慢）===")
deadline = time.time() + 120
while time.time() < deadline:
    a, b = up(9881), up(28565)
    print("   %s  9881=%s 28565=%s" % (time.strftime("%H:%M:%S"), a, b))
    if a and b:
        break
    time.sleep(10)

print()
print("=== 端到端实测 1：直接问 NanoJev（本地模型做选择题）===")
payload = {
    "states": [{
        "id": "s1",
        "state": "晚上十点，我又渴又困，明天还要早起上课。",
        "questions": {
            "q1": {"type": "multiple_choice",
                   "instructions": "此刻最想做的事",
                   "criteria": ["喝奶茶", "睡觉", "打游戏", "写作业"]}
        }
    }]
}
try:
    req = urllib.request.Request("http://127.0.0.1:8765/api/evaluate",
                                data=json.dumps(payload).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=60) as f:
        body = json.loads(f.read().decode("utf-8"))
    dt = time.time() - t0
    print("   ✓ 用时 %.2f 秒" % dt)
    print("   " + json.dumps(body, ensure_ascii=False)[:500])
except Exception as e:
    print("   ✗ %s: %s" % (type(e).__name__, e))

print()
print("=== 端到端实测 2：看 api.py 暴露了哪些路由 ===")
try:
    with urllib.request.urlopen("http://127.0.0.1:28565/openapi.json", timeout=15) as f:
        spec = json.loads(f.read().decode("utf-8"))
    print("   路由：", ", ".join(spec.get("paths", {}).keys())[:400])
except Exception as e:
    print("   ✗ %s: %s" % (type(e).__name__, e))

print()
print("=== 最终端口 ===")
for port, nm in ((8765, "NanoJev"), (9881, "F5-TTS"), (28565, "api.py")):
    print("   %-8s %d  %s" % (nm, port, "✓ 在听" if up(port) else "✗ 没在听"))
print()
print("=== 日志文件 ===")
for n in ("nanojev.log", "f5tts.log", "api.log"):
    p = os.path.join(LOGDIR, n)
    print("   %-12s %s" % (n, ("%d B" % os.path.getsize(p)) if os.path.exists(p) else "✗ 不存在"))
