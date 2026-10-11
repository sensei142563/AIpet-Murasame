# -*- coding: utf-8 -*-
"""TTS 路线第一步：预生成台词包。
   台词表 -> 调电脑 F5(/infer, 带 pet 选音色) -> 存 assets/voice/<pet>/<sha1>.wav + index.json
   生成后逐个校验（RIFF 头 / 大小 / 时长），并把统计写进报告。
"""
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAIN = r"E:\university\order\python\pet\AIpet-Murasame-main"
CHAT = r"E:\university\order\python\pet\chatter"
ASSETS = os.path.join(CHAT, "app/src/main/assets/voice")
F5 = "http://127.0.0.1:9881/infer"

# 常用台词（短句优先：合成快、体积小、命中率高）
LINES = {
    "murasame": [
        "主人，你回来啦。",
        "本座等你好久了。",
        "哼，才不是特意等你的。",
        "今天也要好好吃饭哦。",
        "累了就早点休息吧。",
        "要不要本座陪你聊会儿？",
        "主人真厉害呢。",
        "别担心，有本座在。",
        "晚安，做个好梦。",
        "早上好，今天也要加油。",
        "喂，别摸本座的头啦！",
        "本座可是活了五百多年的刀魂。",
    ],
    "noir": [
        "你好呀，今天过得怎么样？",
        "我一直都在这里哦。",
        "需要我帮忙吗？",
        "记得照顾好自己。",
        "晚安，好好休息。",
        "早上好，新的一天开始了。",
    ],
}


def synth(text, pet, timeout=180):
    body = json.dumps({"text": text, "pet": pet}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(F5, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def wav_info(b):
    if len(b) < 44 or b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        return None
    # 找 fmt / data
    i, rate, ch, bits, data_len = 12, 0, 0, 0, 0
    while i + 8 <= len(b):
        cid, sz = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
        if cid == b"fmt ":
            ch, rate, bits = struct.unpack("<H", b[i + 10:i + 12])[0], struct.unpack("<I", b[i + 12:i + 16])[0], struct.unpack("<H", b[i + 22:i + 24])[0]
        elif cid == b"data":
            data_len = sz
            break
        i += 8 + sz + (sz & 1)
    dur = data_len / (rate * ch * max(1, bits // 8)) if rate and ch else 0
    return {"rate": rate, "channels": ch, "bits": bits, "seconds": round(dur, 2),
            "bytes": len(b)}


print("=== 0. F5 健康检查 ===")
try:
    with urllib.request.urlopen("http://127.0.0.1:9881/health", timeout=10) as r:
        print("   /health:", r.read().decode("utf-8", "replace")[:120])
except Exception as e:
    print("   ✗ F5 不可用：", e)
    sys.exit(1)

index = {}
report = []
total_bytes = 0
for pet, lines in LINES.items():
    d = os.path.join(ASSETS, pet)
    os.makedirs(d, exist_ok=True)
    index[pet] = {}
    for text in lines:
        name = hashlib.sha1((pet + "|" + text).encode("utf-8")).hexdigest()[:16] + ".wav"
        fp = os.path.join(d, name)
        t0 = time.time()
        if os.path.isfile(fp) and os.path.getsize(fp) > 20000:
            info = wav_info(io.open(fp, "rb").read())
            print("   · 已存在 %-42s %s" % (text, info))
        else:
            try:
                b = synth(text, pet)
            except Exception as e:
                print("   ✗ 合成失败 %-30s %s" % (text, e))
                continue
            info = wav_info(b)
            if not info:
                print("   ✗ 返回不是合法 WAV %-30s 头=%s" % (text, b[:16]))
                continue
            io.open(fp, "wb").write(b)
            print("   ✓ %-42s %5.2fs  %6.0f KB  (%.1fs 用时)" %
                  (text, info["seconds"], info["bytes"] / 1024, time.time() - t0))
        index[pet][text] = name
        total_bytes += os.path.getsize(fp)
        report.append({"pet": pet, "text": text, "file": name,
                       "seconds": info["seconds"], "bytes": info["bytes"]})

ip = os.path.join(ASSETS, "index.json")
io.open(ip, "w", encoding="utf-8", newline="\n").write(
    json.dumps({"schema": "aipet.voicepack/1", "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "engine": "F5-TTS (longtext/f5tts_server.py)", "index": index},
               ensure_ascii=False, indent=2))
print()
print("=== 结果 ===")
print("   条目数: %d（丛雨 %d / 诺瓦 %d）" %
      (len(report), len(index.get("murasame", {})), len(index.get("noir", {}))))
print("   总体积: %.2f MB" % (total_bytes / 1024 / 1024))
print("   索引文件: %s (%d B)" % (ip, os.path.getsize(ip)))
secs = [r["seconds"] for r in report]
if secs:
    print("   时长: 最短 %.2fs 最长 %.2fs 平均 %.2fs" % (min(secs), max(secs), sum(secs) / len(secs)))
rp = os.path.join(MAIN, "dev", "shots", "voicepack_report.json")
io.open(rp, "w", encoding="utf-8", newline="\n").write(json.dumps(report, ensure_ascii=False, indent=2))
print("   明细: %s" % rp)
