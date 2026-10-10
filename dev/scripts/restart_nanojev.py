# -*- coding: utf-8 -*-
"""重启 NanoJev（卡死，GPU 100% 不答健康检查）→ 复测健康与 evaluate 计时 → 再测 api 的 /jev/choose。"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
AUD = r"E:\university\order\python\pet\_audit_fish9269"
NANO = os.path.join(AUD, "repros", "NanoJev")
LOG = os.path.join(NANO, "_serve.log")
PY = shutil.which("python") or sys.executable
TMP = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots"

print("=== ① 找并杀掉卡死的 NanoJev ===")
r = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, encoding="utf-8", errors="replace")
pid = None
for l in (r.stdout or "").splitlines():
    if ":8765" in l and "LISTEN" in l.upper():
        pid = l.split()[-1]
        print("   8765 由 pid", pid, "监听")
if pid:
    print("   taskkill:", subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, text=True,
                                         encoding="utf-8", errors="replace").stdout.strip()[:60])
time.sleep(3)

print("=== ② 用当前全局 Python 重启（CUDA/bf16）===")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
with io.open(LOG, "a", encoding="utf-8") as f:
    f.write("\n\n===== 重启 %s =====\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    f.flush()
    proc = subprocess.Popen([PY, "-u", "scripts/serve_decisions.py",
                             "--checkpoint-dir", "checkpoints/NanoJev-unified",
                             "--web-root", "web", "--port", "8765", "--precision", "bf16"],
                            cwd=NANO, stdout=f, stderr=subprocess.STDOUT, env=env)
print("   新 pid =", proc.pid)

print("=== ③ 等就绪（最多 6 分钟）===")
ok = False
for k in range(36):
    time.sleep(10)
    try:
        rr = subprocess.run(["curl.exe", "-s", "--max-time", "8", "http://127.0.0.1:8765/api/health"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        h = (rr.stdout or "").strip()
        if "ready" in h:
            print("   %3ds ✓ %s" % ((k + 1) * 10, h[:110]))
            ok = True
            break
    except Exception:
        pass
    if k % 3 == 2:
        print("   %3ds 还在加载…" % ((k + 1) * 10))
if not ok:
    print("   ✗ 未就绪；日志尾部：")
    for l in io.open(LOG, encoding="utf-8", errors="replace").read().splitlines()[-15:]:
        print("      " + l.rstrip()[:120])
    sys.exit(1)

print()
print("=== ④ 直接打 NanoJev evaluate 并计时 ===")
body = {"states": [{"id": "s1", "state": "hello\n主人，本座今天心情不错。",
                    "questions": {"q1": {"type": "choice", "instructions": "选一个",
                                         "criteria": {"a": "开心", "b": "生气", "c": "害羞", "d": "平静"}}}}]}
bp = os.path.join(TMP, "_req3.json")
io.open(bp, "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
t0 = time.time()
out = subprocess.run(["curl.exe", "-s", "--max-time", "180", "-X", "POST",
                      "-H", "Content-Type: application/json; charset=utf-8",
                      "--data-binary", "@" + bp, "http://127.0.0.1:8765/api/evaluate"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
el = time.time() - t0
print("   耗时 %.2f 秒" % el)
print("   返回:", (out.stdout or "").strip()[:400])
try:
    j = json.loads(out.stdout or "{}")
    st = (j.get("states") or [{}])[0]
    print("   ★ 解析：答案 =", st.get("answers"), "| provider_calls =", j.get("provider_calls"))
except Exception as e:
    print("   （解析失败:", e, "）")

print()
print("=== ⑤ 再打 api 的 /jev/choose 计时 ===")
body2 = {"state": "hello\n主人，本座今天心情不错。", "question": "这条回复最该配哪个表情包？只从给定名称里选一个。",
         "options": ["开心", "生气", "害羞", "平静"], "timeout": 30}
bp2 = os.path.join(TMP, "_req4.json")
io.open(bp2, "w", encoding="utf-8").write(json.dumps(body2, ensure_ascii=False))
t1 = time.time()
out2 = subprocess.run(["curl.exe", "-s", "--max-time", "90", "-X", "POST",
                       "-H", "Content-Type: application/json; charset=utf-8",
                       "--data-binary", "@" + bp2, "http://127.0.0.1:28565/jev/choose"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
print("   耗时 %.2f 秒" % (time.time() - t1))
print("   返回:", (out2.stdout or "").strip()[:300])
print()
print("=== ⑥ GPU ===")
print(subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu",
                      "--format=csv,noheader"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())
print()
print("=== ⑦ NanoJev 日志尾部 ===")
for l in io.open(LOG, encoding="utf-8", errors="replace").read().splitlines()[-8:]:
    print("   " + l.rstrip()[:124])
