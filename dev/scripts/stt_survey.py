# -*- coding: utf-8 -*-
"""STT 选型取证：① 候选 sherpa-onnx 中文模型在 hf-mirror 上的文件与体积
                ② 本仓库打包的 sherpa-onnx AAR 暴露了哪些识别相关类（决定能否换 paraformer / 离线识别）
                ③ selfTest 目前有没有界面入口"""
import io
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CHAT = r"E:\university\order\python\pet\chatter"
REPOS = [
    "csukuangfj/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20",
    "csukuangfj/sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23",
    "csukuangfj/sherpa-onnx-streaming-paraformer-bilingual-zh-en",
    "csukuangfj/sherpa-onnx-paraformer-zh-2024-03-09",
    "csukuangfj/sherpa-onnx-streaming-zipformer-zh-2023-06-26",
]
UA = {"User-Agent": "Mozilla/5.0 (stt-survey)"}

print("=== ① 候选模型体积（hf-mirror API）===")
for repo in REPOS:
    url = "https://hf-mirror.com/api/models/%s/tree/main" % repo
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            files = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("   %-62s ✗ %s" % (repo.split("/")[-1], e))
        continue
    tot = 0
    onnx = []
    for f in files:
        if f.get("type") == "file":
            sz = f.get("size") or (f.get("lfs") or {}).get("size") or 0
            tot += sz
            if str(f.get("path", "")).endswith(".onnx"):
                onnx.append((f["path"], sz))
    print("   %-62s 合计 %6.1f MB，%d 个 onnx" % (repo.split("/")[-1], tot / 1e6, len(onnx)))
    for n, s in onnx:
        print("        %-58s %6.1f MB" % (n, s / 1e6))

print()
print("=== ② 本仓库 sherpa-onnx AAR 暴露的识别类 ===")
jars = []
for root, dirs, fs in os.walk(os.path.expanduser("~/.gradle/caches")):
    for f in fs:
        if f.endswith(".aar") and "sherpa" in f.lower():
            jars.append(os.path.join(root, f))
    if len(jars) > 6:
        break
print("   AAR 文件:", [os.path.basename(x) for x in jars][:5])
classes = []
for a in jars[:3]:
    try:
        with zipfile.ZipFile(a) as z:
            inner = [n for n in z.namelist() if n.endswith(".jar")]
            for n in inner:
                with z.open(n) as f:
                    with zipfile.ZipFile(io.BytesIO(f.read())) as z2:
                        classes += [x for x in z2.namelist() if x.startswith("com/k2fsa/sherpa/onnx/")]
    except Exception as e:
        print("   读 %s 失败: %s" % (os.path.basename(a), e))
names = sorted({os.path.basename(c).replace(".class", "") for c in classes})
key = [n for n in names if re.search(r"Recognizer|Paraformer|Transducer|Whisper|Offline|Online", n) and "$" not in n]
for n in key[:40]:
    print("   " + n)
print("   总计 %d 个类，其中识别相关 %d 个" % (len(names), len(key)))

print()
print("=== ③ selfTest 的界面入口 ===")
for root, dirs, fs in os.walk(os.path.join(CHAT, "app/src/main/java")):
    for f in fs:
        if f.endswith(".kt"):
            p = os.path.join(root, f)
            for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace").read().splitlines(), 1):
                if "selfTest" in l or "OnlineAsr." in l:
                    print("   %s:%d| %s" % (f, i, l.strip()[:120]))
