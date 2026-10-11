# -*- coding: utf-8 -*-
"""用 /stt（原始 WAV body，真重活）做闸门端到端取证：并发两个请求，期间轮询 /heavy/status。"""
import io
import json
import struct
import threading
import time
import urllib.request
import wave

BASE = "http://127.0.0.1:28565"


def make_wav(path, seconds=2.0, sr=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        # 一段有音节的噪声（不是纯静音，避免被优化）
        frames = bytearray()
        for i in range(int(sr * seconds)):
            v = int(6000 * ((i // 400) % 2 * 2 - 1) * (0.3 + 0.7 * ((i % 400) / 400.0)))
            frames += struct.pack("<h", max(-32768, min(32767, v)))
        w.writeframes(bytes(frames))


WAV = r"E:\university\order\python\pet\AIpet-Murasame-main\dev\shots\gate_probe.wav"
make_wav(WAV)
data = io.open(WAV, "rb").read()
print("探针 WAV: %d 字节" % len(data))

print("=== 闸门空闲 ===")
with urllib.request.urlopen(BASE + "/heavy/status", timeout=20) as r:
    print("   ", r.read().decode("utf-8", "replace")[:150])


def status():
    try:
        with urllib.request.urlopen(BASE + "/heavy/status", timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        return {"err": str(e)[:60]}


def post_stt(tag):
    req = urllib.request.Request(BASE + "/stt", data=data,
                                 headers={"Content-Type": "application/octet-stream"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            body = r.read().decode("utf-8", "replace")
        return tag, r.status, round(time.time() - t0, 2), body[:110]
    except urllib.error.HTTPError as e:
        return tag, e.code, round(time.time() - t0, 2), (e.read() or b"").decode("utf-8", "replace")[:110]
    except Exception as e:
        return tag, -1, round(time.time() - t0, 2), str(e)[:110]


print()
print("=== 并发两个 /stt，期间轮询闸门 ===")
res = {}
t1 = threading.Thread(target=lambda: res.__setitem__(1, post_stt(1)))
t2 = threading.Thread(target=lambda: res.__setitem__(2, post_stt(2)))
t1.start()
time.sleep(0.5)
obs = [status()]
t2.start()
for _ in range(40):
    obs.append(status())
    time.sleep(0.5)
    if len(res) == 2 and not obs[-1].get("busy"):
        break
t1.join(); t2.join()

print("   请求1:", res.get(1))
print("   请求2:", res.get(2))
busy = [o for o in obs if o.get("busy")]
holders = sorted({o.get("holder") for o in busy if o.get("holder")})
wmax = max([o.get("waiting") or 0 for o in obs] + [0])
print()
print("   观测到 busy 的采样: %d / %d ；占用者: %s ；最大等待: %d" % (len(busy), len(obs), holders, wmax))
st = status()
print("   近期历史:", json.dumps(st.get("recent"), ensure_ascii=False)[:260])
print()
ok = ("stt" in holders)
print("判定:", "✓ 真实重活确实被闸门串行（观察到 holder=stt，第二个请求进入等待）"
      if ok else "✗ 未观测到占用（可能 STT 太快，或模型未就绪）—— 如实记录")
