# -*- coding: utf-8 -*-
"""找 Kokoro int8 离线 TTS 包：① hf-mirror 模型搜索 ② sherpa 官方 Release 直链探测（HEAD）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-tts)"}

print("=== ① hf-mirror 搜索 kokoro / vits-zh 模型 ===")
for q in ("kokoro", "vits-zh", "tts-zh"):
    try:
        url = "https://hf-mirror.com/api/models?search=%s&limit=20" % q
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            ms = json.loads(r.read().decode("utf-8", "replace"))
        names = [m.get("modelId") or m.get("id") for m in ms]
        print("   [%s] %d 个：" % (q, len(names)))
        for n in names[:12]:
            print("      " + str(n))
    except Exception as e:
        print("   [%s] ✗ %s" % (q, str(e)[:70]))

print()
print("=== ② sherpa-onnx Release 直链探测（HEAD，看哪个存在与多大）===")
cands = [
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_0.tar.bz2",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-icefall-zh-aishell3.tar.bz2",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-vits-zh-ll.tar.bz2",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-zh-hf-fanchen-C.tar.bz2",
]


class HeadReq(urllib.request.Request):
    def get_method(self):
        return "HEAD"


for u in cands:
    try:
        with urllib.request.urlopen(HeadReq(u, headers=UA), timeout=30) as r:
            size = r.headers.get("Content-Length")
            print("   ✓ %-56s %s MB" % (u.split("/")[-1],
                                        ("%.1f" % (int(size) / 1e6)) if size else "?"))
    except Exception as e:
        print("   ✗ %-56s %s" % (u.split("/")[-1], str(e)[:60]))
