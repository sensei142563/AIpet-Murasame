# -*- coding: utf-8 -*-
"""非流式 STT 选型：① 候选模型体积（hf-mirror）② 用 javap 反查 AAR 里 OfflineRecognizer 的确切 API。"""
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-stt)"}
REPOS = [
    "csukuangfj/sherpa-onnx-paraformer-zh-2024-03-09",
    "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
    "csukuangfj/sherpa-onnx-paraformer-zh-2023-09-14",
]
print("=== ① 候选非流式模型（hf-mirror）===")
for repo in REPOS:
    url = "https://hf-mirror.com/api/models/%s/tree/main" % repo
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            files = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("   %-58s ✗ %s" % (repo.split("/")[-1], e))
        continue
    tot, rows = 0, []
    for f in files:
        if f.get("type") == "file":
            sz = f.get("size") or (f.get("lfs") or {}).get("size") or 0
            rows.append((f.get("path"), sz))
            tot += sz
    print("   %-58s 合计 %6.1f MB" % (repo.split("/")[-1], tot / 1e6))
    for n, s in rows:
        if s > 1e5:
            print("        %-56s %6.1f MB" % (n, s / 1e6))

print()
print("=== ② AAR 里 Offline 相关类的确切签名（javap）===")
jbr = r"E:\Android Studio\jbr"
javap = os.path.join(jbr, "bin", "javap.exe")
jars = []
for root, dirs, fs in os.walk(os.path.expanduser("~/.gradle/caches")):
    for f in fs:
        if f == "sherpa-onnx-v1.13.5.aar":
            jars.append(os.path.join(root, f))
print("   javap:", "有" if os.path.isfile(javap) else "无（需用别的方式）", " AAR:", [os.path.basename(j) for j in jars][:1])
if jars and os.path.isfile(javap):
    tmp = os.path.join(os.environ.get("TEMP", "."), "sherpa_javap")
    os.makedirs(tmp, exist_ok=True)
    with zipfile.ZipFile(jars[0]) as z:
        inner = [n for n in z.namelist() if n.endswith(".jar")]
        if inner:
            data = z.read(inner[0])
            cj = os.path.join(tmp, "classes.jar")
            io.open(cj, "wb").write(data)
    print("   已解出 classes.jar: %.1f MB" % (os.path.getsize(cj) / 1e6))
    for cls in ("OfflineRecognizerConfig", "OfflineModelConfig", "OfflineParaformerModelConfig",
                "OfflineSenseVoiceModelConfig", "OfflineRecognizer", "OfflineStream",
                "OfflineRecognizerResult", "FeatureConfig", "OfflineRecognizerKt"):
        r = subprocess.run([javap, "-classpath", cj, "com.k2fsa.sherpa.onnx." + cls],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        out = (r.stdout or r.stderr or "").strip()
        print("   ---- %s ----" % cls)
        for l in out.splitlines()[:26]:
            print("      " + l.strip()[:140])
