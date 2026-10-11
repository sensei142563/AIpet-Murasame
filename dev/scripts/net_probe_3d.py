# -*- coding: utf-8 -*-
"""网络探针：unpkg / jsDelivr / hf-mirror / raw.githubusercontent 哪些可达；并用 jsDelivr 目录 API 找 VRM 示例模型路径。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-net-probe)"}
TESTS = [
    ("unpkg three", "https://unpkg.com/three@0.186.1/package.json"),
    ("unpkg three-vrm", "https://unpkg.com/@pixiv/three-vrm@3.5.5/package.json"),
    ("jsDelivr three", "https://cdn.jsdelivr.net/npm/three@0.186.1/package.json"),
    ("jsDelivr three-vrm", "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.5.5/package.json"),
    ("jsDelivr 目录API", "https://data.jsdelivr.com/v1/packages/npm/@pixiv/three-vrm@3.5.5"),
    ("hf-mirror", "https://hf-mirror.com/api/models/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"),
    ("raw.githubusercontent", "https://raw.githubusercontent.com/pixiv/three-vrm/dev/README.md"),
    ("github.com", "https://github.com/pixiv/three-vrm"),
]
print("=== 可达性 ===")
alive = {}
for name, url in TESTS:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
            b = r.read(400)
            print("   ✓ %-24s %d 字节" % (name, len(b)))
            alive[name] = True
    except Exception as e:
        print("   ✗ %-24s %s" % (name, str(e)[:60]))
        alive[name] = False

print()
print("=== jsDelivr 目录 API 找 three-vrm 示例模型 ===")
try:
    with urllib.request.urlopen(urllib.request.Request(
            "https://data.jsdelivr.com/v1/packages/gh/pixiv/three-vrm@dev?structure=flat", headers=UA),
            timeout=40) as r:
        j = json.loads(r.read().decode("utf-8", "replace"))
    files = [f.get("name", "") for f in (j.get("files") or [])]
    vrm = [f for f in files if f.lower().endswith(".vrm")]
    print("   仓库里 .vrm 文件 %d 个：" % len(vrm))
    for f in vrm[:20]:
        print("      " + f)
    glb = [f for f in files if f.lower().endswith((".glb", ".gltf"))]
    print("   另有 glb/gltf %d 个（前 6）：" % len(glb))
    for f in glb[:6]:
        print("      " + f)
except Exception as e:
    print("   ✗ 目录 API 失败:", str(e)[:120])
