# -*- coding: utf-8 -*-
"""2D→3D 落地可行性探针：① SceneView / Filament 在 Maven Central 是否可得 ② three-vrm 在 npm 是否可得
   ③ 本地是否已有 VRM/glb 资产 ④ 安卓 WebView 方案所需 JS 能否离线打包。"""
import io
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-3d-probe)"}


def get(url, timeout=40):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


print("=== ① Maven Central：安卓 3D 渲染相关库 ===")
probes = [
    ("SceneView (Filament 封装，含 AR)", "https://search.maven.org/solrsearch/select?q=g:io.github.sceneview&rows=8&wt=json"),
    ("Google Filament (Android)", "https://search.maven.org/solrsearch/select?q=g:com.google.android.filament&rows=8&wt=json"),
    ("gltfio", "https://search.maven.org/solrsearch/select?q=a:gltfio&rows=5&wt=json"),
]
for name, url in probes:
    try:
        j = json.loads(get(url))
        docs = j.get("response", {}).get("docs", [])
        print("   %-28s 命中 %d" % (name, len(docs)))
        for d in docs[:4]:
            print("        %s:%s  最新 %s" % (d.get("g"), d.get("a"), d.get("latestVersion") or d.get("v")))
    except Exception as e:
        print("   %-28s ✗ %s" % (name, e))

print()
print("=== ② npm：three / three-vrm（WebView 方案的核心）===")
for pkg in ("three", "@pixiv/three-vrm", "@pixiv/three-vrm-core"):
    try:
        j = json.loads(get("https://registry.npmjs.org/%s" % pkg.replace("/", "%2F")))
        latest = (j.get("dist-tags") or {}).get("latest")
        desc = (j.get("description") or "")[:70]
        print("   %-24s 最新 %-12s %s" % (pkg, latest, desc))
    except Exception as e:
        print("   %-24s ✗ %s" % (pkg, e))

print()
print("=== ③ 本地已有的 3D 资产（VRM/glb/gltf/fbx）===")
root = r"E:\university\order\python\pet"
hits = []
for base, dirs, files in os.walk(root):
    if re.search(r"\\.venv|site-packages|node_modules|GPT-SoVITS|NapCat|\\\.git\\", base):
        dirs[:] = []
        continue
    for f in files:
        if f.lower().endswith((".vrm", ".glb", ".gltf", ".fbx", ".pmx")):
            p = os.path.join(base, f)
            hits.append((os.path.getsize(p), p))
hits.sort(reverse=True)
for sz, p in hits[:12]:
    print("   %9.1f MB  %s" % (sz / 1e6, p.replace(root, ".")))
print("   共 %d 个" % len(hits))

print()
print("=== ④ 安卓仓库现有的 3D/AR 依赖（看要不要新加）===")
g = r"E:\university\order\python\pet\chatter\app\build.gradle.kts"
if os.path.isfile(g):
    for i, l in enumerate(io.open(g, encoding="utf-8", errors="replace").read().splitlines(), 1):
        if re.search(r"implementation|filament|sceneview|arcore|arsceneview|gltf|three", l, re.I):
            print("   %4d| %s" % (i, l.strip()[:130]))
