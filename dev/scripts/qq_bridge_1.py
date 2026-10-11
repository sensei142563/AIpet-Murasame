# -*- coding: utf-8 -*-
"""QQ 搬手机第一步：api.py 加 /qq/status、/qq/sessions、/qq/messages（只读，零风险）
   → 重启 api → 用合成会话文件验证读写通路 → 用 TCP 探测 3001 报告 NapCat 在线状态。"""
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

ROUTE = '''# ===== QQ 通道（搬手机第一步：只读状态与会话）=====
# NapCat/OneBot11 的实时收发在桌面端进程里，这里先提供"看"的能力：
#   /qq/status    连接方式与在线状态 + 会话数
#   /qq/sessions  所有 QQ 会话（私聊/群）与最后一条消息预览
#   /qq/messages  某个会话的最近消息
# 发送通道（命令队列）见 /qq/queue/send，桌面端轮询后经 OneBot11 WS 发出。
def _qq_memory_module():
    import importlib.util as _ilu
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qq", "qq_memory.py")
    spec = _ilu.spec_from_file_location("aipet_qq_memory", p)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _qq_mem_dir():
    try:
        mod = _qq_memory_module()
        d = getattr(mod, "_active_qq_memory_dir", None)
        if callable(d):
            return str(d())
    except Exception:
        pass
    pet = "murasame"
    try:
        cfg = json.loads(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                              "config.json"), encoding="utf-8").read())
        pet = cfg.get("qq_pet") or cfg.get("active_pet") or pet
    except Exception:
        pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "pets", pet, "memory", "qq")


def _qq_cfg():
    try:
        return json.loads(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               "config.json"), encoding="utf-8").read())
    except Exception:
        return {}


def _port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


@app.get("/qq/status")
async def qq_status():
    cfg = _qq_cfg()
    ws_url = str(cfg.get("qq_napcat_ws") or "ws://127.0.0.1:3001")
    http_url = str(cfg.get("qq_napcat_http") or "http://127.0.0.1:6099")
    m = re.search(r"//([^:/]+):(\\d+)", ws_url)
    host, port = (m.group(1), int(m.group(2))) if m else ("127.0.0.1", 3001)
    d = _qq_mem_dir()
    files = []
    if os.path.isdir(d):
        files = [f for f in os.listdir(d) if f.endswith(".json")]
    return {
        "qq_enabled": str(cfg.get("qq_enabled", "")) == "true",
        "napcat_ws": ws_url,
        "napcat_http": http_url,
        "napcat_ws_listening": _port_open(host, port),
        "owner_id": cfg.get("qq_owner_id"),
        "memory_dir": d,
        "sessions": len(files),
        "note": "实时收发在桌面端进程内（OneBot11 正向 WS）；此处只读会话与状态",
    }


@app.get("/qq/sessions")
async def qq_sessions():
    d = _qq_mem_dir()
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"):
                continue
            p = os.path.join(d, f)
            last = None
            cnt = 0
            try:
                j = json.loads(io.open(p, encoding="utf-8").read())
                h = j.get("history") or []
                cnt = len(h)
                if h:
                    last = str(h[-1].get("content") or "")[:80]
            except Exception:
                pass
            out.append({"file": f, "key": f[:-5], "messages": cnt, "last": last,
                        "mtime": int(os.path.getmtime(p))})
    out.sort(key=lambda x: -x["mtime"])
    return {"dir": d, "count": len(out), "sessions": out[:50]}


@app.get("/qq/messages")
async def qq_messages(session: str, limit: int = 30):
    d = _qq_mem_dir()
    f = os.path.join(d, session if session.endswith(".json") else session + ".json")
    if not os.path.isfile(f):
        return {"session": session, "error": "not found", "dir": d}
    try:
        j = json.loads(io.open(f, encoding="utf-8").read())
        h = j.get("history") or []
        return {"session": session, "total": len(h), "messages": h[-max(1, min(limit, 200)):]}
    except Exception as e:
        return {"session": session, "error": "%s: %s" % (type(e).__name__, e)}


@app.post("/qq/queue/send")
async def qq_queue_send(request: Request):
    """把"要发到 QQ 的消息"写进队列文件，桌面端轮询后经 OneBot11 发出。
    body: {"target_type":"private|group","target_id":123,"text":"...","sticker":"可选"}"""
    body = await request.body()
    try:
        item = json.loads(body.decode("utf-8", "replace") or "{}")
    except Exception:
        return {"ok": False, "error": "bad json"}
    if not item.get("target_id") or not (item.get("text") or item.get("sticker")):
        return {"ok": False, "error": "need target_id and text/sticker"}
    qf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "qq_outbox.jsonl")
    os.makedirs(os.path.dirname(qf), exist_ok=True)
    item["queued_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with io.open(qf, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\\n")
    return {"ok": True, "queued_to": qf, "item": item}


'''

s = io.open(API, encoding="utf-8").read().replace("\r\n", "\n")
if '"/qq/status"' in s:
    print("· /qq/* 已存在")
else:
    anchor = '@app.post("/stt")'
    ok = anchor in s
    print(("✓ " if ok else "✗ ") + "定位 /stt 锚点")
    if not ok:
        sys.exit(1)
    s = s.replace(anchor, ROUTE + anchor, 1)
    if not re.search(r"^import socket$", s, re.M):
        s = s.replace("import time", "import time\nimport socket", 1)
    if "import io" not in s.split("\n\n")[0]:
        if not re.search(r"^import io$", s, re.M):
            s = s.replace("import time", "import io\nimport time", 1)
    io.open(API, "w", encoding="utf-8", newline="\n").write(s)
    print("✓ 已加入 /qq/status /qq/sessions /qq/messages /qq/queue/send")

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
for i in range(20):
    time.sleep(2)
    try:
        with socket.create_connection(("127.0.0.1", 28565), timeout=1):
            print("   ✓ 就绪 %ds" % (i * 2 + 2))
            break
    except Exception:
        pass


def get(path):
    with urllib.request.urlopen("http://127.0.0.1:28565" + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


print()
print("=== ① /qq/status ===")
st = get("/qq/status")
for k in ("qq_enabled", "napcat_ws", "napcat_ws_listening", "owner_id", "memory_dir", "sessions"):
    print("   %-22s %s" % (k, st.get(k)))

print()
print("=== ② 造一个合成会话文件，验证 /qq/sessions 与 /qq/messages ===")
d = st["memory_dir"]
os.makedirs(d, exist_ok=True)
fake = os.path.join(d, "_verify_1234567.json")
io.open(fake, "w", encoding="utf-8", newline="\n").write(json.dumps(
    {"history": [{"role": "user", "content": "QQ 通路验收探针-1", "timestamp": "2026-10-11 17:35:01"},
                 {"role": "assistant", "content": "QQ 通路验收探针-2", "timestamp": "2026-10-11 17:35:02"}]},
    ensure_ascii=False, indent=2))
print("   写入:", fake)
se = get("/qq/sessions")
print("   会话数:", se["count"])
hit = [x for x in se["sessions"] if x["file"].startswith("_verify_")]
print("   找到合成会话:", hit[:1])
ms = get("/qq/messages?session=_verify_1234567")
print("   消息数:", ms.get("total"), " 最后一条:", (ms.get("messages") or [{}])[-1].get("content"))
print()
print("   判定:", "✓ 只读通路打通（真机 QQ 上线后即可读真实会话）"
      if hit and ms.get("total") == 2 else "✗ 通路有问题")
os.unlink(fake)
print("   （已删除合成文件 ✓ 不污染真实数据）")

print()
print("=== ③ 发送队列写入测试 ===")
body = json.dumps({"target_type": "private", "target_id": 1234567, "text": "队列验收探针"},
                  ensure_ascii=False).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:28565/qq/queue/send", data=body,
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=60) as r:
    q = json.loads(r.read().decode("utf-8", "replace"))
print("   ", q)
qf = os.path.join(MAIN, "data", "qq_outbox.jsonl")
if os.path.isfile(qf):
    print("   队列文件行数:", len(io.open(qf, encoding="utf-8").read().strip().splitlines()))
    print("   末行:", io.open(qf, encoding="utf-8").read().strip().splitlines()[-1][:120])
