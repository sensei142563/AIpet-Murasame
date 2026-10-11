# -*- coding: utf-8 -*-
"""STT 抄作业①：给 api.py 加 POST /stt（收原始 wav 字节 → 复用 tool/stt.py 的 faster-whisper large-v3）
   → 重启 api → 用「已知文本」的预生成台词当标准答案，POST 进去比对，给出准确率与耗时。"""
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
os.chdir(MAIN)
sys.path.insert(0, MAIN)

# ---------- ① 加路由 ----------
s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if '"/stt"' in s:
    print("· /stt 已存在")
else:
    route = '''# ===== 手机端 STT：收原始 WAV 字节，复用 tool/stt.py 的 faster-whisper large-v3 =====
# 手机本地只有 sherpa 14M（效果一般），连得上电脑时改走这里，质量直接对齐桌面端。
@app.post("/stt")
async def stt_transcribe(request: Request):
    import tempfile as _tf
    data = await request.body()
    if not data or len(data) < 1000:
        return {"text": "", "ms": 0, "reason": "audio too small (%d bytes)" % len(data)}
    t0 = time.time()
    tmp = _tf.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        text = await asyncio.to_thread(_stt_transcribe_full, tmp.name)
        return {"text": text or "", "ms": int((time.time() - t0) * 1000), "engine": "faster-whisper-large-v3"}
    except Exception as e:
        return {"text": "", "ms": int((time.time() - t0) * 1000), "error": "%s: %s" % (type(e).__name__, e)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _stt_transcribe_full(path):
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("aipet_stt", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tool", "stt.py"))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.transcribe_full(path)


'''
    anchor = '@app.post("/voice/start")'
    ok = anchor in s
    print(("✓ " if ok else "✗ ") + "定位 /voice/start 锚点")
    if ok:
        s = s.replace(anchor, route + anchor, 1)
        if not re.search(r"^import asyncio$", s, re.M):
            s = s.replace("import os", "import os\nimport asyncio", 1)
        if not re.search(r"from fastapi import .*\bRequest\b", s) and "Request" not in s.split("@app.")[0]:
            s = s.replace("from fastapi import FastAPI", "from fastapi import FastAPI, Request", 1)
        io.open(API, "w", encoding="utf-8", newline="\n").write(s)
        print("✓ /stt 已加入 api.py（asyncio/tempfile 已确保）")

# ---------- ② 重启 api（分离进程）----------
print()
print("=== 重启 api.py ===")
out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
pids = set()
for line in out.splitlines():
    if ":28565" in line and "LISTENING" in line:
        p = line.split()[-1]
        if p.isdigit():
            pids.add(p)
for p in pids:
    subprocess.run(["taskkill", "/F", "/PID", p], capture_output=True)
    print("   停掉旧 api pid", p)
time.sleep(2)
LOG = os.path.join(MAIN, "dev", "logs", "api.log")
env = dict(os.environ)
env["PYTHONIOENCODING"] = "utf-8"
env["TYPESAFE_BASE_URL"] = "http://127.0.0.1:8765/api/evaluate"
f = open(LOG, "ab")
subprocess.Popen([PY, "-u", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "28565"],
                 cwd=MAIN, stdout=f, stderr=subprocess.STDOUT, env=env,
                 creationflags=0x00000008 | 0x00000200)
for i in range(20):
    time.sleep(2)
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ api 已就绪（%ds）" % (i * 2 + 2))
            break
    except Exception:
        pass
else:
    print("   ✗ api 没起来，看 dev/logs/api.log")
    sys.exit(1)

# ---------- ③ 用已知文本的台词当标准答案 ----------
print()
print("=== 用预生成台词（已知文本）验证 /stt ===")
idx = json.loads(io.open(os.path.join(CHAT, "app/src/main/assets/voice/index.json"),
                         encoding="utf-8").read())
samples = []
for pet, mp in idx["index"].items():
    for text, name in list(mp.items())[:3]:
        p = os.path.join(CHAT, "app/src/main/assets/voice", pet, name)
        if os.path.isfile(p):
            samples.append((text, p))

import difflib
rows = []
for text, p in samples[:5]:
    b = io.open(p, "rb").read()
    req = urllib.request.Request("http://127.0.0.1:28565/stt", data=b,
                                 headers={"Content-Type": "application/octet-stream"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            j = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("   ✗ 请求失败:", e)
        continue
    got = (j.get("text") or "").strip()
    ratio = difflib.SequenceMatcher(None, text, got).ratio()
    rows.append((text, got, ratio, j.get("ms"), time.time() - t0, j.get("error")))
    print("   标准: %s" % text)
    print("   识别: %s" % (got or "(空)"))
    print("   相似度: %.2f   服务端耗时: %sms   往返: %.1fs%s" %
          (ratio, j.get("ms"), time.time() - t0, ("  错误: " + str(j.get("error"))) if j.get("error") else ""))
    print()

if rows:
    avg = sum(r[2] for r in rows) / len(rows)
    print("=== 结论 ===")
    print("   样本 %d 条，平均相似度 %.2f" % (len(rows), avg))
    print("   平均往返 %.1f 秒" % (sum(r[4] for r in rows) / len(rows)))
    rp = os.path.join(MAIN, "dev", "shots", "stt_verify.json")
    io.open(rp, "w", encoding="utf-8", newline="\n").write(
        json.dumps([{"truth": r[0], "got": r[1], "ratio": r[2], "ms": r[3]} for r in rows],
                   ensure_ascii=False, indent=2))
    print("   明细:", rp)
    print("   判定:", "✓ 手机可借用电脑 large-v3" if avg >= 0.6 else "⚠ 相似度偏低，需要看样本")
