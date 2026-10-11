# -*- coding: utf-8 -*-
"""TTS 选型取证：① 候选 sherpa-onnx 离线 TTS 模型在 hf-mirror 的文件与体积
                ② OfflineTtsEngine 期望的目录结构与文件名（确定要下哪些）"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-tts)"}
REPOS = [
    "csukuangfj/vits-icefall-zh-aishell3",
    "csukuangfj/kokoro-multi-lang-v1_0",
    "csukuangfj/sherpa-onnx-vits-zh-ll",
    "csukuangfj/vits-zh-hf-fanchen-C",
]
print("=== ① 候选离线 TTS 模型 ===")
for repo in REPOS:
    url = "https://hf-mirror.com/api/models/%s/tree/main" % repo
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            files = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("   %-40s ✗ %s" % (repo.split("/")[-1], str(e)[:50]))
        continue
    tot, big, has_espeak = 0, [], False
    for f in files:
        if f.get("type") == "file":
            sz = f.get("size") or (f.get("lfs") or {}).get("size") or 0
            tot += sz
            if sz > 200000:
                big.append((f.get("path"), sz))
            if "espeak" in str(f.get("path", "")):
                has_espeak = True
    print("   %-40s 合计 %6.1f MB  espeak目录=%s" % (repo.split("/")[-1], tot / 1e6, has_espeak))
    for n, s in big[:8]:
        print("        %-52s %6.1f MB" % (n, s / 1e6))

print()
print("=== ② OfflineTtsEngine 期望的目录/文件 ===")
p = r"E:\university\order\python\pet\chatter\app\src\main\java\com\aipet\murasame\ui\OfflineTtsEngine.kt"
for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
    if re.search(r'DIR|assets|File\(|model|voices|tokens|espeak|lexicon|lang|dir\b|OfflineTts\w*Config|fun ', l):
        print("   %4d| %s" % (i, l.strip()[:130]))
