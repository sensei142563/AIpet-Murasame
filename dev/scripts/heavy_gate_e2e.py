# -*- coding: utf-8 -*-
"""真实接口级取证：并发打两个 /tts，期间轮询 /heavy/status，
   应看到 busy=true、holder=tts，且第二个请求进入 waiting。"""
import json
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:28565"


def post(path, body, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, len(r.read()), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, len(e.read() or b""), time.time() - t0
    except Exception as e:
        return -1, str(e)[:80], time.time() - t0


def status():
    with urllib.request.urlopen(BASE + "/heavy/status", timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


print("=== 先看闸门空闲状态 ===")
print("   ", json.dumps(status(), ensure_ascii=False)[:160])

print()
print("=== 并发打两个 /tts（真实重型接口）===")
res = {}


def worker(i):
    res[i] = post("/tts", {"text": "闸门取证第%d句" % i, "pet": "murasame"})


t1 = threading.Thread(target=worker, args=(1,))
t2 = threading.Thread(target=worker, args=(2,))
t1.start()
time.sleep(0.35)          # 让第一个先拿到闸门
observed = []
for _ in range(14):
    observed.append(status())
    time.sleep(0.4)
t2.start()
for _ in range(20):
    observed.append(status())
    time.sleep(0.4)
t1.join(); t2.join()

print("   请求1:", res.get(1))
print("   请求2:", res.get(2))
print()
busy_seen = [o for o in observed if o.get("busy")]
holders = sorted({o.get("holder") for o in busy_seen if o.get("holder")})
waiting_max = max([o.get("waiting") or 0 for o in observed] + [0])
print("=== 观测到的闸门状态 ===")
print("   见到 busy 的采样数: %d / %d" % (len(busy_seen), len(observed)))
print("   占用者: %s" % holders)
print("   最大等待数: %d" % waiting_max)
print()
ok = ("tts" in holders) and (len(busy_seen) > 0)
print("判定:", "✓ 真实重型接口确实被闸门串行（/heavy/status 能看到 holder=tts）"
      if ok else "✗ 没观测到占用 —— 可能 F5 未运行或请求太快，需人工看")
print()
print("   近期历史:", json.dumps(status().get("recent"), ensure_ascii=False)[:300])
