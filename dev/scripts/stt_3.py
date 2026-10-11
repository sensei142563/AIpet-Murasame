# -*- coding: utf-8 -*-
"""把 /stt 的模型加载改成只做一次（模块级缓存 + 首次预热），再测单条真实耗时。"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
API = os.path.join(MAIN, "api.py")
PY = r"C:\Users\ASUS\AppData\Local\Programs\Python\Python310\python.exe"

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
old = '''def _stt_transcribe_full(path):
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("aipet_stt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool", "stt.py"))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.transcribe_full(path)'''
new = '''_STT_MOD = None
_STT_LOCK = None


def _stt_module():
    """只加载一次（否则每次请求都会重建 faster-whisper 模型，单条要 20~37 秒）。"""
    global _STT_MOD, _STT_LOCK
    import threading
    if _STT_LOCK is None:
        _STT_LOCK = threading.Lock()
    with _STT_LOCK:
        if _STT_MOD is None:
            import importlib.util as _ilu
            spec = _ilu.spec_from_file_location(
                "aipet_stt",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool", "stt.py"))
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _STT_MOD = mod
    return _STT_MOD


def _stt_warmup():
    try:
        t0 = time.time()
        _stt_module().warmup("large-v3")
        print("[stt] 预热完成 %.1fs" % (time.time() - t0), flush=True)
    except Exception as e:
        print("[stt] 预热失败: %s: %s" % (type(e).__name__, e), flush=True)


def _stt_transcribe_full(path):
    return _stt_module().transcribe_full(path)'''
if old in s:
    s = s.replace(old, new, 1)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已改为模型只加载一次 + 预热")
else:
    print("· 未找到旧实现（可能已改）")

# 启动时预热（放在 app 定义之后，避免阻塞导入）
if "_stt_warmup()" not in s.replace("def _stt_warmup", ""):
    anchor = '@app.post("/stt")'
    if anchor in s:
        s = s.replace(anchor, 'try:\n    import threading as _th\n    _th.Timer(1.0, _stt_warmup).start()\nexcept Exception:\n    pass\n\n\n' + anchor, 1)
        io.open(API, "w", encoding="utf-8", newline="\n").write(s)
        print("✓ 已加启动预热（后台线程，1 秒后开始）")

print()
print("=== 重启 api（等预热完成）===")
out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
for line in out.splitlines():
    if ":28565" in line and "LISTENING" in line:
        p = line.split()[-1]
        if p.isdigit():
            subprocess.run(["taskkill", "/F", "/PID", p], capture_output=True)
            print("   停旧 api", p)
time.sleep(2)
LOG = os.path.join(MAIN, "dev", "logs", "api.log")
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["TYPESAFE_BASE_URL"] = "http://127.0.0.1:8765/api/evaluate"
subprocess.Popen([PY, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"],
                 cwd=MAIN, stdout=open(LOG, "ab"), stderr=subprocess.STDOUT, env=env,
                 creationflags=0x00000008 | 0x00000200)
print("   等待预热（最多 120s）…")
warm = False
for i in range(60):
    time.sleep(2)
    t = io.open(LOG, encoding="utf-8", errors="replace").read()
    if "[stt] 预热完成" in t:
        print("   " + [l for l in t.splitlines() if "预热完成" in l][-1])
        warm = True
        break
    if "[stt] 预热失败" in t:
        print("   " + [l for l in t.splitlines() if "预热失败" in l][-1])
        break
print("   预热:", "✓" if warm else "（未确认）")

idx = json.loads(io.open(os.path.join(CHAT, "app/src/main/assets/voice/index.json"),
                         encoding="utf-8").read())
import difflib
rows = []
for pet, mp in idx["index"].items():
    for text, name in list(mp.items())[:2]:
        p = os.path.join(CHAT, "app/src/main/assets/voice", pet, name)
        if not os.path.isfile(p):
            continue
        b = io.open(p, "rb").read()
        req = urllib.request.Request("http://127.0.0.1:28565/stt", data=b,
                                     headers={"Content-Type": "application/octet-stream"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            print("   ✗", e)
            continue
        got = (j.get("text") or "").strip()
        ratio = difflib.SequenceMatcher(None, text, got).ratio()
        rows.append((text, got, ratio, j.get("ms")))
        print("   标准 %-18s 识别 %-18s 相似 %.2f  服务端 %sms  往返 %.1fs" %
              (text, got, ratio, j.get("ms"), time.time() - t0))
if rows:
    print()
    print("   平均相似度 %.2f   平均服务端耗时 %.0f ms   平均往返 %.1f s" % (
        sum(r[2] for r in rows) / len(rows),
        sum(r[3] or 0 for r in rows) / len(rows),
        sum(r[3] or 0 for r in rows) / len(rows) / 1000.0))
    print("   判定:", "✓ 已可用于交互（秒级）" if (sum(r[3] or 0 for r in rows) / len(rows)) < 5000
          else "⚠ 仍偏慢，需要换更小模型或量化")
