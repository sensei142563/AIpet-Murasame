# -*- coding: utf-8 -*-
"""① HEAD 试探 silero_vad.onnx 的官方下载地址 ② 用 Python 从 AAR 里取 classes.jar 并 javap VAD 类。"""
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (aipet-vad)"}


class HeadReq(urllib.request.Request):
    def get_method(self):
        return "HEAD"


print("=== ① silero_vad.onnx 候选地址（HEAD 看是否存在与大小）===")
cands = [
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/vad-models/silero_vad.onnx",
    "https://cdn.jsdelivr.net/gh/k2-fsa/sherpa-onnx@master/silero_vad.onnx",
]
found = []
for u in cands:
    try:
        with urllib.request.urlopen(HeadReq(u, headers=UA), timeout=30) as r:
            n = r.headers.get("Content-Length")
            print("   OK  %-72s %s" % (u.split("/")[-2] + "/" + u.split("/")[-1],
                                       ("%.2f MB" % (int(n) / 1e6)) if n else "?"))
            found.append(u)
    except Exception as e:
        print("   --  %-72s %s" % (u.split("/")[-2] + "/" + u.split("/")[-1], str(e)[:46]))
print("   可用地址: %d 个" % len(found))

print()
print("=== ② 从 AAR 取 classes.jar 并 javap VAD 相关类 ===")
aar = None
root = os.path.join(os.path.expanduser("~"), ".gradle", "caches")
for base, dirs, files in os.walk(root) if os.path.isdir(root) else []:
    for f in files:
        if f.startswith("sherpa-onnx") and f.endswith(".aar"):
            aar = os.path.join(base, f)
            break
    if aar:
        break
if not aar:
    print("   ✗ 没找到 sherpa AAR")
    sys.exit(0)
print("   AAR: %s (%.1f MB)" % (os.path.basename(aar), os.path.getsize(aar) / 1e6))
out = os.path.join(os.environ.get("TEMP", "."), "aipet_aar")
os.makedirs(out, exist_ok=True)
with zipfile.ZipFile(aar) as z:
    names = [n for n in z.namelist() if n.endswith("classes.jar")]
    print("   内含 classes.jar: %s" % names)
    if names:
        z.extract(names[0], out)
        cj = os.path.join(out, names[0])
        print("   解出: %s (%.1f MB)" % (cj, os.path.getsize(cj) / 1e6))
        # 看看 classes.jar 里有哪些 Vad 相关类
        with zipfile.ZipFile(cj) as zj:
            vad_cls = sorted(n for n in zj.namelist()
                             if "vad" in n.lower() or "Vad" in n)
            print("   Vad 相关类 %d 个：" % len(vad_cls))
            for n in vad_cls[:24]:
                print("      " + n)
        javap = r"E:\Android Studio\jbr\bin\javap.exe"
        if os.path.isfile(javap):
            targets = ["com.k2fsa.sherpa.onnx.Vad",
                       "com.k2fsa.sherpa.onnx.SileroVadModelConfig",
                       "com.k2fsa.sherpa.onnx.VadModelConfig"]
            r = subprocess.run([javap, "-classpath", cj] + targets,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            print("   javap 输出：")
            for l in (r.stdout or r.stderr or "").splitlines()[:44]:
                print("      " + l.strip()[:130])
        else:
            print("   ✗ javap 不存在")
